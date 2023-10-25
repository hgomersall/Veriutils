from .hdl_blocks import *
from kea.axi import (
    AxiStreamSlaveBFM, axi_stream_buffer, axi_master_playback,
    AxiStreamInterface)

from myhdl import *

import myhdl
from myhdl.conversion._toVHDL import _shortversion
myhdl_vhdl_package_filename = "pck_myhdl_%s.vhd" % _shortversion

import copy
import os
import tempfile
import re

from string import Template
import csv

import random
from collections.abc import MutableMapping, Sequence
from collections import OrderedDict

import inspect

try:
    # Python 3
    from collections.abc import Mapping
except ImportError:
    # Python 2.7
    from collections import Mapping

import sys
PY3 = (sys.version_info[0] == 3)
if PY3:
    string_type = str
else:
    string_type = basestring

if sys.version_info < (3, 8):
    # We need to patch python pre 3.7 so it can deep copy objects with regular
    # expressions.
    # See https://stackoverflow.com/a/56935186
    copy._deepcopy_dispatch[type(re.compile(''))] = lambda r, _: r

__all__ = ['SynchronousTest', 'myhdl_cosimulation', 'SignalOutput',
           'AxiStreamOutput']

PERIOD = 10

# This is a lot of a hack because we want to keep sane signal names in the
# namespace that myhdl can find when populating v*_code (using the $name)
# strategy. We can only really do this in globals().
_quasi_signal_namespace = {}

def _add_local_signal_to_globals(name, signal):

    # We use the calling stack for our quasi namespace
    stack_hierarchy = [
        hierarchy[3] for hierarchy in inspect.stack()[1:-1]][::-1]

    modified_name = name

    if modified_name not in globals():
        globals()[modified_name] = signal

    else:
        while modified_name in globals():
            modified_name = name + '_%06x' % random.randrange(16**6)

        globals()[modified_name] = signal

    containing_dict = _quasi_signal_namespace
    for each_entry in stack_hierarchy:
        try:
            containing_dict = containing_dict[each_entry]
        except KeyError:
            containing_dict[each_entry] = {}
            containing_dict = containing_dict[each_entry]

    containing_dict[name] = modified_name

    return modified_name

def _get_globals_signal_name(name):
    # We assume we are accessing from the same function that has already
    # added a signal to the globals
    stack_hierarchy = [
        hierarchy[3] for hierarchy in inspect.stack()[1:-1]][::-1]

    containing_dict = _quasi_signal_namespace
    for each_entry in stack_hierarchy:
        try:
            containing_dict = containing_dict[each_entry]
        except KeyError:
            raise KeyError('Could not find local signal in the global '
                           'quasi-namespace. This is likely a Veriutils bug.')

    modified_name = containing_dict[name]

    return modified_name

def _get_local_signal_from_globals(name):

    modified_name = _get_globals_signal_name(name)
    return globals()[modified_name]

@block
def file_writer(filename, signal_list, clock, signal_names=None):

    vhdl_signal_str_write_list = []
    vhdl_name_str_write_list = []

    verilog_signal_str_write_list = []
    verilog_name_str_write_list = []

    vhdl_annotations = ''
    verilog_annotations = ''

    for n, each_signal in enumerate(signal_list):
        modified_sig_name = (
            _add_local_signal_to_globals('signal_' + str(n), each_signal))
        each_signal.read = True

        if signal_names is None:
            vhdl_name_str_write_list.append(
                'write(output_line, string\'(\"$%s\"));' % modified_sig_name)
            verilog_name_str_write_list.append(
                '$$fwrite(output_file, \"$%s\");' % modified_sig_name)
        else:
            # We assign the signal headers from the signal names
            vhdl_name_str_write_list.append(
                'write(output_line, string\'(\"%s\"));' % signal_names[n])
            verilog_name_str_write_list.append(
                '$$fwrite(output_file, \"%s\");' % signal_names[n])

            port_name = signal_names[n].split()[-1]
            annotation = '<name_annotation> $%s %s' % (modified_sig_name,
                                                       port_name)
            vhdl_annotations += '-- %s\n' % annotation
            verilog_annotations += '// %s\n' % annotation

        if isinstance(each_signal._val, bool):
            vhdl_signal_str_write_list.append(
                'write(output_line, std_logic($%s));' % modified_sig_name)
        else:
            vhdl_signal_str_write_list.append(
                'write(output_line, std_logic_vector($%s));' %
                modified_sig_name)

        verilog_signal_str_write_list.append(
            '$$fwrite(output_file, \"%%b\", $%s);' % modified_sig_name)

    vhdl_name_indent = ' ' * 12
    vhdl_name_str_write = (
        ('\n%swrite(output_line, string\'(\",\"));\n%s' %
         (vhdl_name_indent, vhdl_name_indent))
        .join(vhdl_name_str_write_list))

    verilog_name_indent = ' ' * 4
    verilog_name_str_write = (
        ('\n%s$$fwrite(output_file, \",\");\n%s' %
         (verilog_name_indent, verilog_name_indent))
        .join(verilog_name_str_write_list))

    vhdl_signal_indent = ' ' * 8
    vhdl_signal_str_write = (
        ('\n%swrite(output_line, string\'(\",\"));\n%s' %
         (vhdl_signal_indent, vhdl_signal_indent))
        .join(vhdl_signal_str_write_list))

    verilog_signal_indent = ' ' * 12
    verilog_signal_str_write = (
        ('\n%s$$fwrite(output_file, \",\");\n%s' %
         (verilog_signal_indent, verilog_signal_indent))
        .join(verilog_signal_str_write_list))

    file_writer.verilog_code = '''
%s
initial begin: write_to_file
    integer output_file;

    output_file = $$fopen("%s", "w");

    %s
    $$fwrite(output_file, "\\n");
    $$fflush(output_file);

    while (1'b1) begin
        @(posedge $clock) begin
            %s
            $$fwrite(output_file, "\\n");
            $$fflush(output_file);
        end
    end
end
    ''' % (verilog_annotations, filename, verilog_name_str_write,
           verilog_signal_str_write,)

    file_writer.vhdl_code = '''
%s
write_to_file: process ($clock) is

    file output_file : TEXT open WRITE_MODE is "%s";
    variable output_line : LINE;
    variable first_line_to_print : boolean := true;
begin
    if rising_edge($clock) then
        if first_line_to_print then
            %s
            writeLine(output_file, output_line);
            first_line_to_print := false;
        end if;
        %s
        writeline(output_file, output_line);
    end if;
end process write_to_file;
    ''' % (vhdl_annotations, filename, vhdl_name_str_write,
           vhdl_signal_str_write,)

    @always(clock.posedge)
    def _dummy_file_writer():
        # It's necessary to access all the signals in the right way inside
        # the dummy writer in order that the used signals can be inferred
        # correctly.
        for n in range(len(signal_list)):
            print(_get_local_signal_from_globals('signal_' + str(n)))

    return _dummy_file_writer

@block
def axi_stream_file_writer(
    clock, axi_stream_interface, axi_writer_suffix, filename):

    vhdl_signal_str_write_list = []
    vhdl_name_str_write_list = []

    verilog_signal_str_write_list = []
    verilog_name_str_write_list = []

    signal_TVALID_name = _add_local_signal_to_globals(
        'signal_TVALID', axi_stream_interface.TVALID)
    axi_stream_interface.TVALID.read = True


    signal_TREADY_name = _add_local_signal_to_globals(
        'signal_TREADY', axi_stream_interface.TREADY)
    axi_stream_interface.TREADY.driven = 'reg'

    signal_names = ('TDATA', 'TLAST', 'TKEEP', 'TSTRB', 'TID', 'TDEST')

    for each_signal_name in signal_names:
        try:
            each_signal = getattr(axi_stream_interface, each_signal_name)
        except AttributeError:
            # Attribute not available, so ignore it.
            continue

        modified_sig_name = _add_local_signal_to_globals(
            'signal_' + each_signal_name, each_signal)
        each_signal.read = True

        if signal_names is None:
            vhdl_name_str_write_list.append(
                'write(output_line, string\'(\"$%s\"));' % modified_sig_name)
            verilog_name_str_write_list.append(
                '$$fwrite(output_file, \"$%s\");' % modified_sig_name)
        else:
            # We assign the signal headers from the signal names
            vhdl_name_str_write_list.append(
                'write(output_line, string\'(\"%s\"));' % each_signal_name)
            verilog_name_str_write_list.append(
                '$$fwrite(output_file, \"%s\");' % each_signal_name)


        if isinstance(each_signal._val, bool):
            vhdl_signal_str_write_list.append(
                'write(output_line, std_logic($%s));' % modified_sig_name)
        else:
            vhdl_signal_str_write_list.append(
                'write(output_line, std_logic_vector($%s));' %
                modified_sig_name)

        verilog_signal_str_write_list.append(
            '$$fwrite(output_file, \"%%b\", $%s);' % modified_sig_name)

    vhdl_name_indent = ' ' * 16
    vhdl_name_str_write = (
        ('\n%swrite(output_line, string\'(\",\"));\n%s' %
         (vhdl_name_indent, vhdl_name_indent))
        .join(vhdl_name_str_write_list))

    verilog_name_indent = ' ' * 4
    verilog_name_str_write = (
        ('\n%s$$fwrite(output_file, \",\");\n%s' %
         (verilog_name_indent, verilog_name_indent))
        .join(verilog_name_str_write_list))

    vhdl_signal_indent = ' ' * 12
    vhdl_signal_str_write = (
        ('\n%swrite(output_line, string\'(\",\"));\n%s' %
         (vhdl_signal_indent, vhdl_signal_indent))
        .join(vhdl_signal_str_write_list))

    verilog_signal_indent = ' ' * 16
    verilog_signal_str_write = (
        ('\n%s$$fwrite(output_file, \",\");\n%s' %
         (verilog_signal_indent, verilog_signal_indent))
        .join(verilog_signal_str_write_list))

    axi_stream_file_writer.verilog_code = '''
initial begin: write_to_file_%s
    integer output_file;

    output_file = $$fopen("%s", "w");

    %s
    $$fwrite(output_file, "\\n");
    $$fflush(output_file);

    while (1'b1) begin
        @(posedge $clock) begin
            $%s = 1;

            if ($%s & $%s) begin
                %s
                $$fwrite(output_file, "\\n");
                $$fflush(output_file);
            end
        end
    end
end
    ''' % (axi_writer_suffix, filename, verilog_name_str_write,
           signal_TREADY_name, signal_TVALID_name, signal_TREADY_name,
           verilog_signal_str_write,)

    axi_stream_file_writer.vhdl_code = '''
write_to_file_%s: process ($clock) is

    file output_file : TEXT open WRITE_MODE is "%s";
    variable output_line : LINE;
    variable first_line_to_print : boolean := true;
begin
    if rising_edge($clock) then
        $%s <= '1';

        if $%s='1' and $%s='1' then
            if first_line_to_print then
                %s
                writeLine(output_file, output_line);
                first_line_to_print := false;
            end if;
            %s
            writeline(output_file, output_line);
        end if;
    end if;
end process write_to_file_%s;
    ''' % (axi_writer_suffix, filename, signal_TREADY_name,
           signal_TREADY_name, signal_TVALID_name, vhdl_name_str_write,
           vhdl_signal_str_write, axi_writer_suffix)

    @always(clock.posedge)
    def _dummy_file_writer():
        # It's necessary to access all the signals in the right way inside
        # the dummy writer in order that the used signals can be inferred
        # correctly.
        axi_stream_interface.TREADY.next = 1

        if axi_stream_interface.TVALID and axi_stream_interface.TREADY:
            for signal_name in signal_names:
                print(_get_local_signal_from_globals('signal_' + signal_name))

    return _dummy_file_writer


class SimulationOutputGroup(Sequence):

    def __init__(self, group_dict):
        self._lookups = group_dict

        self._output_length = None

        for each in group_dict:
            if self._output_length is None:
                self._output_length = len(group_dict[each])

            else:
                if len(group_dict[each]) != self._output_length:
                    raise ValueError(
                        'All the signal outputs need to be the same length')

        self._setup_prototypes()

    def __eq__(self, other):
        if not isinstance(other, SimulationOutputGroup):
            return False

        return other._lookups == self._lookups

    def __repr__(self):
        return [each for each in self].__repr__()

    def _setup_prototypes(self):
        ''' Creates an ordered dictionary of objects that can be used to
        create the necessary output.

        The ordered dictionary, when traversed in order, should produce a
        coherent result. See __getitem__ for its usage.
        '''

        prototype_outputs = OrderedDict()

        create_list = lambda n: [None] * n
        create_dict = lambda keys: {key: None for key in keys}

        for each_key in self._lookups.keys():
            prototype_lookup = []

            for layer in each_key:
                tuple_lookup = tuple(prototype_lookup)

                if isinstance(layer, str):
                    # In the outputs, create or update the a representing the
                    # interface type
                    if tuple_lookup not in prototype_outputs:
                        keys = set([layer])
                    else:
                        keys = prototype_outputs[tuple_lookup][1]
                        keys.add(layer)

                    prototype_outputs[tuple_lookup] = (create_dict, keys)

                elif isinstance(layer, int):
                    # In the outputs, create or update a list
                    if tuple_lookup not in prototype_outputs:
                        # The second arg gives the length
                        prototype_outputs[tuple_lookup] = (
                            create_list, layer + 1)

                    elif layer >= prototype_outputs[tuple_lookup][1]:
                        # We need to make the length longer
                        prototype_outputs[tuple_lookup] = (
                            create_list, layer + 1)

                    else:
                        # We can leave it as is
                        pass

                prototype_lookup.append(layer)

        self._prototype_outputs = prototype_outputs

    def __getitem__(self, index):

        def get_int_indexed_value(index):
            for each in self._prototype_outputs:
                factory, arg = self._prototype_outputs[each]

                if each == ():
                    # The base case
                    output = factory(arg)

                else:
                    output_layer = output
                    for layer in each[:-1]:
                        output_layer = output_layer[layer]

                    output_layer[each[-1]] = factory(arg)

            for each in self._lookups:
                output_layer = output
                for layer in each[:-1]:
                    output_layer = output_layer[layer]

                output_layer[each[-1]] = self._lookups[each][index]

            return output

        if isinstance(index, slice):
            start, stop, step = index.indices(self._output_length)

            return [get_int_indexed_value(int_index)
                    for int_index in range(start, stop, step)]

        elif isinstance(index, int):
            return get_int_indexed_value(index)

        else:
            raise TypeError('list indices must be integers or slices')

    def __len__(self):
        return self._output_length

class SimulationOutputs(MutableMapping):
    def __init__(self, init_dict=None):
        self._lookups = {}
        self._user_keys = set()
        self._list_checker = re.compile(
            '\A([a-zA-Z_][a-zA-Z0-9_]*)\[(\d+)\]\Z')

        if init_dict is not None:
            for each_key in init_dict:
                self[each_key] = init_dict[each_key]

    def __repr__(self):
        user_key_dict = {each: self[each] for each in self._user_keys}
        return user_key_dict.__repr__()

    def __iter__(self):
        return iter(self._user_keys)

    def _str_key_to_tuple_key(self, item_key):
        assert isinstance(item_key, str)

        split_key = item_key.split('.')

        # We check to see if the last (leaf) entry is a list.
        index_match = self._list_checker.match(split_key[-1])

        if index_match is not None:
            list_name = index_match.groups()[0]
            list_index = int(index_match.groups()[1])

            if list_index is not None:
                # If we have a list lookup, we need to remove it from the
                # last element and append it as a new element.
                split_key[-1] = list_name
                split_key.append(list_index)

        return tuple(split_key)

    def _get_group_from_key(self, group_key):
        assert isinstance(group_key, tuple)

        group_key_depth = len(group_key)

        # We now populate the group from the lookups dict, stripping out the
        # group key.
        group = {}
        for each_key in self._lookups:
            # Defensive (this should not happen)
            # We make sure we haven't got some weird call going on in which
            # the group key is the same as a key in lookups. This should
            # be picked up _before_ this function is called.
            assert each_key != group_key

            # Check if the first part of the tuple is same as group_key
            if each_key[:group_key_depth] == group_key:
                # If it is, use the second part to populate the new group
                # dict.
                group[each_key[group_key_depth:]] = self._lookups[each_key]

        if len(group) > 0:
            return group
        else:
            return None

    def __setitem__(self, item, val):
        self._lookups[self._str_key_to_tuple_key(item)] = val
        self._user_keys.add(item)

    def __getitem__(self, item):
        lookup = self._str_key_to_tuple_key(item)

        if lookup in self._lookups:
            return self._lookups[self._str_key_to_tuple_key(item)]

        else:
            group = self._get_group_from_key(lookup)
            if group is not None:
                return SimulationOutputGroup(group)

            raise KeyError(
                '"{}" not in the outputs, and no other way of accessing it is '
                'available'.format(item))

    def __delitem__(self, item):
        del self._lookups[self._str_key_to_tuple_key(item)]
        self._user_keys.discard(item)

    def __len__(self):
        return len(self._lookups)

class SignalOutput(list):
    pass

class AxiStreamOutput(dict):
    pass

class ObjectLookup(object):

    def __init__(self):
        self._uniqueifier = None

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '{}({})'.format(self.type, self.name)

    @property
    def signal_type_str(self):
        try:
            if isinstance(self.object.val, intbv):
                if self.object.min < 0:
                    return 'signed'

                else:
                    return 'unsigned'

            elif isinstance(self.object.val, bool):
                return 'bool'

        except AttributeError:
            raise ValueError(
                'Object is not a signal to have an associated signal type.')

    def bump_uniqueifier(self):
        if self._uniqueifier is None:
            self._uniqueifier = 0

        else:
            self._uniqueifier += 1

    def store_sim_value(self, base_dict, val):
        '''Appends val to the list contained in
        base_dict[self.name]['signals'].

        If base_dict[self.name] does not exist, a new list is created
        to populate.
        '''

        if self.name in base_dict:
            assert isinstance(base_dict[self.name], SignalOutput)

        else:
            base_dict[self.name] = SignalOutput()

        base_dict[self.name].append(val)

    def extract_sim_values(self, base_dict):
        '''Extracts the values from the base dictionary using the lookup of
        this argument. This is essentially the reverse of `store_sim_value`,
        but it will iterate over the full list and return every value
        recorded.

        It assumes the signal is present in the dictionary.
        '''
        return copy.copy(base_dict[self.name])

    def clone(self):
        new_self = copy.copy(self)
        new_self._obj = copy_signal(self._obj)
        return new_self

    @property
    def object(self):
        return self._obj

    @property
    def type(self):
        return self._obj_type

    @property
    def init_str(self):
        if isinstance(self.object, myhdl._Signal._Signal):

            if isinstance(self.object.val, intbv):
                max_val = self.object.max
                min_val = self.object.min

                if min_val == 0 and max_val == 2**(len(self.object)):
                    return 'Signal(intbv({})[{}:])'.format(
                        int(self.object._init), len(self.object))

                else:
                    return 'Signal(intbv({}, min={}, max={}))'.format(
                        int(self.object._init), self.object.min,
                        self.object.max)

            elif isinstance(self.object.val, bool):
                return 'Signal({})'.format(self.object._init)

            else:
                raise ValueError("Unhandled type: {}".format(self.name))

        else:
            return repr(self.object)



class SimpleObject(ObjectLookup):

    @property
    def name(self):
        return self._basename

    @property
    def convertible_name(self):
        convertible_name = self.name
        if self._uniqueifier is None:
            return convertible_name
        else:
            return convertible_name + '_{}'.format(self._uniquefier)

    @property
    def recording_header(self):
        return 'simple {} {}'.format(self.signal_type_str, self.name)

    def __init__(self, basename, obj, obj_type):
        super(SimpleObject, self).__init__()

        self._basename = basename
        self._obj = obj
        self._obj_type = obj_type

class ObjectInList(ObjectLookup):

    @property
    def name(self):
        return self._basename + '[{}]'.format(self._index)

    @property
    def convertible_name(self):
        convertible_name = self._basename + '{}'.format(self._index)

        if self._uniqueifier is None:
            return convertible_name
        else:
            return convertible_name + '_{}'.format(self._uniquefier)

    @property
    def recording_header(self):
        return 'list {} {}'.format(self.signal_type_str, self.name)


    def __init__(self, basename, obj_list, index, obj_type):

        super().__init__()
        self._basename = basename
        self._obj_type = obj_type
        self._obj = obj_list[index]
        self._index = index

class ObjectInInterface(ObjectLookup):

    @property
    def depth(self):
        return len(self._interface_lookup)

    @property
    def name(self):
        return self._basename + '.' + '.'.join(self._interface_lookup)

    @property
    def convertible_name(self):
        convertible_name = (
            self._basename + '_' + '_'.join(self._interface_lookup))

        if self._uniqueifier is None:
            return convertible_name
        else:
            return convertible_name + '_{}'.format(self._uniquefier)

    @property
    def recording_header(self):
        return 'interface {} {}'.format(self.signal_type_str, self.name)

    @property
    def base_interface(self):
        return self._interface

    @property
    def parent_interface(self):

        layer = self.base_interface

        for layer_name in self._interface_lookup[:-1]:
            layer = getattr(layer, layer_name)

        return layer

    def __init__(self, basename, interface, interface_lookup, obj_type):

        super().__init__()

        self._basename = basename
        self._obj_type = obj_type

        layer = interface
        for layer_name in interface_lookup:
            layer = getattr(layer, layer_name)

        self._obj = layer
        self._interface = interface
        self._interface_lookup = interface_lookup

class ObjectInListInInterface(ObjectLookup):

    @property
    def name(self):
        return (self._basename + '.' + '.'.join(self._interface_lookup)
                + '[{}]'.format(self._index))

    @property
    def convertible_name(self):
        convertible_name = (
            self._basename + '_' + '_'.join(self._interface_lookup) +
            '_{}'.format(self._index))

        if self._uniqueifier is None:
            return convertible_name
        else:
            return convertible_name + '_{}'.format(self._uniquefier)

    @property
    def recording_header(self):
        return 'interface_list {} {}'.format(self.signal_type_str, self.name)

    def __init__(
        self, basename, interface, interface_lookup, obj_type, index):

        super().__init__()

        self._basename = basename
        self._obj_type = obj_type

        layer = interface
        for layer_name in interface_lookup:
            layer = getattr(layer, layer_name)

        self._obj = layer[index]
        self._interface = interface
        self._interface_lookup = interface_lookup
        self._index = index

def _expand_to_signal_hierarchy(signal_obj, depth=0):
    '''Takes an object - like a signal, list of signals or an
    interface, and returns the hierachy of that object. If signal_obj is a
    signal, then the attribute hierarchy is empty. Each value in the attribute
    name list is one more layer down in the interface hierarchy.
    '''
    if isinstance(signal_obj, myhdl._Signal._Signal):
        return [], [signal_obj]

    elif isinstance(signal_obj, list):
        # Already a list. Check it's a list of signals.
        all_non_signals = True
        for each in signal_obj:
            if isinstance(each, myhdl._Signal._Signal):
                all_non_signals = False

        if all_non_signals:
            return [], []

        return [], signal_obj

    else:
        signal_list = []
        attribute_name_list = []

        try:
            for each in signal_obj.__dict__:
                each_attr_name_list, each_signal_list = (
                    _expand_to_signal_hierarchy(
                        getattr(signal_obj, each), depth=depth+1))

                if each_signal_list != []:
                    signal_list += each_signal_list
                    attribute_name_list += [(each, each_attr_name_list)]

        except AttributeError as e:
            # A non-signal, non-interface
            return [], []

        return attribute_name_list, signal_list

def _turn_object_hierarchy_types_into_name_list(hierarchy, indent=''):
    '''A function that recurses through the object
    hierachy and generates a list of the names in the hierarchy in order.

    It describes the unique lookup from the base to the leaf.
    '''
    name_list = []
    type_list = []
    for each in hierarchy:
        if each[1] is None:
            # We ignore the object, since it was explicitly excluded in
            # the hierarchy
            pass

        elif isinstance(each[1][0], str):
            name_list.append([each[0]])
            type_list.append(each[1][0])

        else:
            _name_list, _type_list = (
                _turn_object_hierarchy_types_into_name_list(each[1]))

            name_list += [
                [each[0]] + flattened_each for flattened_each in _name_list]
            type_list += _type_list

    return name_list, type_list

def _flatten_hierarchy(name, hierarchy_object, hierarchy_types):
    '''Returns a flat list of subclasses of `ObjectLookup` that
    describes how to extract an object from the passed in hierarchy_object.
    '''
    if hierarchy_types == ['non-signal']:
        return [SimpleObject(name, hierarchy_object, hierarchy_types[0])]

    elif isinstance(hierarchy_object, myhdl._Signal._Signal):
        return [SimpleObject(name, hierarchy_object, hierarchy_types[0])]

    elif isinstance(hierarchy_object, list):
        if len(hierarchy_types) == 1:
            this_type = hierarchy_types[0]
            list_types = [
                this_type if isinstance(each, myhdl._Signal._Signal)
                else 'non-signal' for each in hierarchy_object]

        return [ObjectInList(name, hierarchy_object, idx, each_type) for
                idx, each_type in enumerate(list_types)]

    else:
        name_list, type_list = (
            _turn_object_hierarchy_types_into_name_list(hierarchy_types))

        return_objects = []
        for each_lookup, each_type in zip(name_list, type_list):
            leaf_object = hierarchy_object
            for node in each_lookup:
                leaf_object = getattr(leaf_object, node)

            if isinstance(leaf_object, list):
                if not isinstance(each_type, list) or len(each_type) == 0:
                    this_type = each_type
                    list_types = [
                        this_type if isinstance(each, myhdl._Signal._Signal)
                        else 'non-signal' for each in leaf_object]
                else:
                    list_types = each_type

                for n, list_type in enumerate(list_types):
                    return_objects.append(
                        ObjectInListInInterface(
                            name, hierarchy_object, each_lookup, list_type, n))

            else:
                return_objects.append(
                    ObjectInInterface(
                        name, hierarchy_object, each_lookup, each_type))

        return return_objects

class MissingSignalError(Exception):
    def __init__(self, signal_name):
        self.signal_name = signal_name
        super(MissingSignalError, self).__init__('')


def _types_from_signal_hierarchy(hierarchy, types):
    '''For every entry in the hierarchy, find the corresponding types.

    This might propagate down the hierarchy from a string, or be a dict.
    '''
    if len(hierarchy) == 0:
        _types = [types]

    else:
        _types = []
        for name, next_hierarchy in hierarchy:
            try:
                if isinstance(types, string_type):
                    _types.append((name, _types_from_signal_hierarchy(
                        next_hierarchy, types)))

                else:
                    try:
                        _types.append(
                            (name, _types_from_signal_hierarchy(
                                next_hierarchy, types[name])))
                    except KeyError:
                        # This signal is not in the type dict, so we set it
                        # to None so it can be removed later
                        _types.append((name, None))
            except MissingSignalError as e:
                # There was a missing signal in the hierarchy, so we need to
                # propagate the excption with a bit more info about what
                # signal it was.
                raise MissingSignalError(name + '.' + e.signal_name)

    def _contains_only_non_signals(type_val):
        '''Recurses through a dict of strings, ending in a string and checks
        that the leaf value is 'non-signal', otherwise False is returned.
        '''
        if isinstance(type_val, dict):
            return all(
                _contains_only_non_signals(type_val[each])
                for each in type_val)

        else:
            assert isinstance(type_val, str)
            return type_val == 'non-signal'

    # Check we've covered all the types that were passed in by the user,
    # otherwise we want to raise an exception.
    if isinstance(types, dict):
        _inferred_type_keys = [each[0] for each in _types]
        for set_name in types:
            if set_name not in _inferred_type_keys:
                if not _contains_only_non_signals(types[set_name]):
                    raise MissingSignalError(set_name)

    return _types


class Args(object):

    def __getitem__(self, item):
        for each in self:
            if item == each.name:
                return each
        else:
            raise KeyError

    def __iter__(self):
        return iter(self.flattened_args)

    @property
    def types(self):
        return [each.type for each in self]

    @property
    def objects(self):
        return [each.object for each in self]

    @property
    def names(self):
        return [each.name for each in self]

    @property
    def convertible_names(self):
        return [each.convertible_name for each in self]

    @property
    def outputs(self):
        return [each for each in self if each.type == 'output']

    @property
    def args(self):
        return self._args

    @property
    def axi_stream_in_interfaces(self):
        interfaces = {}
        for arg in self:
            if arg.type == 'axi_stream_in':
                if not isinstance(arg, ObjectInInterface):
                    raise ValueError(
                        'Signal is set to "axi_stream_in", but is not in an '
                        'interface: {}'.format(arg.name))

                if not isinstance(arg.parent_interface, AxiStreamInterface):
                    raise ValueError(
                        'Signal is set to "axi_stream_in", but is not in an '
                        'interface of type AxiStreamInterface: {}'.format(
                            arg.name))

                interface_name = '.'.join(arg.name.split('.')[:-1])

                if interface_name in interfaces:
                    assert arg.parent_interface is interfaces[interface_name]

                interfaces[interface_name] = arg.parent_interface

        return interfaces

    @property
    def axi_stream_out_interfaces(self):
        interfaces = {}
        for arg in self:
            if arg.type == 'axi_stream_out':
                if not isinstance(arg, ObjectInInterface):
                    raise ValueError(
                        'Signal is set to "axi_stream_out", but is not in an '
                        'interface: {}'.format(arg.name))

                if not isinstance(arg.parent_interface, AxiStreamInterface):
                    raise ValueError(
                        'Signal is set to "axi_stream_out", but is not in an '
                        'interface of type AxiStreamInterface{}'.format(
                            arg.name))

                interface_name = '.'.join(arg.name.split('.')[:-1])

                if interface_name in interfaces:
                    assert arg.parent_interface is interfaces[interface_name]

                interfaces[interface_name] = arg.parent_interface

        return interfaces

    def clone_for_dut(self):
        '''Creates a copy of self, with certain signal types being copied, and
        certain types being kept the same.
        '''

        def _replicate_signals(signal_collection, types, depth=0):

            if not isinstance(signal_collection, dict):
                # Use the __dict__ attribute of the object
                signal_dict = signal_collection.__dict__
                is_dict = False
            else:
                signal_dict = signal_collection
                is_dict = True

            output_dict = signal_dict.copy()

            for name in types:
                if (types[name] == 'output' or types[name] == 'random'):
                    if isinstance(signal_dict[name], list):
                        # Special case signal lists
                        # Only copy the signals
                        output_dict[name] = [
                            copy_signal(each) if
                            isinstance(each, myhdl._Signal._Signal) else
                            each for each in signal_dict[name]]
                    else:
                        output_dict[name] = copy_signal(signal_dict[name])

                elif (types[name] == 'axi_stream_out' or
                      types[name] == 'axi_stream_in'):
                    # We copy all the axi stream signals.
                    output_dict[name] = copy_signal(signal_dict[name])

                elif types[name] == 'non-signal':
                    # Non signals are not copied. The rationale is that
                    # only the outputs should be different between the
                    # dut and the ref
                    pass

                elif types[name] in self._valid_arg_types:
                    # We don't want to copy
                    continue

                else:
                    # We have an interface, so recurse
                    output_dict[name] = _replicate_signals(
                        signal_dict[name], types[name])

            if is_dict:
                output = output_dict
            else:
                output = copy.copy(signal_collection)
                for name in types:
                    setattr(output, name, output_dict[name])

            return output

        dut_args = _replicate_signals(self.args, self.arg_types)

        return Args(dut_args, self.arg_types)

    def __init__(self, args, arg_types):

        valid_arg_types = ('clock', 'init_reset', 'random', 'output',
                           'custom', 'custom_reset', 'axi_stream_out',
                           'axi_stream_in', 'non-signal')

        flattened_args = []
        for each_arg in args:

            hierarchy, signal_objects = (
                _expand_to_signal_hierarchy(args[each_arg]))

            if ((len(signal_objects) == 0) and
                arg_types[each_arg] != 'non-signal'):
                # The hierarchy lookup returned no signals, but the type
                # is set to be a signal type.
                raise ValueError(
                    'A argument that has no signal component is set to '
                    'be a signal type: {} set as {}'.format(
                        each_arg, arg_types[each_arg]))

            try:
                hierarchy_types = _types_from_signal_hierarchy(
                    hierarchy, arg_types[each_arg])

            except MissingSignalError as e:
                missing_signal = each_arg + '.' + e.signal_name
                raise KeyError(
                    'Arg type dict references a non-existant '
                    'signal or signal type: {}'.format(missing_signal))

            flattened_args += _flatten_hierarchy(
                each_arg, args[each_arg], hierarchy_types)

        unique_convertible_names = []
        for each_arg in flattened_args:

            if (each_arg.type != 'non-signal' and
                not isinstance(each_arg.object, myhdl._Signal._Signal)):

                # Every type except non-signal should have been expanded out
                # to a Signal (encapsulated within an ObjectLookup). This
                # means we can check and error if it's not a signal.
                raise ValueError(
                    'Unsupported argument type: {} is set to be of type {}, '
                    'but we cannot handle it as such.'.format(
                        each_arg.name, each_arg.type))

            if each_arg.type not in valid_arg_types:
                raise ValueError(
                    'Invalid argument or argument types:'
                    ' All the signals in the hierarchy '
                    'should be one of type: %s (signal %s)' %
                    (', '.join(valid_arg_types), each_arg.name))

            while each_arg.convertible_name in unique_convertible_names:
                each_arg.bump_uniqueifier()

            unique_convertible_names.append(each_arg.convertible_name)

        self.flattened_args = flattened_args
        self._valid_arg_types = valid_arg_types
        self._args = args
        self.arg_types = arg_types


class SynchronousTest(object):

    def __init__(self, dut_factory, ref_factory, args, arg_types,
                 period=None, custom_sources=None,
                 enforce_convertible_top_level_interfaces=True,
                 time_units='ns'):
        '''Construct a synchronous test case for the pair of factories
        given by `dut_factory` and `ref_factory`. Each factory is constructed
        with the provided args (which probably corresponds to a signal list).

        if `dut_factory` is None, then it is simply not used

        arg_types specifies how each arg should be handled. It is a dict to
        a valid type string. The supported type strings are:
            * `'clock'`
            * `'init_reset'`
            * `'random'`
            * `'output'`
            * `'custom'`
            * `'custom_reset'`
            * `'axi_stream_in'`
            * `'axi_stream_out'`
            * `'non-signal'`

        * The `'clock'` arg is auto-connected to a clock generator. There
        should be one and only one clock object.
        * `'init_reset'` should be a reset signal, and is auto-connected to
        a reset generator that drives active for a few cycles, then goes
        inactive. That is, it resets at initialization.
        * A `'random'` arg is a signal that is auto-connected to a random
        number generator. This can be any type of signal.
        * `'output'` args are simply recorded, but are duplicated for the
        dut_factory. This means the dut_factory and the ref_factory can
        output different values. Note, this also means that if a custom_source
        takes an output as one of its signals, it is the output that
        corresponds to that being driven by the instance from `ref_factory`
        (i.e. the reference).
        * A `'custom'` arg is assumed to be handled elsewhere (say, as a
        constant or handled through a custom_source).
        * `'custom_reset'` is like a `'custom'` arg, but for reset signals.
        * `'axi_stream_in'` denotes the argument is an AXI stream input
        interface. This means the important information is what is contained
        in the packets of the axi stream rather than the raw signals.
        It is up to the user to pass a ``custom_source`` that generates
        the relevant axi signals. It's important to note that unpredictable
        things might happen if there is feedback into the AXI customs source
        other than through the AXI stream interface. It is assumed that the
        custom source that drives the AXI stream interface is independent
        of the model or other sources.
        * `'axi_stream_out'` denotes the argument is an AXI stream output
        interface that should be handled as such. This means the data is
        packetised and returned in that form in addition to the raw signals.
        * `'non-signal'` denotes an argument that is not a signal or an
        interface (i.e. an argument that is used during construction only).

        If an argument is an interface type, then a dict of the above can be
        used. That is, each attribute in the interface can be a key in a
        dict that points to a string from the above list.

        ``period`` sets the clock period.

        ``custom_sources`` is a list of tuples as
        ``(myhdl_block, *args, **kwargs)``, which is instantiated at
        simulation or conversion time. ``args`` and ``kwargs`` correspond
        to the arguments and keyword arguments needed to instantiate each
        custom source. ``myhdl_block`` should be a callable block object.

        Any sources that are needed to support the `'custom'` or
        `'custom_reset'` args should be included in this list.

        If ``enforce_convertible_top_level_interfaces`` is set to ``True``
        (the default) an error will be raised if the any of of the arguments
        contains an interface which itself contains a list somewhere. These are
        fine to use inside a design, but if used as the top block, will result
        in a converted top module that has the list signals missing from the
        signature. This is arguably a problem with myhdl but we can check such
        a scenario through Veriutils. As such, in order to test blocks that use
        these features, you need to explicitly set
        ``enforce_convertible_top_level_interfaces`` to ``False``. We only
        enforce the case in which the top level interface is contains a list as
        that is the case that MyHDL fails to error for on conversion.

        ``time_units`` is used to define the units of the ``period`` argument.
        It is also used in cosimulate to create the ``timescale``.
        '''

        # Reset the clock source block count
        global clock_source_block_count
        clock_source_block_count = 0

        valid_arg_types = ('clock', 'init_reset', 'random', 'output',
                           'custom', 'custom_reset', 'axi_stream_out',
                           'axi_stream_in', 'non-signal')

        if period is None:
            self.period = PERIOD
        else:
            self.period = period

        if time_units not in AVAILABLE_TIME_UNITS:
            raise ValueError(
                'Invalid time unit. Please select from: ' +
                ', '.join(AVAILABLE_TIME_UNITS))

        self.time_units = time_units

        self.dut_factory = dut_factory
        self.ref_factory = ref_factory

        if set(args.keys()) != set(arg_types.keys()):
            raise ValueError('Invalid argument or argument type keys: '
                             'The argument dict and the argument type dict '
                             'should have all the same keys.')


        self.elaborated_args = Args(args, arg_types)

        if enforce_convertible_top_level_interfaces:
            # In this case we need to make sure that our interfaces are
            # all acceptable for converting at the top level
            for each in self.elaborated_args:
                if isinstance(each, ObjectInListInInterface):
                    raise ValueError(
                        'Lists in interfaces are explicitly disallowed '
                        'when enforce_convertible_top_level_interfaces is '
                        'set to True. This is because MyHDL will fail '
                        'to convert such interfaces properly, but without '
                        'warning. If the block being tested is intended to '
                        'be used only within a design and not at the top '
                        'level, you can safely set '
                        'enforce_convertible_top_level_interfaces to False to '
                        'bypass this error. The relevant argument is: '
                        '{}'.format(each._basename))

        flattened_types = self.elaborated_args.types
        flattened_signals = self.elaborated_args.objects
        flattened_signal_names = self.elaborated_args.names

        self.elaborated_dut_args = self.elaborated_args.clone_for_dut()

        if 'clock' not in flattened_types:
            raise ValueError('Missing clock: There should be a single '
                             'clock in the argument list.')

        if flattened_types.count('clock') > 1:
            raise ValueError('Multiple clocks: There should be one and only '
                             'one clock in the argument list.')

        if (flattened_types.count('init_reset') +
            flattened_types.count('custom_reset') > 1):

            raise ValueError('Multiple resets: There should be one and only '
                             'one reset in the argument list.')

        self.clock = flattened_signals[flattened_types.index('clock')]
        self.clockgen_factory = (
            clock_source, (self.clock, self.period, self.time_units), {})

        self._use_init_reset = False

        if 'init_reset' in flattened_types:
            self.reset = flattened_signals[
                flattened_types.index('init_reset')]

            self.init_reset_factory = (
                init_reset_source, (self.reset, self.clock), {})
            self._use_init_reset = True

        elif 'custom_reset' in flattened_types:
            self.reset = flattened_signals[
                flattened_types.index('custom_reset')]
            self.init_reset_factory = ()

        else:
            # We need to create a reset to keep dependent HDL blocks happy
            # (though it won't be driven)
            self.reset = ResetSignal(False, active=True, isasync=False)
            self.init_reset_factory = ()


        if custom_sources is None:
            custom_sources = []

        else:
            for n, each_custom_source in enumerate(custom_sources):
                malformed_custom_source = False

                if (not isinstance(each_custom_source[1], (tuple, list))
                    or not isinstance(each_custom_source[2], dict)):

                    raise ValueError(
                        'Malformed custom source: custom source %d. It '
                        'should be (block, arg_list, kwargs_dict)' % (n,))

        self.custom_sources = custom_sources

        # Now sort out the arguments - the outputs should be replicated
        self.ref_args = self.elaborated_args.args
        self.dut_args = self.elaborated_dut_args.args

        # Deal with random values
        # Create the random sources.
        self.random_source_factories = []
        for each_arg, each_dut_arg in zip(self.elaborated_args,
                                          self.elaborated_dut_args):

            if each_arg.type == 'random':
                seed = random.randrange(0, 0x5EEDF00D)
                self.random_source_factories.append(
                    (random_source,
                     (each_arg.object, self.clock, self.reset),
                     {'seed': seed}))

                if dut_factory is not None:
                    self.random_source_factories.append(
                        (random_source,
                         (each_dut_arg.object, self.clock, self.reset),
                         {'seed': seed}))


        # Now create the recorder sinks for every signal
        self.output_recorder_factories = []

        def _add_recorder_sink(arg, output_dict):

            if arg.type == 'non-signal':
                # We don't record non-signals
                return

            handler = lambda val: arg.store_sim_value(output_dict, val)

            val_handler_inst = (
                handler_sink, (arg.object, self.clock, handler), {})

            self.output_recorder_factories.append(val_handler_inst)

        ref_outputs = SimulationOutputs()
        for arg in self.elaborated_args:
            _add_recorder_sink(arg, ref_outputs)

        if dut_factory is not None:
            dut_outputs = SimulationOutputs()
            for arg in self.elaborated_dut_args:
                _add_recorder_sink(arg, dut_outputs)

        else:
            dut_outputs = None

        # Now deal with the AXI interfaces
        ref_axi_stream_in_interfaces = (
            self.elaborated_args.axi_stream_in_interfaces)
        dut_axi_stream_in_interfaces = (
            self.elaborated_dut_args.axi_stream_in_interfaces)

        ref_axi_stream_out_interfaces = (
            self.elaborated_args.axi_stream_out_interfaces)
        dut_axi_stream_out_interfaces = (
            self.elaborated_dut_args.axi_stream_out_interfaces)

        # Create all the relevant AXI blocks
        self.axi_stream_out_ref_bfms = {}
        self.axi_stream_in_ref_bfms = {}
        if dut_factory is not None:
            self.axi_stream_out_dut_bfms = {}

        else:
            self.axi_stream_out_dut_bfms = None

        self.axi_stream_out_bfm_sink_factories = []
        self.axi_stream_out_bfm_sink_interface_names = []

        self.axi_stream_in_bfm_sink_factories = []
        self.axi_stream_in_bfm_sink_interface_names = []
        self.axi_stream_in_ref_interfaces = {}
        self.axi_stream_in_buffer_factories = []

        for each_interface in ref_axi_stream_in_interfaces:
            TREADY_probability = None

            ref_axi_intfc = ref_axi_stream_in_interfaces[each_interface]

            ref_bfm = AxiStreamSlaveBFM()
            self.axi_stream_in_ref_bfms[each_interface] = ref_bfm
            self.axi_stream_in_bfm_sink_factories.append(
                (ref_bfm.model,
                 (self.clock, ref_axi_intfc, TREADY_probability), {}))

            self.axi_stream_in_bfm_sink_interface_names.append(each_interface)
            self.axi_stream_in_ref_interfaces[each_interface] = ref_axi_intfc

            if dut_factory is not None:
                dut_axi_intfc = dut_axi_stream_in_interfaces[each_interface]

                self.axi_stream_in_buffer_factories.append(
                    (axi_stream_buffer,
                     (self.clock, ref_axi_intfc, dut_axi_intfc),
                     {'passive_sink_mode': True}))


        for each_interface in ref_axi_stream_out_interfaces:

            TREADY_probability = 1.0

            ref_axi_intfc = ref_axi_stream_out_interfaces[each_interface]

            ref_bfm = AxiStreamSlaveBFM()
            self.axi_stream_out_ref_bfms[each_interface] = ref_bfm
            self.axi_stream_out_bfm_sink_factories.append(
                (ref_bfm.model,
                 (self.clock, ref_axi_intfc, TREADY_probability), {}))

            self.axi_stream_out_bfm_sink_interface_names.append(each_interface)

            if dut_factory is not None:
                dut_bfm = AxiStreamSlaveBFM()
                dut_axi_intfc = dut_axi_stream_out_interfaces[each_interface]
                self.axi_stream_out_dut_bfms[each_interface] = dut_bfm
                self.axi_stream_out_bfm_sink_factories.append(
                    (dut_bfm.model,
                     (self.clock, dut_axi_intfc, TREADY_probability),
                     {}))


        self.test_factories = [(ref_factory, (), self.ref_args)]

        if dut_factory is not None:
            self.test_factories += [(dut_factory, (), self.dut_args)]

        self._dut_factory = dut_factory

        self._outputs = (dut_outputs, ref_outputs)

        # Note: self.ref_args is args
        self.args = args
        self.arg_types = arg_types

        self._simulator_run = False

    def cosimulate(self, cycles, vcd_name=None):
        '''Co-simulate the device under test and the reference design.

        Return a pair tuple of lists, each corresponding to the recorded
        signals (in the order they were passed) of respectively the
        device under test and the reference design.

        if ``cycles`` is None, then the simulation continues until
        StopSimulation is raised.

        If ``vcd_name`` is not ``None``, a vcd file will be created of the
        waveform.
        '''

        # And also clear the AXI sink BFMs
        if self.axi_stream_out_ref_bfms is not None:
            for bfm in self.axi_stream_out_ref_bfms.values():
                bfm.reset()

        if self.axi_stream_out_dut_bfms is not None:
            for bfm in self.axi_stream_out_dut_bfms.values():
                bfm.reset()

        if self.axi_stream_in_ref_bfms is not None:
            for bfm in self.axi_stream_in_ref_bfms.values():
                bfm.reset()

        for ref_each, dut_each in zip(self.elaborated_args,
                                      self.elaborated_dut_args):

            if not isinstance(ref_each.object, myhdl._Signal._Signal):
                continue

            else:
                dut_each.object._clear()
                ref_each.object._clear()

        @block
        def top():
            random_sources = [
                factory(*args, **kwargs) for factory, args, kwargs in
                self.random_source_factories]
            output_recorders = [
                factory(*args, **kwargs) for factory, args, kwargs in
                self.output_recorder_factories]

            test_instances = []
            for name, (factory, args, kwargs) in zip(
                ('ref', 'dut'), self.test_factories):

                try:
                    test_instances.append(factory(*args, **kwargs))
                except myhdl.BlockError as e:
                    raise myhdl.BlockError(
                        'The %s factory returned an invalid object: %s' %
                        (name, e))

            custom_sources = [
                factory(*args, **kwargs) for factory, args, kwargs in
                self.custom_sources]

            axi_sources = [
                factory(*args, **kwargs) for factory, args, kwargs in
                self.axi_stream_out_bfm_sink_factories]

            axi_sources.extend([
                factory(*args, **kwargs) for factory, args, kwargs in
                self.axi_stream_in_bfm_sink_factories])

            axi_sources.extend([
                factory(*args, **kwargs) for factory, args, kwargs in
                self.axi_stream_in_buffer_factories])

            clockgen = self.clockgen_factory[0](
                *self.clockgen_factory[1], **self.clockgen_factory[2])

            try:
                init_reset = self.init_reset_factory[0](
                    *self.init_reset_factory[1], **self.init_reset_factory[2])
            except IndexError:
                init_reset = []

            return [random_sources, output_recorders, test_instances,
                    custom_sources, axi_sources, [clockgen, init_reset]]

        top_level_block = top()

        if vcd_name is not None:
            traceSignals.name = vcd_name
            trace = True
        else:
            trace = False

        # Generate the appropriate timescale based on the time_units. This is
        # in the form '1ns/1ns' (when time_units is ns).
        timescale = '1' + str(self.time_units) + '/1' + str(self.time_units)

        top_level_block.config_sim(trace=trace, timescale=timescale)

        try:
            if cycles is not None:
                top_level_block.run_sim(duration=cycles*self.period, quiet=1)
            else:
                top_level_block.run_sim(duration=None, quiet=1)

        finally:
            top_level_block.quit_sim()

        self._simulator_run = True

        def axi_signals_from_name(name, output_set):
            object_path = name.split('.')

            this_axi_signals = []
            for each in output_set[object_path[0]]:

                layer = each
                for layer_name in object_path[1:]:
                    layer = layer[layer_name]

                this_axi_signals.append(layer)

            return this_axi_signals

        # We do some munging, so we do it on a copy of the outputs
        outputs = copy.deepcopy(self._outputs)

        # Finally write the AXI outputs as necessary
        for each_axi_interface in self.axi_stream_out_ref_bfms:

            ref_axi_signals = axi_signals_from_name(
                each_axi_interface, outputs[1])
            ref_bfm = self.axi_stream_out_ref_bfms[each_axi_interface]

            outputs[1][each_axi_interface] = AxiStreamOutput({
                'packets': ref_bfm.completed_packets,
                'incomplete_packet': ref_bfm.current_packets})

            if self.axi_stream_out_dut_bfms is not None:
                dut_axi_signals = axi_signals_from_name(
                    each_axi_interface, outputs[0])
                dut_bfm = self.axi_stream_out_dut_bfms[each_axi_interface]

                outputs[0][each_axi_interface] = AxiStreamOutput({
                    'packets': dut_bfm.completed_packets,
                    'incomplete_packet': dut_bfm.current_packets})

        return outputs

    @block
    def dut_convertible_top(
        self, output_path, signal_output_filename='signal_outputs',
        axi_stream_packets_filename_prefix='axi_stream_out'):
        '''Acts as a top-level MyHDL method, implementing a portable,
        convertible version of the SynchronousTest object wrapping the
        device under test.

        The test vector that serves as the stimulus to all the inputs (except
        the clock) is generated by calls to the :meth:`cosimulate` method.
        :meth:`cosimulate` should be run for at least as many cycles as is
        the simulation of :meth:`dut_convertible_top`. If
        cosimulate is run for fewer cycles than :meth:`dut_convertible_top`,
        the result is undefined.
        '''
        if not self._simulator_run:
            raise RuntimeError('The simulator should be run before '
                               'dut_convertible_top')

        if self._dut_factory is None:
            raise RuntimeError('The dut was configured to be None in '
                               'construction, so no meaningful conversion '
                               'can take place.')

        # NOTE I'm not sure if this is the correct thing to do or not,
        # but the signals and interfaces and so on that are used for the
        # conversion are all the reference signals (not the dut signals).
        # This is probably not a problem as they're really only used to define
        # how the conversion should take place (and not actually run at all).
        # It's important only insomuch as it needs to be done consistently.

        clock = self.clock
        reset = self.reset
        ref_outputs = self._outputs[1]

        for each in self.elaborated_dut_args:
            # Sanity check
            if each.type == 'clock':
                assert each.object is self.clock

            if each.type == 'reset':
                assert each.object is self.reset

        dut_args = self.elaborated_dut_args.args

        flattened_ref_outputs = {}
        for each in self.elaborated_args:
            # Only work with signals
            if each.type != 'non-signal':
                flattened_ref_outputs[each.convertible_name] = (
                    each.extract_sim_values(ref_outputs))

        instances = []
        signals_to_record = []

        # Generate all the convertible blocks for handling the signals.
        for each_signal in self.elaborated_dut_args:

            convertible_name = each_signal.convertible_name

            if each_signal.type == 'non-signal':
                continue

            if isinstance(each_signal.object.val, EnumItemType):
                # enums are currently unsupported here
                raise ValueError('enum signals are currently unsupported')

            elif each_signal.type == 'clock':
                instances.append(
                    clock_source(clock, self.period, self.time_units))

            elif each_signal.type == 'init_reset':
                # This should be played back
                drive_list = tuple(flattened_ref_outputs[convertible_name])
                instances.append(lut_signal_driver(
                    reset, drive_list, clock,
                    signal_name=each_signal.name))

            elif each_signal.type == 'output':
                # We need to record it
                signals_to_record.append(each_signal)

            elif each_signal.type == 'custom_reset':
                # This should be played back
                drive_list = tuple(flattened_ref_outputs[convertible_name])
                instances.append(lut_signal_driver(
                    reset, drive_list, clock, signal_name=each_signal.name))

            elif each_signal.type == 'axi_stream_out':
                # We record all the axi signals
                signals_to_record.append(each_signal)

            elif each_signal.type == 'axi_stream_in':
                # We record all the axi signals
                signals_to_record.append(each_signal)

            else:
                # This should be played back too
                drive_list = tuple(flattened_ref_outputs[convertible_name])
                instances.append(lut_signal_driver(
                    each_signal.object, drive_list, clock,
                    signal_name=each_signal.name))

#        # FIXME
#        # The following code should ideally not be necessary. For some reason
#        # the MyHDL conversion fails to identify the interface signals that
#        # are used (perhaps due to the v*_code attribute in the file writer?).
#        # It converts, but the signals are not declared.
#        # The following assigns each interface signal to an individual
#        # written signal. This seems to convert properly, but it's a bit
#        # of a hack.
#        # Basically, everything should work by simply deleting here up to END
#        # below.
#        interface_mapping = {}
#        for each_signal_name in recorded_local_name_list:
#            if each_signal_name in signal_object_lookup:
#
#                if lookup_type[each_signal_name] == 'interface':
#                    interface_name, hierarchy = (
#                        signal_object_lookup[each_signal_name])
#                    # FIXME We only support one level
#                    signal_attr_name = hierarchy[0]
#
#                    # We need to copy the signal so we only drive the
#                    # interface from one place.
#                    copied_signal = copy_signal(signal_dict[each_signal_name])
#                    signal_dict[each_signal_name] = copied_signal
#
#                    interface_mapping.setdefault(
#                        interface_name, {})[signal_attr_name] = (
#                            signal_dict[each_signal_name])
#
#        for each_interface_name in interface_mapping:
#            each_interface = self.args[each_interface_name]
#            each_mapping = interface_mapping[each_interface_name]
#
#            instances.append(deinterfacer(each_interface, each_mapping))
#
        ### END

        # Set up the recording headers
        recorded_list = []
        recorded_list_names = []
        for each_signal in signals_to_record:
            recorded_list.append(each_signal.object)
            recorded_list_names.append(each_signal.recording_header)


        signal_output_file = os.path.join(output_path, signal_output_filename)
        # Setup the output writer and add it to the instances list
        instances.append(file_writer(
            signal_output_file, recorded_list, clock, recorded_list_names))

        axi_stream_in_dut_interfaces = (
            self.elaborated_dut_args.axi_stream_in_interfaces)

        axi_stream_out_dut_interfaces = (
            self.elaborated_dut_args.axi_stream_out_interfaces)

        for axi_interface_name in axi_stream_in_dut_interfaces:

            axi_bfm = self.axi_stream_in_ref_bfms[axi_interface_name]
            axi_interface = axi_stream_in_dut_interfaces[
                axi_interface_name]
            signal_record = axi_bfm.signal_record

            instances.append(
                axi_master_playback(clock, axi_interface, signal_record))

        used_file_writer_names = set()
        for n, axi_interface_name in enumerate(axi_stream_out_dut_interfaces):

            dut_axi_intfc = axi_stream_out_dut_interfaces[axi_interface_name]

            axi_stream_file_writer_filename = os.path.join(
                axi_stream_packets_filename_prefix + '_' + axi_interface_name)

            axi_stream_file_writer_args = [self.clock, dut_axi_intfc]

            base_file_writer_name = (
                str(n) + '_' + axi_interface_name).replace('.', '_')

            this_file_writer_name = base_file_writer_name
            uniqueifier = 0
            while this_file_writer_name in used_file_writer_names:
                this_file_writer_name = (
                    base_file_writer_name + '_' + int(uniqueifier))
                uniqueifier += 1

            used_file_writer_names.add(this_file_writer_name)

            axi_stream_file_writer_args.append(this_file_writer_name)
            axi_stream_file_writer_args.append(
                os.path.join(output_path, axi_stream_file_writer_filename))

            instances.append(
                axi_stream_file_writer(*axi_stream_file_writer_args))

        # Finally, add the device under test
        instances.append(self._dut_factory(**dut_args))

        return instances

def myhdl_cosimulation(cycles, dut_factory, ref_factory, args, arg_types,
                       period=None, custom_sources=None,
                       enforce_convertible_top_level_interfaces=True,
                       vcd_name=None, time_units='ns'):
    '''Run a cosimulation of a pair of MyHDL instances. This is a thin
    wrapper around a :class:`SynchronousTest` object, in which the object
    is created and then the cosimulate method is run, with the ``cycles``
    argument. See the documentation for :class:`SynchronousTest` for the
    definition of all the arguments except ``cycles``.

    What is returned is what is returned from
    :meth:`SynchronousTest.cosimulate`.
    '''
    sim_object = SynchronousTest(
        dut_factory, ref_factory, args, arg_types, period, custom_sources,
        enforce_convertible_top_level_interfaces, time_units=time_units)

    return sim_object.cosimulate(cycles, vcd_name=vcd_name)



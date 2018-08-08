from .hdl_blocks import *
from .axi import AxiStreamSlaveBFM, axi_stream_buffer, axi_master_playback

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

import collections
import random

import inspect

import sys
PY3 = sys.version_info[0]
if PY3:
    string_type = str
else:
    string_type = basestring

__all__ = ['SynchronousTest', 'myhdl_cosimulation']

PERIOD = 10

signal_0 = 10

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

    modifed_name = containing_dict[name]

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

    signal_names = ('TDATA', 'TLAST', 'TKEEP', 'TSTRB')

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

def _expand_to_signal_list(signal_obj, depth=0):
    '''Takes a signal object - either a signal or an interface, and returns
    a list of all the signals therein contained, along with a corresponding
    list of attribute names. If signal_obj is a signal, then the attribute
    name list is empty. Each value in the attribute name list is one more
    layer down in the interface hierarchy.

    Supports one level of interface - it would be easy to extend, but the
    functionality is not currently desired or tested.
    '''
    if depth > 1:
        # recursion limit
        return [], []

    if isinstance(signal_obj, myhdl._Signal._Signal):
        return [signal_obj], []

    elif isinstance(signal_obj, list):
        #already a list
        return signal_obj, []

    else:
        signal_list = []
        attribute_name_list = []

        try:
            for each in signal_obj.__dict__:
                each_signal_list, each_attr_name_list = (
                    _expand_to_signal_list(
                        getattr(signal_obj, each), depth=depth+1))

                if each_signal_list == []:
                    # Not a signal returned, and recursion limit reached.
                    continue

                signal_list += each_signal_list
                attribute_name_list += [(each, each_attr_name_list)]

        except AttributeError as e:
            # A non-signal, non-interface
            return [], []

        return signal_list, attribute_name_list

def _turn_signal_hierarchy_into_name(hierarchy):
    '''A function that recurses through the signal
    hierachy and generates a name from it, putting a dot between
    each level in the hierarchy.
    '''
    this_level_name, next_hierarchy = hierarchy

    if next_hierarchy == []:
        return this_level_name

    else:
        return (this_level_name + '.' +
                _turn_signal_hierarchy_into_name(next_hierarchy))

def _types_from_signal_hierarchy(hierarchy, types):
    '''For every entry in the hierarchy, find the corresponding types.

    This might propagate down the hierarchy from a string, or be a dict.
    '''
    if len(hierarchy) == 0:
        _types = [types]

    else:
        _types = []
        for name, next_hierarchy in hierarchy:
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

    return _types

@block
def single_signal_assigner(input_signal, output_signal):

    @always_comb
    def single_assignment():
        output_signal.next = input_signal

    return single_assignment

@block
def deinterfacer(interface, assignment_dict):

    assigner_blocks = []
    signal_dict = {}
    for attr_name in assignment_dict:
        signal_dict['input_' + attr_name] = getattr(interface, attr_name)
        signal_dict['output_' + attr_name] = assignment_dict[attr_name]

        if isinstance(signal_dict['input_' + attr_name],
                      myhdl._Signal._Signal):

            assigner_blocks.append(
                single_signal_assigner(
                    signal_dict['input_' + attr_name],
                    signal_dict['output_' + attr_name]))

    return assigner_blocks

def _create_flattened_args(args, arg_types):
    # Turn all the interfaces into just another signal in the list

    arg_list = sorted(args.keys())
    non_signal_list = []
    flattened_args = {}
    flattened_arg_types = {}
    lookup_type = {}
    signal_object_lookup = {}
    for each_arg_name in arg_list:

        if arg_types[each_arg_name] == 'non-signal':
            non_signal_list.append(each_arg_name)
            continue
        else:
            each_signal_name = each_arg_name

        each_signal_obj = args[each_signal_name]

        _signal_list, attribute_name_list = (
            _expand_to_signal_list(each_signal_obj))

        hierarchy_types = _types_from_signal_hierarchy(
            attribute_name_list, arg_types[each_signal_name])

        if len(_signal_list) == 1 and len(attribute_name_list) == 0:
            # A normal signal
            flattened_args[each_signal_name] = _signal_list[0]
            flattened_arg_types[each_signal_name] = (
                arg_types[each_signal_name])

        elif len(_signal_list) > 0 and len(attribute_name_list) == 0:
            # The signal list case
            name_idx = 0
            # sig_n is the index in a list with non-signals missing.
            sig_n = 0
            for n, each_signal in enumerate(_signal_list):
                if not isinstance(each_signal, myhdl._Signal._Signal):
                    # ignore non signals
                    continue

                # Get a unique signal name
                while True:
                    sub_signal_name = each_signal_name + str(name_idx)
                    name_idx += 1
                    if sub_signal_name not in arg_list:
                        break

                flattened_args[sub_signal_name] = each_signal
                flattened_arg_types[sub_signal_name] = (
                    arg_types[each_signal_name])
                # The lookup is the list name and the index, and also the
                # index in a list stripped of any non-signals
                signal_object_lookup[sub_signal_name] = (
                    each_signal_name, n, sig_n)
                lookup_type[sub_signal_name] = 'signal_list'

                sig_n += 1

        else:
            # The interface case
            interface_name = each_signal_name

            # The following currently only works with one level of
            # interface hierarchy
            for each_sub_signal, each_interface_lookup, each_type in zip(
                _signal_list, attribute_name_list, hierarchy_types):

                if each_type[1] is None:
                    # Not assigned a type, so we have to ignore it.
                    continue

                # Get a unique signal name
                # Try the obvious name first
                sub_signal_name = (
                    interface_name + '_' + each_interface_lookup[0])
                subname_idx = 0
                while True:
                    if sub_signal_name not in arg_list:
                        break

                    else:
                        sub_signal_name = (
                            interface_name + '_' + each_interface_lookup[0] +
                            str(subname_idx))
                        subname_idx += 1

                flattened_args[sub_signal_name] = each_sub_signal
                # As we said above, we only support one level of
                # hierarchy. This means the type is simply stored in
                # `each_type` as follows.
                flattened_arg_types[sub_signal_name] = (
                    each_type[1][0])

                signal_object_lookup[sub_signal_name] = (
                    each_signal_name, each_interface_lookup)
                lookup_type[sub_signal_name] = 'interface'

    return (non_signal_list, flattened_args, flattened_arg_types,
            signal_object_lookup, lookup_type)

def _signal_from_sigdict_and_name(sigdict, name):

    split_name = name.split('.')
    sig_obj = sigdict[split_name[0]]

    for attr_name in split_name[1:]:
        sig_obj = getattr(sig_obj, attr_name)

    return sig_obj


class SynchronousTest(object):

    def __init__(self, dut_factory, ref_factory, args, arg_types,
                 period=None, custom_sources=None):
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
        '''

        valid_arg_types = ('clock', 'init_reset', 'random', 'output',
                           'custom', 'custom_reset', 'axi_stream_out',
                           'axi_stream_in', 'non-signal')

        if period is None:
            self.period = PERIOD
        else:
            self.period = period

        self.dut_factory = dut_factory
        self.ref_factory = ref_factory

        if set(args.keys()) != set(arg_types.keys()):
            raise ValueError('Invalid argument or argument type keys: '
                             'The argument dict and the argument type dict '
                             'should have all the same keys.')

        flattened_types = []
        flattened_signals = []
        flattened_signal_names = []

        def _arg_checker(signal_collection, types, name_prefix='', depth=0):

            if not isinstance(signal_collection, collections.Mapping):
                # Use the __dict__ attribute of the object
                signal_objs = signal_collection.__dict__
            else:
                signal_objs = signal_collection

            for name in types:
                if len(name_prefix) > 0:
                    resolved_name = name_prefix + '.' + name
                else:
                    resolved_name = name

                if (isinstance(signal_objs[name], myhdl._Signal._Signal) and
                    types[name] not in valid_arg_types):

                    raise ValueError('Invalid argument or argument types:'
                                     ' All the signals in the hierarchy '
                                     'should be one of type: %s (signal %s)' %
                                     (', '.join(valid_arg_types), name))

                elif not isinstance(signal_objs[name], myhdl._Signal._Signal):

                    if types[name] == 'non-signal':
                        # Nothing more to be done
                        continue


                    elif types[name] in valid_arg_types:

                        # This is ok (we can assign a hierarchy to be of
                        # one type
                        flattened_signal_names.append(resolved_name)
                        flattened_types.append(types[name])
                        flattened_signals.append(signal_objs[name])

                    else:
                        try:
                            _arg_checker(
                                signal_objs[name], types[name],
                                name_prefix=resolved_name)
                        except KeyError as e:
                            raise KeyError(
                                'Arg type dict references a non-existant '
                                'signal or signal type: '
                                '%s (failure handling \'%s\')' % (e, name))

                else:
                    flattened_signal_names.append(resolved_name)
                    flattened_types.append(types[name])
                    flattened_signals.append(signal_objs[name])

        _arg_checker(args, arg_types)

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
        self.clockgen_factory = (clock_source, (self.clock, self.period), {})

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
            self.reset = ResetSignal(False, active=True, async=False)
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
        self.ref_args = args

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
                    # Do a non-deep copy. If your code is messing with
                    # some deep mutable types, then it needs rethinking!
                    output_dict[name] = copy.copy(signal_dict[name])

                elif types[name] in valid_arg_types:
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

        self.dut_args = _replicate_signals(self.ref_args, arg_types)

        # Deal with random values
        # Create the random sources.
        self.random_source_factories = []
        for each_signal, each_name, each_type in zip(
            flattened_signals, flattened_signal_names, flattened_types):

            if each_type == 'random':

                seed = random.randrange(0, 0x5EEDF00D)
                self.random_source_factories.append(
                    (random_source,
                     (each_signal, self.clock, self.reset), {'seed': seed}))

                if dut_factory is not None:
                    dut_signal = _signal_from_sigdict_and_name(
                        self.dut_args, each_name)
                    self.random_source_factories.append(
                        (random_source,
                         (dut_signal, self.clock, self.reset),
                         {'seed': seed}))


        # Now create the recorder sinks for every signal
        ref_outputs = {}
        if dut_factory is not None:
            dut_outputs = {}
        else:
            dut_outputs = None

        self.output_recorder_factories = []
        for arg_name in args:

            if arg_types[arg_name] == 'non-signal':
                # We don't record non-signals, so continue to the next arg.
                continue

            else:
                signal = arg_name

            dut_signal = self.dut_args[signal]
            ref_signal = self.ref_args[signal]

            if dut_factory is not None:
                dut_arg_output = []
                dut_recorder = (
                    recorder_sink, (dut_signal, self.clock, dut_arg_output),
                    {})

                dut_outputs[signal] = dut_arg_output
                self.output_recorder_factories.append(dut_recorder)

            ref_arg_output = []
            ref_recorder = (
                recorder_sink, (ref_signal, self.clock, ref_arg_output), {})
            ref_outputs[signal] = ref_arg_output
            self.output_recorder_factories.append(ref_recorder)

        # Now create the axi sinks
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

        for each_type, each_name in zip(
            flattened_types, flattened_signal_names):

            if each_type == 'axi_stream_out':

                TREADY_probability = 1.0

                ref_axi_signal = self.ref_args[each_name]

                ref_bfm = AxiStreamSlaveBFM()
                self.axi_stream_out_ref_bfms[each_name] = ref_bfm
                self.axi_stream_out_bfm_sink_factories.append(
                    (ref_bfm.model,
                     (self.clock, ref_axi_signal, TREADY_probability), {}))

                self.axi_stream_out_bfm_sink_interface_names.append(each_name)

                if dut_factory is not None:
                    dut_bfm = AxiStreamSlaveBFM()
                    dut_axi_signal = self.dut_args[each_name]
                    self.axi_stream_out_dut_bfms[each_name] = dut_bfm
                    self.axi_stream_out_bfm_sink_factories.append(
                        (dut_bfm.model,
                         (self.clock, dut_axi_signal, TREADY_probability),
                         {}))

            elif each_type == 'axi_stream_in':

                TREADY_probability = None

                ref_axi_signal = self.ref_args[each_name]

                ref_bfm = AxiStreamSlaveBFM()
                self.axi_stream_in_ref_bfms[each_name] = ref_bfm
                self.axi_stream_in_bfm_sink_factories.append(
                    (ref_bfm.model,
                     (self.clock, ref_axi_signal, TREADY_probability), {}))

                self.axi_stream_in_bfm_sink_interface_names.append(each_name)
                self.axi_stream_in_ref_interfaces[each_name] = (
                        ref_axi_signal)

                if dut_factory is not None:
                    dut_axi_signal = self.dut_args[each_name]

                    self.axi_stream_in_buffer_factories.append(
                        (axi_stream_buffer,
                         (self.clock, ref_axi_signal, dut_axi_signal),
                         {'passive_sink_mode': True}))

        self.test_factories = [(ref_factory, (), self.ref_args)]

        if dut_factory is not None:
            self.test_factories += [(dut_factory, (), self.dut_args)]

        self._dut_factory = dut_factory

        self.outputs = (dut_outputs, ref_outputs)

        # Note: self.ref_args is args
        self.args = args
        self.arg_types = arg_types

        self._simulator_run = False

    def cosimulate(self, cycles, vcd_name=None, timescale=None):
        '''Co-simulate the device under test and the reference design.

        Return a pair tuple of lists, each corresponding to the recorded
        signals (in the order they were passed) of respectively the
        device under test and the reference design.

        if ``cycles`` is None, then the simulation continues until
        StopSimulation is raised.

        If vcd_name is not None, a vcd file will be created of the waveform.

        If timescale is not None, the simulation will be run under the
        timescale specified.
        '''

        # We initially need to clear all the signals to bring them to
        # a defined initial state.
        (non_signal_list, flattened_args,
         flattened_arg_types, _, _)= (
             _create_flattened_args(self.args, self.arg_types))

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

        for each_signal_obj in flattened_args:

            if isinstance(flattened_args[each_signal_obj], list):
                # Special case the list signal object
                for each_signal in flattened_args[each_signal_obj]:
                    if not isinstance(each_signal, myhdl._Signal._Signal):
                        continue

                    each_signal._clear()
            else:
                flattened_args[each_signal_obj]._clear()

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

        if timescale is not None:
            top_level_block.config_sim(trace=trace, timescale=timescale)
        else:
            top_level_block.config_sim(trace=trace)

        try:
            if cycles is not None:
                top_level_block.run_sim(duration=cycles*self.period, quiet=1)
            else:
                top_level_block.run_sim(duration=None, quiet=1)

        finally:
            top_level_block.quit_sim()

        self._simulator_run = True

        def axi_interface_from_name(name, output_set):
            object_path = name.split('.')
            current_object = output_set

            for level_name in object_path:
                current_object = current_object[level_name]

            return current_object

        # Finally write the AXI outputs as necessary
        # Currently only works for a top level interface (though the
        # code is partially implemented for the more general case)
        for each_axi_interface in self.axi_stream_out_ref_bfms:

            ref_axi_signals = axi_interface_from_name(
                each_axi_interface, self.outputs[1])
            ref_bfm = self.axi_stream_out_ref_bfms[each_axi_interface]

            self.outputs[1][each_axi_interface] = {
                'signals': ref_axi_signals,
                'packets': ref_bfm.completed_packets,
                'incomplete_packet': ref_bfm.current_packet}

            if self.axi_stream_out_dut_bfms is not None:
                dut_axi_signals = axi_interface_from_name(
                    each_axi_interface, self.outputs[0])
                dut_bfm = self.axi_stream_out_dut_bfms[each_axi_interface]

                self.outputs[0][each_axi_interface] = {
                    'signals': dut_axi_signals,
                    'packets': dut_bfm.completed_packets,
                    'incomplete_packet': dut_bfm.current_packet}

        return self.outputs

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
        ref_outputs = self.outputs[1]

        (non_signal_list, flattened_args,
         flattened_arg_types, signal_object_lookup, lookup_type) = (
             _create_flattened_args(self.args, self.arg_types))

        # Convert ref_outputs to be valid with our flattened signal list
        # i.e. convert the interface recordings into just another signal
        flattened_ref_outputs = {}

        def _extract_recorded_sample(recording_sample, hierarchy):
            '''A function that recurses through the a sample recording to
            extract the correct one. It takes as its input a sample recording
            (i.e. the recording at one time instant), and the signal
            hierarchy in the form returned from _expand_to_signal_list.
            '''
            this_level_name, next_hierarchy = hierarchy

            if next_hierarchy == []:
                return recording_sample[this_level_name]

            else:
                return _extract_recorded_sample(
                    recording_sample[this_level_name], next_hierarchy)

        for each_signal_name in flattened_args:

            if isinstance(flattened_args[each_signal_name].val,
                          EnumItemType):
                # enums are currently unsupported here
                raise ValueError('enum signals are currently unsupported')

            if each_signal_name not in signal_object_lookup:
                # A simple signal
                flattened_ref_outputs[each_signal_name] = (
                    ref_outputs[each_signal_name])

            elif lookup_type[each_signal_name] == 'signal_list':
                # a signal list

                # Get the output list and the idx for this particular
                # flattened signal
                arg_sig_list = (
                    ref_outputs[signal_object_lookup[each_signal_name][0]])
                # We use the signal-removed idx (tuple position 2)
                list_idx = signal_object_lookup[each_signal_name][2]

                flattened_ref_outputs[each_signal_name] = [
                    each_sample[list_idx] for each_sample in arg_sig_list]

            elif lookup_type[each_signal_name] == 'interface':
                # An interface
                top_level_name, hierarchy = (
                    signal_object_lookup[each_signal_name])

                if flattened_arg_types[each_signal_name] == 'axi_stream_out':
                    this_ref_output = [
                        _extract_recorded_sample(each_sample, hierarchy) for
                        each_sample in ref_outputs[top_level_name]['signals']]
                else:
                    this_ref_output = [
                        _extract_recorded_sample(each_sample, hierarchy) for
                        each_sample in ref_outputs[top_level_name]]

                flattened_ref_outputs[each_signal_name] = this_ref_output

        flattened_signal_list = sorted(flattened_args.keys())
        instances = []
        output_idx = 0
        input_idx = 0
        recorded_local_name_list = []

        flattened_dut_args = {}

        signal_dict = {}

        # Now we only have signals, we can do the right thing with them...
        for each_signal_name in flattened_signal_list:
            each_signal = flattened_args[each_signal_name]

            if flattened_arg_types[each_signal_name] == 'clock':
                instances.append(clock_source(clock, self.period))
                flattened_dut_args[each_signal_name] = clock

            elif flattened_arg_types[each_signal_name] == 'init_reset':
                # This should be played back
                drive_list = tuple(flattened_ref_outputs[each_signal_name])
                instances.append(lut_signal_driver(
                    reset, drive_list, clock, signal_name=each_signal_name))

                flattened_dut_args[each_signal_name] = reset
                #instances.append(init_reset_source(reset, clock))
                #flattened_dut_args[each_signal_name] = reset

            elif flattened_arg_types[each_signal_name] == 'output':
                # We need to record it
                signal_dict[each_signal_name] = each_signal
                recorded_local_name_list.append(each_signal_name)
                flattened_dut_args[each_signal_name] = (
                    signal_dict[each_signal_name])

            elif flattened_arg_types[each_signal_name] == 'custom_reset':
                # This should be played back
                drive_list = tuple(flattened_ref_outputs[each_signal_name])
                instances.append(lut_signal_driver(
                    reset, drive_list, clock, signal_name=each_signal_name))
                flattened_dut_args[each_signal_name] = reset

            elif flattened_arg_types[each_signal_name] == 'axi_stream_out':
                # We record all the axi signals
                signal_dict[each_signal_name] = each_signal
                recorded_local_name_list.append(each_signal_name)
                flattened_dut_args[each_signal_name] = (
                    signal_dict[each_signal_name])

            elif flattened_arg_types[each_signal_name] == 'axi_stream_in':
                # We record all the axi signals
                signal_dict[each_signal_name] = each_signal
                recorded_local_name_list.append(each_signal_name)
                flattened_dut_args[each_signal_name] = (
                    signal_dict[each_signal_name])

            else:
                # This should be played back too
                drive_list = tuple(flattened_ref_outputs[each_signal_name])
                signal_dict[each_signal_name] = each_signal
                instances.append(lut_signal_driver(
                    signal_dict[each_signal_name], drive_list, clock,
                    signal_name=each_signal_name))

                flattened_dut_args[each_signal_name] = (
                    signal_dict[each_signal_name])

        # FIXME
        # The following code should ideally not be necessary. For some reason
        # the MyHDL conversion fails to identify the interface signals that
        # are used (perhaps due to the v*_code attribute in the file writer?).
        # It converts, but the signals are not declared.
        # The following assigns each interface signal to an individual
        # written signal. This seems to convert properly, but it's a bit
        # of a hack.
        # Basically, everything should work by simply deleting here up to END
        # below.
        interface_mapping = {}
        for each_signal_name in recorded_local_name_list:
            if each_signal_name in signal_object_lookup:

                if lookup_type[each_signal_name] == 'interface':
                    interface_name, hierarchy = (
                        signal_object_lookup[each_signal_name])
                    # FIXME We only support one level
                    signal_attr_name = hierarchy[0]

                    # We need to copy the signal so we only drive the
                    # interface from one place.
                    copied_signal = copy_signal(signal_dict[each_signal_name])
                    signal_dict[each_signal_name] = copied_signal

                    interface_mapping.setdefault(
                        interface_name, {})[signal_attr_name] = (
                            signal_dict[each_signal_name])

        for each_interface_name in interface_mapping:
            each_interface = self.args[each_interface_name]
            each_mapping = interface_mapping[each_interface_name]

            instances.append(deinterfacer(each_interface, each_mapping))

        ### END

        # Set up the recording headers
        recorded_list = []
        recorded_list_names = []
        for each_signal_name in recorded_local_name_list:

            recorded_list.append(signal_dict[each_signal_name])

            if isinstance(signal_dict[each_signal_name].val, intbv):
                if signal_dict[each_signal_name].min < 0:
                    type_str = 'signed'
                else:
                    type_str = 'unsigned'

            elif isinstance(signal_dict[each_signal_name]._init, bool):
                type_str = 'bool'

            if each_signal_name not in signal_object_lookup:
                # A simple signal
                recorded_list_names.append(
                    'simple %s %s' % (type_str, each_signal_name))

            elif lookup_type[each_signal_name] == 'signal_list':

                sig_lookup_vals = signal_object_lookup[each_signal_name]
                header_name = '%s[%d]' % (
                    sig_lookup_vals[0], sig_lookup_vals[1])

                recorded_list_names.append(
                    'list %s %s' % (type_str, header_name))

            elif lookup_type[each_signal_name] == 'interface':
                signal_hierarchy = signal_object_lookup[each_signal_name]
                recorded_list_names.append(
                    'interface %s %s' % (
                        type_str,
                        _turn_signal_hierarchy_into_name(signal_hierarchy)))

        signal_output_file = os.path.join(output_path, signal_output_filename)
        # Setup the output writer and add it to the instances list
        instances.append(file_writer(
            signal_output_file, recorded_list, clock, recorded_list_names))

        # Set up the AXI drivers
        for axi_interface_name in self.axi_stream_in_ref_bfms:

            axi_bfm = self.axi_stream_in_ref_bfms[axi_interface_name]
            axi_interface = self.axi_stream_in_ref_interfaces[
                axi_interface_name]
            packets = axi_bfm.completed_packets_with_validity

            if len(axi_bfm.current_packet) > 0:
                packets.append(axi_bfm.current_packet_with_validity)
                instances.append(
                    axi_master_playback(clock, axi_interface, packets,
                                        incomplete_last_packet=True))
            else:
                instances.append(
                    axi_master_playback(clock, axi_interface, packets))

        # Now set up the AXI stream file writers. There is one file per axi
        # writer.
        for n, (axi_stream_out_bfm_factory, axi_interface_name) in (
            enumerate(zip(self.axi_stream_out_bfm_sink_factories,
                          self.axi_stream_out_bfm_sink_interface_names))):

            axi_stream_file_writer_filename = os.path.join(
                axi_stream_packets_filename_prefix + '_' + axi_interface_name)

            axi_stream_file_writer_args = list(
                axi_stream_out_bfm_factory[1][:-1])
            axi_stream_file_writer_args.append(
                str(n) + '_' + axi_interface_name)
            axi_stream_file_writer_args.append(
                os.path.join(output_path, axi_stream_file_writer_filename))

            instances.append(
                axi_stream_file_writer(*axi_stream_file_writer_args))

        # unflatten dut_args so it can be passed to the dut factory
        dut_args = {}
        for each_arg in flattened_dut_args:
            if each_arg not in signal_object_lookup:
                dut_args[each_arg] = flattened_dut_args[each_arg]

            elif lookup_type[each_arg] == 'signal_list':
                sig_list_name = signal_object_lookup[each_arg][0]
                # Check the signal list isn't already in dut_args before
                # we add it
                if sig_list_name not in dut_args:
                    signal_dict[sig_list_name] = self.args[sig_list_name]
                    dut_args[sig_list_name] = signal_dict[sig_list_name]

            elif lookup_type[each_arg] == 'interface':
                interface_name, _ = signal_object_lookup[each_arg]
                # Check the interface isn't already in dut_args before
                # we add it
                if interface_name not in dut_args:
                    signal_dict[interface_name] = self.args[interface_name]
                    dut_args[interface_name] = signal_dict[interface_name]

        # Add back in the non-signals
        for non_signal in non_signal_list:
            dut_args[non_signal] = self.args[non_signal]

        # Finally, add the device under test
        instances.append(self._dut_factory(**dut_args))

        return instances

def myhdl_cosimulation(cycles, dut_factory, ref_factory, args, arg_types,
                       period=None, custom_sources=None, vcd_name=None,
                       timescale=None):
    '''Run a cosimulation of a pair of MyHDL instances. This is a thin
    wrapper around a :class:`SynchronousTest` object, in which the object
    is created and then the cosimulate method is run, with the ``cycles``
    argument. See the documentation for :class:`SynchronousTest` for the
    definition of all the arguments except ``cycles``.

    What is returned is what is returned from
    :meth:`SynchronousTest.cosimulate`.
    '''
    sim_object = SynchronousTest(dut_factory, ref_factory, args, arg_types,
                                 period, custom_sources)

    return sim_object.cosimulate(
        cycles, vcd_name=vcd_name, timescale=timescale)



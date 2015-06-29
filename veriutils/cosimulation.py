from .hdl_blocks import *
from . import VIVADO_EXECUTABLE

from myhdl import * 

import myhdl
from myhdl.conversion._toVHDL import _shortversion
myhdl_vhdl_package_filename = "pck_myhdl_%s.vhd" % _shortversion

import copy
import os
import tempfile
import re

from string import Template
import shutil
import subprocess
import csv

import collections

try: # pragma: no branch
    # Python 2
    from ConfigParser import RawConfigParser
except ImportError:
    # Python 3
    from configparser import RawConfigParser

import sys
PY3 = sys.version_info[0]
if PY3:
    string_type = str
else:
    string_type = basestring

__all__ = ['SynchronousTest', 'myhdl_cosimulation', 
           'vivado_vhdl_cosimulation', 'vivado_verilog_cosimulation', 
           'VivadoError']

PERIOD = 10

def _file_writer(filename, signal_list, clock, signal_names=None):

    ## Add clock to the signal list
    #signal_list.append(clock)
    ## We also need to add it's name to the name list.
    ## We don't know the name yet, but it's looked up at conversion time.
    ## signal_X is the name assigned in this function (where X is the index
    ## of the signal in the signal_list).
    #signal_names.append('unsigned $signal_%d' % len(signal_names))

    @always(clock.posedge)
    def _dummy_file_writer():
        pass

    vhdl_signal_str_write_list = []
    vhdl_name_str_write_list = []
    
    verilog_signal_str_write_list = []
    verilog_name_str_write_list = []

    for n, each_signal in enumerate(signal_list):
        locals()['signal_' + str(n)] = each_signal
        locals()['signal_' + str(n)].read = True
        
        if signal_names is None:
            vhdl_name_str_write_list.append(
                'write(output_line, string\'(\"$signal_%d\"));' % n)
            verilog_name_str_write_list.append(
                '$$fwrite(output_file, \"$signal_%d\");' % n)
        else:
            # We assign the signal headers from the signal names
            vhdl_name_str_write_list.append(
                'write(output_line, string\'(\"%s\"));' % signal_names[n])
            verilog_name_str_write_list.append(
                '$$fwrite(output_file, \"%s\");' % signal_names[n])


        if len(each_signal) == 1:
            vhdl_signal_str_write_list.append(
                'write(output_line, std_logic($signal_%d));' % n)
        else:
            vhdl_signal_str_write_list.append(
                'write(output_line, std_logic_vector($signal_%d));' % n)

        verilog_signal_str_write_list.append(
            '$$fwrite(output_file, \"%%b\", $signal_%d);' % n)
    
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

    _file_writer.verilog_code = '''
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
    ''' % (filename, verilog_name_str_write, verilog_signal_str_write,)

    _file_writer.vhdl_code = '''
write_to_file: process ($clock) is
    use IEEE.std_logic_textio.all;

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
    ''' % (filename, vhdl_name_str_write, vhdl_signal_str_write,)

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
                    break

                signal_list += each_signal_list
                attribute_name_list += [(each, each_attr_name_list)]
                
        except AttributeError:
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
                _types.append(
                    (name, _types_from_signal_hierarchy(
                        next_hierarchy, types[name])))

    return _types

def _single_signal_assigner(input_signal, output_signal):
    
    @always_comb
    def single_assignment():
        output_signal.next = input_signal
        
    return single_assignment

def _deinterfacer(interface, assignment_dict):
    
    assigner_blocks = []
    for attr_name in assignment_dict:
        locals()['input_' + attr_name] = getattr(interface, attr_name)
        locals()['output_' + attr_name] = assignment_dict[attr_name]
        
        if isinstance(locals()['input_' + attr_name], 
                      myhdl._Signal._Signal):
            
            assigner_blocks.append(
                _single_signal_assigner(
                    locals()['input_' + attr_name],
                    locals()['output_' + attr_name]))
    
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
        else:
            each_signal_name = each_arg_name

        each_signal_obj = args[each_signal_name]

        _signal_list, attribute_name_list = (
            _expand_to_signal_list(each_signal_obj))

        hierarchy_types = _types_from_signal_hierarchy(
            attribute_name_list, arg_types[each_signal_name])

        if len(_signal_list) == 1:
            flattened_args[each_signal_name] = _signal_list[0]
            flattened_arg_types[each_signal_name] = (
                arg_types[each_signal_name])

        elif len(_signal_list) > 0 and len(attribute_name_list) == 0:

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
            name_idx = 0
            # The following currently only works with one level of
            # interface hierarchy
            for each_sub_signal, each_interface_lookup, each_type in zip(
                _signal_list, attribute_name_list, hierarchy_types):

                # Get a unique signal name
                while True:
                    sub_signal_name = each_signal_name + str(name_idx)
                    name_idx += 1                        
                    if sub_signal_name not in arg_list:
                        break

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


class SynchronousTest(object):

    def __init__(self, dut_factory, ref_factory, args, arg_types, 
                 period=PERIOD, custom_sources=None):
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
            * `'non-signal'`

        * The `'clock'` arg is auto-connected to a clock generator. There 
        should be at least one clock object.
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
        * `'non-signal'` denotes an argument that is not a signal or an
        interface (i.e. an argument that is used during construction only).

        If an argument is an interface type, then a dict of the above can be
        used. That is, each attribute in the interface can be a key in a 
        dict that points to a string from the above list.

        ``period`` sets the clock period.

        ``custom_sources`` is a list of sources that are simply appended
        to the simulation instance list. Each custom source should be a valid
        myhdl generator, but no checking is done to make sure. Any sources
        that are needed to support the `'custom'` or `'custom_reset'` args
        should be included in this list.
        '''

        valid_arg_types = ('clock', 'init_reset', 'random', 'output', 
                           'custom', 'custom_reset', 'non-signal')

        self.period = PERIOD
        
        self.dut_factory = dut_factory
        self.ref_factory = ref_factory

        if set(args.keys()) != set(arg_types.keys()):
            raise ValueError('Invalid argument or argument type keys: '
                             'The argument dict and the argument type dict '
                             'should have all the same keys.')

        flattened_types = []
        flattened_signals = []

        def _arg_checker(signal_collection, types, depth=0):

            if not isinstance(signal_collection, collections.Mapping):
                # Use the __dict__ attribute of the object
                signal_objs = signal_collection.__dict__
            else:
                signal_objs = signal_collection

            for name in types:
                if (isinstance(signal_objs[name], myhdl._Signal._Signal) and
                    types[name] not in valid_arg_types):

                    raise ValueError('Invalid argument or argument types:' 
                                     ' All the signals in the hierarchy '
                                     'should be one of type: %s' % 
                                     (', '.join(valid_arg_types),))

                elif not isinstance(signal_objs[name], myhdl._Signal._Signal):

                    if types[name] == 'non-signal':
                        # Nothing more to be done
                        continue


                    elif types[name] in valid_arg_types:

                        # This is ok (we can assign a hierarchy to be of 
                        # one type
                        flattened_types.append(types[name])
                        flattened_signals.append(signal_objs[name])

                    else:
                        try:
                            _arg_checker(signal_objs[name], types[name])
                        except KeyError:
                            raise KeyError('Arg type dict references a '
                                           'non-existant signal')

                else:
                    
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
        self.clockgen = clock_source(self.clock, self.period)

        self._use_init_reset = False

        if 'init_reset' in flattened_types:
            self.reset = flattened_signals[
                flattened_types.index('init_reset')]

            self.init_reset = init_reset_source(self.reset, self.clock)
            self._use_init_reset = True

        elif 'custom_reset' in flattened_types:
            self.reset = flattened_signals[
                flattened_types.index('custom_reset')]
            self.init_reset = ()

        else:
            # We need to create a reset to keep dependent HDL blocks happy
            # (though it won't be driven)
            self.reset = ResetSignal(False, active=True, async=False)
            self.init_reset = ()

        # Deal with random values
        # Create the random sources.
        self.random_sources = [
            random_source(each_signal, self.clock, self.reset) 
            for each_signal, each_type in 
            zip(flattened_signals, flattened_types) if each_type == 'random']

        if custom_sources is None:
            custom_sources = []

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
                if types[name] == 'output':
                    if isinstance(signal_dict[name], list):
                        # Special case signal lists
                        # Only copy the signals
                        output_dict[name] = [
                            copy_signal(each) if 
                            isinstance(each, myhdl._Signal._Signal) else 
                            each for each in signal_dict[name]]
                    else:
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

        # Now create the recorder sinks for every signal
        ref_outputs = {}
        if dut_factory is not None:
            dut_outputs = {}
        else:
            dut_outputs = None

        self.output_recorders = []
        for arg_name in args:

            if arg_types[arg_name] == 'non-signal':
                # We don't record non-signals, so continue to the next arg.
                continue

            else:
                signal = arg_name

            dut_signal = self.dut_args[signal]
            ref_signal = self.ref_args[signal]

            if dut_factory is not None:
                dut_recorder, dut_arg_output = recorder_sink(
                    dut_signal, self.clock)

                dut_outputs[signal] = dut_arg_output
                self.output_recorders.append(dut_recorder)

            ref_recorder, ref_arg_output = recorder_sink(
                ref_signal, self.clock)
            ref_outputs[signal] = ref_arg_output
            self.output_recorders.append(ref_recorder)
            

        ref_instance = ref_factory(**self.ref_args)
        if ref_instance is None:
            raise ValueError('The ref factory returned a None '
                             'object, not an instance')

        self.test_instances = [ref_instance]

        if dut_factory is not None:
            dut_instance = dut_factory(**self.dut_args)        
            if dut_instance is None:
                raise ValueError('The dut factory returned a None '
                                 'object, not an instance')
            
            self.test_instances += [dut_instance]

        self._dut_factory = dut_factory

        self.outputs = (dut_outputs, ref_outputs)
        self.args = args
        self.arg_types = arg_types

        self._simulator_run = False

    def cosimulate(self, cycles):
        '''Co-simulate the device under test and the reference design.

        Return a pair tuple of lists, each corresponding to the recorded
        signals (in the order they were passed) of respectively the 
        device under test and the reference design.
        '''

        # We initially need to clear all the signals to bring them to
        # a defined initial state.
        (non_signal_list, flattened_args, 
         flattened_arg_types, _, _)= (
             _create_flattened_args(self.args, self.arg_types))

        for each_signal_obj in flattened_args:

            if isinstance(flattened_args[each_signal_obj], list):
                # Special case the list signal object
                for each_signal in flattened_args[each_signal_obj]:
                    if not isinstance(each_signal, myhdl._Signal._Signal):
                        continue

                    each_signal._clear()
            else:
                flattened_args[each_signal_obj]._clear()

        sim = Simulation(self.random_sources + self.output_recorders + 
                         self.test_instances + self.custom_sources + 
                         [self.clockgen, self.init_reset])

        sim.run(duration=cycles*self.period, quiet=1)

        sim._finalize()

        self._simulator_run = True
        return self.outputs


    def dut_convertible_top(self, signal_output_file):
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
            hierachy in the form returned from _expand_to_signal_list.
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

        # Now we only have signals, we can do the right thing with them...
        for each_signal_name in flattened_signal_list:
            each_signal = flattened_args[each_signal_name]

            if flattened_arg_types[each_signal_name] == 'clock':
                instances.append(clock_source(clock, self.period))
                flattened_dut_args[each_signal_name] = clock

            elif flattened_arg_types[each_signal_name] == 'init_reset':
                # This should be played back                
                drive_list = tuple(flattened_ref_outputs[each_signal_name])
                instances.append(lut_signal_driver(reset, drive_list, clock))
                flattened_dut_args[each_signal_name] = reset
                #instances.append(init_reset_source(reset, clock))
                #flattened_dut_args[each_signal_name] = reset

            elif flattened_arg_types[each_signal_name] == 'output':
                # We need to record it
                locals()[each_signal_name] = each_signal
                recorded_local_name_list.append(each_signal_name)
                flattened_dut_args[each_signal_name] = (
                    locals()[each_signal_name])

            elif flattened_arg_types[each_signal_name] == 'custom_reset':
                # This should be played back                
                drive_list = tuple(flattened_ref_outputs[each_signal_name])
                instances.append(lut_signal_driver(reset, drive_list, clock))
                flattened_dut_args[each_signal_name] = reset

            else:
                # This should be played back too
                drive_list = tuple(flattened_ref_outputs[each_signal_name])
                locals()[each_signal_name] = each_signal
                instances.append(lut_signal_driver(
                    locals()[each_signal_name], drive_list, clock))

                flattened_dut_args[each_signal_name] = (
                    locals()[each_signal_name])

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
                    copied_signal = copy_signal(locals()[each_signal_name])
                    locals()[each_signal_name] = copied_signal

                    interface_mapping.setdefault(
                        interface_name, {})[signal_attr_name] = (
                            locals()[each_signal_name])

        for each_interface_name in interface_mapping:
            each_interface = self.args[each_interface_name]
            each_mapping = interface_mapping[each_interface_name]

            instances.append(_deinterfacer(each_interface, each_mapping))

        ### END

        # Set up the recording headers
        recorded_list = []
        recorded_list_names = []
        for each_signal_name in recorded_local_name_list:

            recorded_list.append(locals()[each_signal_name])

            if isinstance(locals()[each_signal_name].val, intbv):
                if locals()[each_signal_name].min < 0:
                    type_str = 'signed'
                else:
                    type_str = 'unsigned'

            elif isinstance(locals()[each_signal_name]._init, bool):
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

        # Setup the output writer and add it to the instances list
        instances.append(_file_writer(
            signal_output_file, recorded_list, clock, recorded_list_names))


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
                    locals()[sig_list_name] = self.args[sig_list_name]
                    dut_args[sig_list_name] = locals()[sig_list_name]

            elif lookup_type[each_arg] == 'interface':
                interface_name, _ = signal_object_lookup[each_arg]
                # Check the interface isn't already in dut_args before
                # we add it
                if interface_name not in dut_args:
                    locals()[interface_name] = self.args[interface_name]
                    dut_args[interface_name] = locals()[interface_name]

        # Add back in the non-signals
        for non_signal in non_signal_list:
            dut_args[non_signal] = self.args[non_signal]

        # Finally, add the device under test
        instances.append(self._dut_factory(**dut_args))

        return instances

def myhdl_cosimulation(cycles, dut_factory, ref_factory, args, arg_types, 
                       period=PERIOD, custom_sources=None):
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

    return sim_object.cosimulate(cycles)

class VivadoError(RuntimeError):
    pass

def _vivado_generic_cosimulation(
    target_language, cycles, dut_factory, ref_factory, args, 
    arg_types, period, custom_sources, keep_temp_files, config_file,
    template_path_prefix):

    if VIVADO_EXECUTABLE is None:
        raise EnvironmentError('Vivado executable not in path')
    
    config = RawConfigParser()
    config.read(config_file)

    sim_object = SynchronousTest(dut_factory, ref_factory, args, arg_types, 
                                 period, custom_sources)

    # Two cycles are lost in the vivado simulation - one for the propagation
    # delay between reading and writing, and one because of differences in
    # the time definitions? Fence post issue?
    #
    # Is adding two to the number of cycles the right thing to do?
    _cycles = cycles + 2

    # We need to create the test data
    sim_object.cosimulate(cycles)

    tmp_dir = tempfile.mkdtemp()
    try:
        project_name = 'tmp_project'
        project_path = os.path.join(tmp_dir, project_name)

        time = period * _cycles

        try:
            ip_dependencies = dut_factory.ip_dependencies
        except AttributeError:
            ip_dependencies = ()

        xci_file_list = [
            config.get('IP paths', each_ip) for each_ip in ip_dependencies]
        
        for each_xci_file in xci_file_list:
            # The files should all now exist
            if not os.path.exists(each_xci_file):
                raise EnvironmentError('An expected xci IP file is missing: '
                                       '%s' % (each_xci_file))

        vhdl_files = []
        verilog_files = []
        ip_additional_hdl_files = []

        for each_ip in ip_dependencies:
            if config.has_option('IP additional files', each_ip):
                ip_additional_hdl_files += [
                    each.strip() for each in 
                    config.get('IP additional files', each_ip).split()]
                
        if target_language == 'VHDL':
            try:
                vhdl_dependencies = list(dut_factory.vhdl_dependencies)
            except AttributeError:
                vhdl_dependencies = []

            vhdl_dut_files = [
                os.path.join(tmp_dir, 'dut_convertible_top.vhd'),
                os.path.join(tmp_dir, myhdl_vhdl_package_filename)]

            vhdl_files += vhdl_dependencies + vhdl_dut_files

            # Generate the output VHDL files
            toVHDL.name = None
            toVHDL.directory = tmp_dir

            signal_output_filename = os.path.join(tmp_dir, 'signal_outputs')
            toVHDL(sim_object.dut_convertible_top, signal_output_filename)

        elif target_language == 'Verilog':
            try:
                verilog_dependencies = list(dut_factory.verilog_dependencies)
            except AttributeError:
                verilog_dependencies = []

            verilog_dut_files = [
                os.path.join(tmp_dir, 'dut_convertible_top.v'),]

            verilog_files += verilog_dependencies + verilog_dut_files

            # Generate the output Verilog files
            toVerilog.name = None
            toVerilog.directory = tmp_dir

            signal_output_filename = os.path.join(tmp_dir, 'signal_outputs')
            toVerilog(sim_object.dut_convertible_top, signal_output_filename)

        else:
            raise ValueError('Target language must be \'Verilog\' or '
                             '\'VHDL\'')

        for each_hdl_file in (vhdl_files + verilog_files + 
                              ip_additional_hdl_files):
            # The files should all now exist
            if not os.path.exists(each_hdl_file):
                raise EnvironmentError(
                    'An expected HDL file is missing: %s'
                    % (each_hdl_file))

        xci_files_string = ' '.join(xci_file_list)
        vhdl_files_string = ' '.join(vhdl_files)
        verilog_files_string = ' '.join(verilog_files)
        ip_additional_hdl_files_string = ' '.join(ip_additional_hdl_files)

        template_substitutions = {
            'target_language': target_language,
            'part': config.get('General', 'part'),
            'project_name': project_name,
            'project_path': project_path,
            'time': time,
            'xci_files': xci_files_string,
            'vhdl_files': vhdl_files_string,
            'verilog_files': verilog_files_string,
            'ip_additional_hdl_files': ip_additional_hdl_files_string}

        template_file_path = os.path.abspath(
            os.path.join(template_path_prefix, 
                         config.get('tcl template paths', 'simulate')))

        with open(template_file_path, 'r') as template_file:
            template_string = template_file.read()

        simulate_template = Template(template_string)
        simulate_script = simulate_template.safe_substitute(
            template_substitutions)

        simulate_script_filename = os.path.join(
            tmp_dir, 'simulate_script.tcl')

        with open(simulate_script_filename, 'w') as simulate_script_file:
            simulate_script_file.write(simulate_script)

        vivado_process = subprocess.Popen(
            [VIVADO_EXECUTABLE, '-nolog', '-nojournal', '-mode', 'batch', 
             '-source', simulate_script_filename], stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        out, err = vivado_process.communicate()

        if err != '':
            if target_language == 'VHDL':
                xvhdl_log_filename = os.path.join(
                    tmp_dir, 'tmp_project', 'tmp_project.sim', 'sim_1', 
                    'behav', 'xvhdl.log')

                if xvhdl_log_filename in err:
                    with open(xvhdl_log_filename, 'r') as log_file:
                        err += '\n'
                        err += 'xvhdl.log:\n'
                        err += log_file.read()

                raise VivadoError(
                    'Error running the Vivado VHDL simulator:\n%s' % err)

            elif target_language == 'Verilog':
                xvhdl_log_filename = os.path.join(
                    tmp_dir, 'tmp_project', 'tmp_project.sim', 'sim_1', 
                    'behav', 'xvlog.log')

                if xvhdl_log_filename in err:
                    with open(xvhdl_log_filename, 'r') as log_file:
                        err += '\n'
                        err += 'xvlog.log:\n'
                        err += log_file.read()

                raise VivadoError(
                    'Error running the Vivado Verilog simulator:\n%s' % err)

        with open(signal_output_filename, 'r') as signal_output_file:
            signal_reader = csv.DictReader(signal_output_file, delimiter=',')

            vivado_signals = [row for row in signal_reader]

        # Most of the dut outputs will be the same as ref, we then overwrite
        # the others from the written file.
        dut_outputs = copy.copy(sim_object.outputs[1])
        ref_outputs = sim_object.outputs[1]

        vivado_signal_keys = vivado_signals[0].keys()

        # Rearrange the output signals into the correct form
        _vivado_signals = {key: [] for key in vivado_signals[0].keys()}

        for each_row in vivado_signals:
            for each_key in vivado_signal_keys:
                _vivado_signals[each_key].append(each_row[each_key])

        vivado_signals = _vivado_signals

        interface_outputs = {}
        siglist_outputs = {}
        for each_signal_name_str in vivado_signals:

            each_dut_outputs = []

            sig_container, signal_type, each_signal = (
                each_signal_name_str.split(' '))

            for dut_str_value in vivado_signals[each_signal_name_str]:
                try:
                    if signal_type == 'bool':
                        each_value = bool(int(dut_str_value))
                    else:
                        # We assume an intbv
                        _each_value = (
                            intbv(dut_str_value)[len(dut_str_value):])

                        if signal_type =='signed':
                            each_value = _each_value.signed()
                        else:
                            each_value = _each_value
                    
                except ValueError:
                    # Probably an undefined.
                    each_value = None
                    
                each_dut_outputs.append(each_value)
            
            # add each per-signal list into a data structure that
            # can be easily turned into the correct output when it is not
            # possible to add it directly.
            if sig_container == 'interface':
                output_name_list = each_signal.split('.')

                # We have an interface, so group the recorded signals 
                # of the interface together.

                # FIXME Only one level of interface supported
                interface_outputs.setdefault(
                    output_name_list[0], {})[output_name_list[1]] = (
                        each_dut_outputs)

            elif sig_container == 'list':
                # We have a list                
                parsed_header = re.search(
                    '(?P<list_name>.*)\[(?P<index>.*)\]', each_signal)

                siglist_name = parsed_header.group('list_name')
                siglist_index = int(parsed_header.group('index'))

                siglist_outputs.setdefault(
                    siglist_name, {})[siglist_index] = each_dut_outputs

            else:
                # We have a normal signal
                dut_outputs[each_signal] = each_dut_outputs

        # Now convert the data structures into suitable outputs.

        for each_siglist in siglist_outputs:

            # Order the values by the siglist_index
            ordered_siglist_output = collections.OrderedDict(sorted(
                siglist_outputs[each_siglist].items(), key=lambda t: t[0]))

            new_dut_output = []

            for each_list_out in zip(*ordered_siglist_output.values()):
                new_dut_output.append(list(each_list_out))

        for each_interface in interface_outputs:

            attr_names = interface_outputs[each_interface].keys()

            reordered_interface_outputs =  zip(
                *(interface_outputs[each_interface][key] for 
                  key in attr_names))

            # We need to write the interface values to dut_outputs, but
            # taking the values from ref_outputs if the interface signal was
            # not an output.
            new_dut_output = []
            for ref_output, simulated_output in zip(
                dut_outputs[each_interface], reordered_interface_outputs):

                new_interface_out = ref_output.copy()
                new_interface_out.update(
                    dict(zip(attr_names, simulated_output)))

                new_dut_output.append(new_interface_out)

            dut_outputs[each_interface] = new_dut_output

        for each_signal in ref_outputs:
            # Now only output the correct number of cycles
            ref_outputs[each_signal] = ref_outputs[each_signal][:cycles]
            dut_outputs[each_signal] = dut_outputs[each_signal][:cycles]
    
    finally:

        if not keep_temp_files:
            shutil.rmtree(tmp_dir)
        else:
            print('As requested, the temporary files have not been deleted.'
                  '\nThey can be found in %s.' % (tmp_dir,))

    return dut_outputs, ref_outputs


def vivado_vhdl_cosimulation(
    cycles, dut_factory, ref_factory, args, arg_types, 
    period=PERIOD, custom_sources=None, keep_temp_files=False, 
    config_file='veriutils.cfg', template_path_prefix=''):
    '''Run a cosimulation in which the device under test is simulated inside
    Vivado, using VHDL as the intermediate language.

    This function has exactly the same interface as myhdl_cosimulation.

    The outputs should be identical to from myhdl_cosimulation except for
    one important caveat: until values are initialised explicitly, they 
    are recorded as undefined. Undefined values are set to None in the output.

    This is particularly noticeable in the case when an asynchronous reset
    is used. Care should be taken to handle the outputs appropriately.

    By default, all the temporary files are cleaned up after use. This 
    behaviour can be turned off by settings ``keep_temp_files`` to ``True``.
    '''

    # Before we mess with toVHDL, remember what it was originally.
    toVHDL_name_state = toVHDL.name
    toVHDL_dir_state = toVHDL.directory
    
    # We now need to make sure we clean up after ourselves.
    try:
        target_language = 'VHDL'

        dut_outputs, ref_outputs = _vivado_generic_cosimulation(
            target_language, cycles, dut_factory, ref_factory, args, 
            arg_types, period, custom_sources, keep_temp_files,
            config_file, template_path_prefix)

    finally:
        # Undo the changes to toVHDL
        toVHDL.name = toVHDL_name_state
        toVHDL.directory = toVHDL_dir_state

    return dut_outputs, ref_outputs

def vivado_verilog_cosimulation(
    cycles, dut_factory, ref_factory, args, arg_types, 
    period=PERIOD, custom_sources=None, keep_temp_files=False, 
    config_file='veriutils.cfg', template_path_prefix=''):
    '''Run a cosimulation in which the device under test is simulated inside
    Vivado, using Verilog as the intermediate language.

    This function has exactly the same interface as myhdl_cosimulation.

    The outputs should be identical to from myhdl_cosimulation except for
    one important caveat: until values are initialised explicitly, they 
    are recorded as undefined. Undefined values are set to None in the output.

    This is particularly noticeable in the case when an asynchronous reset
    is used. Care should be taken to handle the outputs appropriately.

    By default, all the temporary files are cleaned up after use. This 
    behaviour can be turned off by settings ``keep_temp_files`` to ``True``.
    '''

    # Before we mess with toVerilog, remember what it was originally.
    toVerilog_name_state = toVerilog.name
    toVerilog_dir_state = toVerilog.directory
    
    # We now need to make sure we clean up after ourselves.
    try:
        target_language = 'Verilog'

        dut_outputs, ref_outputs = _vivado_generic_cosimulation(
            target_language, cycles, dut_factory, ref_factory, args, 
            arg_types, period, custom_sources, keep_temp_files,
            config_file, template_path_prefix)

    finally:
        # Undo the changes to toVHDL
        toVerilog.name = toVerilog_name_state
        toVerilog.directory = toVerilog_dir_state

    return dut_outputs, ref_outputs


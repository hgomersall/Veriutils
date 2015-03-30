from .hdl_blocks import *
from . import VIVADO_EXECUTABLE

from myhdl import * 

import myhdl
from myhdl.conversion._toVHDL import _shortversion
myhdl_vhdl_package_filename = "pck_myhdl_%s.vhd" % _shortversion

import copy
import os
import tempfile

from string import Template
import shutil
import subprocess
import csv

try: # pragma: no branch
    # Python 2
    from ConfigParser import RawConfigParser
except ImportError:
    # Python 3
    from configparser import RawConfigParser


__all__ = ['SynchronousTest', 'myhdl_cosimulation', 'vivado_cosimulation']

PERIOD = 10

def _file_writer(filename, signal_list, clock, signal_names=None):

    # Add clock to the signal list
    signal_list.append(clock)
    # We also need to add it's name to the name list.
    # We don't know the name yet, but it's looked up at conversion time.
    # signal_X is the name assigned in this function (where X is the index
    # of the signal in the signal_list).
    signal_names.append('unsigned $signal_%d' % len(signal_names))

    @always(clock.posedge)
    def _dummy_file_writer():
        pass

    signal_str_write_list = []
    name_str_write_list = []
    for n, each_signal in enumerate(signal_list):
        locals()['signal_' + str(n)] = each_signal
        locals()['signal_' + str(n)].read = True
        
        if signal_names is None:
            name_str_write_list.append(
                'write(output_line, string\'(\"$signal_%d\"));' % n)
        else:
            # We assign the signal headers from the signal names
            name_str_write_list.append(
                'write(output_line, string\'(\"%s\"));' % signal_names[n])

        if len(each_signal) == 1:
            signal_str_write_list.append(
                'write(output_line, std_logic($signal_%d));' % n)
        else:
            signal_str_write_list.append(
                'write(output_line, std_logic_vector($signal_%d));' % n)
    
    name_indent = ' ' * 12
    name_str_write = (
        ('\n%swrite(output_line, string\'(\",\"));\n%s' % 
         (name_indent, name_indent))
        .join(name_str_write_list))

    signal_indent = ' ' * 8
    signal_str_write = (
        ('\n%swrite(output_line, string\'(\",\"));\n%s' % 
         (signal_indent, signal_indent))
        .join(signal_str_write_list))

    _file_writer.vhdl_code = '''
write_to_file: process (clock) is
    use IEEE.std_logic_textio.all;

    file output_file : TEXT open WRITE_MODE is "%s";
    variable output_line : LINE;
    variable first_line_to_print : boolean := true;
begin
    if rising_edge(clock) then
        if first_line_to_print then
            %s
            writeLine(output_file, output_line);
            first_line_to_print := false;
        end if;
        %s
        writeline(output_file, output_line);
    end if;
end process write_to_file;
    ''' % (filename, name_str_write, signal_str_write,)

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

    else:
        signal_list = []
        attribute_name_list = []
        for each in signal_obj.__dict__:
            each_signal_list, each_attr_name_list = _expand_to_signal_list(
                getattr(signal_obj, each), depth=depth+1)

            if each_signal_list == []:
                # Not a signal returned, and recursion limit reached.
                break

            signal_list += each_signal_list
            attribute_name_list += [(each, each_attr_name_list)]

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

def _single_signal_assigner(input_signal, output_signal):
    
    @always_comb
    def single_assignment():
        output_signal.next = input_signal
        
    return single_assignment

def _deinterfacer(interface, assignment_dict):
    
    assigner_blocks = []
    for attr_name in interface.__dict__:
        locals()['input_' + attr_name] = getattr(interface, attr_name)
        locals()['output_' + attr_name] = assignment_dict[attr_name]
        
        if isinstance(locals()['input_' + attr_name], 
                      myhdl._Signal._Signal):
            
            assigner_blocks.append(
                _single_signal_assigner(
                    locals()['input_' + attr_name],
                    locals()['output_' + attr_name]))
    
    return assigner_blocks


class SynchronousTest(object):

    def __init__(self, dut_factory, ref_factory, args, arg_types, 
                 period=PERIOD, custom_sources=None):
        '''Construct a synchronous test case for the pair of factories
        given by `dut_factory` and `ref_factory`. Each factory is constructed
        with the provided args (which probably corresponds to a signal list).

        if `ref_factory` is None, then it is simply not used

        arg_types specifies how each arg should be handled. It is a dict to
        a valid type string. The supported type strings are: 
            * `'clock'`
            * `'init_reset'`
            * `'random'`
            * `'output'`
            * `'custom'`
            * `'custom_reset'`

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

        ``period`` sets the clock period.

        ``custom_sources`` is a list of sources that are simply appended
        to the simulation instance list. Each custom source should be a valid
        myhdl generator, but no checking is done to make sure. Any sources
        that are needed to support the `'custom'` or `'custom_reset'` args
        should be included in this list.
        '''

        valid_arg_types = ('clock', 'init_reset', 'random', 'output', 
                           'custom', 'custom_reset')

        self.period = PERIOD
        
        self.dut_factory = dut_factory
        self.ref_factory = ref_factory

        if set(args.keys()) != set(arg_types.keys()):
            raise ValueError('Invalid argument or argument type keys: '
                             'The argument dict and the argument type dict '
                             'should have all the same keys.')

        if not set(arg_types.values()).issubset(set(valid_arg_types)):
            raise ValueError('Invalid argument or argument types: '
                             'The argument type dict should only contain '
                             'valid argument types')

        if 'clock' not in arg_types.values():
            raise ValueError('Missing clock: There should be a single '
                             'clock in the argument list.')

        if arg_types.values().count('clock') > 1:
            raise ValueError('Multiple clocks: There should be one and only '
                             'one clock in the argument list.')

        if ('init_reset' not in arg_types.values() and
            'custom_reset' not in arg_types.values()):
            raise ValueError('Missing reset: There should be a single '
                             'reset in the argument list.')

        if (arg_types.values().count('init_reset') + 
            arg_types.values().count('custom_reset') > 1):

            raise ValueError('Multiple resets: There should be one and only '
                             'one reset in the argument list.')


        self.clock = args[arg_types.keys()[arg_types.values().index('clock')]]
        self.clockgen = clock_source(self.clock, self.period)

        self._use_init_reset = False

        if 'init_reset' in arg_types.values():
            self.reset = args[arg_types.keys()[
                arg_types.values().index('init_reset')]]

            self.init_reset = init_reset_source(self.reset, self.clock)
            self._use_init_reset = True

        else:
            # Assume a custom reset
            self.reset = args[arg_types.keys()[
                arg_types.values().index('custom_reset')]]
            self.init_reset = ()

        # Deal with random values
        # Get the indices first
        random_args = [
            key for key in arg_types if arg_types[key] == 'random']

        # Now create the random sources.
        self.random_sources = [
            random_source(args[arg], self.clock, self.reset)
            for arg in random_args]

        if custom_sources is None:
            custom_sources = []

        self.custom_sources = custom_sources

        # Now sort out the arguments - the outputs should be replicated
        self.dut_args = copy.copy(args)
        self.ref_args = args

        output_args = [
            key for key in arg_types if arg_types[key] == 'output']

        for output_arg in output_args:
            self.dut_args[output_arg] = copy_signal(args[output_arg])

        # Now create the recorder sinks for every signal
        ref_outputs = {}
        if dut_factory is not None:
            dut_outputs = {}
        else:
            dut_outputs = None

        self.output_recorders = []
        for signal in args:
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
        sim = Simulation(self.random_sources + self.output_recorders + 
                         self.test_instances + self.custom_sources + 
                         [self.clockgen, self.init_reset])

        sim.run(duration=cycles*self.period, quiet=1)

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

        clock = self.clock
        reset = self.reset
        ref_outputs = self.outputs[1]

        signal_list = sorted(self.args.keys())

        # Turn all the interfaces into just another signal in the list
        flattened_args = {}
        flattened_arg_types = {}
        interface_lookup = {}
        for each_signal_name in signal_list:
            each_signal_obj = self.args[each_signal_name]

            _signal_list, attribute_name_list = (
                _expand_to_signal_list(each_signal_obj))

            if len(_signal_list) == 1:
                flattened_args[each_signal_name] = _signal_list[0]
                flattened_arg_types[each_signal_name] = (
                    self.arg_types[each_signal_name])
            else:
                n = 0
                for each_sub_signal, each_interface_lookup in zip(
                    _signal_list, attribute_name_list):

                    # Get a unique signal name
                    while True:
                        sub_signal_name = each_signal_name + str(n)
                        n += 1                        
                        if sub_signal_name not in signal_list:
                            break

                    flattened_args[sub_signal_name] = each_sub_signal
                    # The type of the sub signal should be the same as
                    # the interface type
                    flattened_arg_types[sub_signal_name] = (
                        self.arg_types[each_signal_name])

                    interface_lookup[sub_signal_name] = (
                        each_signal_name, each_interface_lookup)

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

            if each_signal_name not in interface_lookup:
                # A simple signal
                flattened_ref_outputs[each_signal_name] = (
                    ref_outputs[each_signal_name])

            else:
                # An interface
                top_level_name, hierarchy = (
                    interface_lookup[each_signal_name])

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
        # the MyHDL conversion fails to identify the interface signals are
        # used (perhaps due to the vhdl_code attribute in the file writer?).
        # It converts, but the signals are not declared.
        # The following assigns each interface signal to an individual 
        # written signal. This seems to convert properly, but it's a bit
        # of a hack.
        # Basically, everything should work by simply deleting here up to END
        # below.
        interface_mapping = {}
        for each_signal_name in recorded_local_name_list:
            if each_signal_name in interface_lookup:
                
                interface_name, hierarchy = interface_lookup[each_signal_name]
                # FIXME We only support one level
                signal_attr_name = hierarchy[0]

                # We need to copy the signal so we only drive the interface
                # from one place.
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

        recorded_list = []
        recorded_list_names = []
        for each_signal_name in recorded_local_name_list:

            recorded_list.append(locals()[each_signal_name])

            if isinstance(locals()[each_signal_name].val, intbv):
                if locals()[each_signal_name].min < 0:
                    type_str = 'signed'
                else:
                    type_str = 'unsigned'

            elif isinstance(locals()[each_signal_name].val, bool):
                type_str = 'bool'

            if each_signal_name not in interface_lookup:
                # A simple signal
                recorded_list_names.append(
                    '%s %s' % (type_str, each_signal_name))

            else:
                signal_hierarchy = interface_lookup[each_signal_name]
                recorded_list_names.append(
                    '%s %s' % (
                        type_str, 
                        _turn_signal_hierarchy_into_name(signal_hierarchy)))

        # Setup the output writer and add it to the instances list
        instances.append(_file_writer(
            signal_output_file, recorded_list, clock, recorded_list_names))


        # unflatten dut_args so it can be passed to the dut factory
        dut_args = {}
        for each_arg in flattened_dut_args:
            if each_arg not in interface_lookup:
                dut_args[each_arg] = flattened_dut_args[each_arg]

            else:
                interface_name, _ = interface_lookup[each_arg]
                # Check the interface isn't already in dut_args before
                # we add it
                if interface_name not in dut_args:
                    locals()[interface_name] = self.args[interface_name]
                    dut_args[interface_name] = locals()[interface_name]

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


def vivado_cosimulation(cycles, dut_factory, ref_factory, args, arg_types, 
                        period=PERIOD, custom_sources=None):
    '''Run a cosimulation in which the device under test is simulated inside
    Vivado.

    This function has exactly the same interface as myhdl_cosimulation.

    The outputs should be identical to from myhdl_cosimulation except for
    one important caveat: until values are initialised explicitly, they 
    are recorded as undefined. Undefined values are set to None in the output.

    This is particularly noticeable in the case when an asynchronous reset
    is used. Care should be taken to handle the outputs appropriately.
    '''

    if VIVADO_EXECUTABLE is None:
        raise EnvironmentError('Vivado executable not in path')

    sim_object = SynchronousTest(dut_factory, ref_factory, args, arg_types, 
                                 period, custom_sources)

    # Two cycles are lost in the vivado simulation - one for the propagation
    # delay between reading and writing, and one because of differences in
    # the time definitions? Fence post issue?
    #
    # Is adding two to the number of cycles the right thing to do?
    _cycles = cycles + 2

    # We need to create the test data
    sim_object.cosimulate(_cycles)

    config = RawConfigParser()
    config.read('veriutils.cfg')

    # Before we mess with toVHDL, remember what it was originally.
    toVHDL_name_state = toVHDL.name
    toVHDL_dir_state = toVHDL.directory
    
    tmp_dir = tempfile.mkdtemp()
    # We now need to make sure we clean up after ourselves.
    try:
        project_name = 'tmp_project'
        project_path = os.path.join(tmp_dir, project_name)

        time = period * _cycles

        try:
            ip_dependencies = dut_factory.ip_dependencies
        except AttributeError:
            ip_dependencies = ()

        try:
            vhdl_dependencies = list(dut_factory.vhdl_dependencies)
        except AttributeError:
            vhdl_dependencies = []

        xci_file_list = [
            config.get('IP paths', each_ip) for each_ip in ip_dependencies]

        ip_additional_vhdl_files = []

        for each_ip in ip_dependencies:
            if config.has_option('IP additional files', each_ip):
                ip_additional_vhdl_files += [
                    each.strip() for each in 
                    config.get('IP additional files', each_ip).split()]
        
        vhdl_dut_files = [os.path.join(tmp_dir, 'dut_convertible_top.vhd'),
                          os.path.join(tmp_dir, myhdl_vhdl_package_filename)]

        vhdl_files = (
            vhdl_dependencies + vhdl_dut_files + ip_additional_vhdl_files)

        for each_xci_file in xci_file_list:
            # The files should all now exist
            if not os.path.exists(each_xci_file):
                raise EnvironmentError('An expected xci IP file is missing: '
                                       '%s' % (each_xci_file))

        xci_files_string = ' '.join(xci_file_list)
        vhdl_files_string = ' '.join(vhdl_files)

        template_substitutions = {
            'part': config.get('General', 'part'),
            'project_name': project_name,
            'project_path': project_path,
            'time': time,
            'xci_files': xci_files_string,
            'vhdl_files': vhdl_files_string}

        template_file_path = os.path.abspath(
            config.get('tcl template paths', 'simulate'))

        with open(template_file_path, 'r') as template_file:
            template_string = template_file.read()

        simulate_template = Template(template_string)
        simulate_script = simulate_template.safe_substitute(
            template_substitutions)

        simulate_script_filename = os.path.join(
            tmp_dir, 'simulate_script.tcl')

        with open(simulate_script_filename, 'w') as simulate_script_file:
            simulate_script_file.write(simulate_script)
        
        # Generate the output VHDL files
        toVHDL.name = None
        toVHDL.directory = tmp_dir

        signal_output_filename = os.path.join(tmp_dir, 'signal_outputs')
        toVHDL(sim_object.dut_convertible_top, signal_output_filename)

        for each_vhdl_file in vhdl_files:
            # The files should all now exist
            if not os.path.exists(each_vhdl_file):
                raise EnvironmentError('An expected vhdl file is missing: %s'
                                       % (each_vhdl_file))

        vivado_process = subprocess.Popen(
            [VIVADO_EXECUTABLE, '-nolog', '-nojournal', '-mode', 'batch', 
             '-source', simulate_script_filename], stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        out, err = vivado_process.communicate()

        if err != '':

            xvhdl_log_filename = os.path.join(
                tmp_dir, 'tmp_project', 'tmp_project.sim', 'sim_1', 'behav', 
                'xvhdl.log')

            if xvhdl_log_filename in err:
                with open(xvhdl_log_filename, 'r') as log_file:
                    err += '\n'
                    err += 'xvhdl.log:\n'
                    err += log_file.read()

            raise RuntimeError(
                'Error running the Vivado simulator:\n%s' % err)

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
        for each_signal_name_str in vivado_signals:

            each_dut_outputs = []

            signal_type, each_signal = each_signal_name_str.split(' ')

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
                
            output_name_list = each_signal.split('.')

            if len(output_name_list) > 1:
                # We have an interface, so group the recorded signals 
                # of the interface together.

                # FIXME Only one level of interface supported
                interface_outputs.setdefault(
                    output_name_list[0], {})[output_name_list[1]] = (
                        each_dut_outputs)
            else:
                # We have a normal signal
                dut_outputs[each_signal] = each_dut_outputs

        for each_interface in interface_outputs:

            attr_names = interface_outputs[each_interface].keys()

            reordered_interface_outputs =  zip(
                *(interface_outputs[each_interface][key] for 
                  key in attr_names))

            dut_outputs[each_interface] = [
                dict(zip(attr_names, each)) for 
                each in reordered_interface_outputs]

        for each_signal in ref_outputs:
            # Now only output the correct number of cycles
            ref_outputs[each_signal] = ref_outputs[each_signal][:cycles]
            dut_outputs[each_signal] = dut_outputs[each_signal][:cycles]

    finally:
        # Undo the changes to toVHDL
        toVHDL.name = toVHDL_name_state
        toVHDL.directory = toVHDL_dir_state
        shutil.rmtree(tmp_dir)
        
    return dut_outputs, ref_outputs



from .base_hdl_test import HDLTestCase, TestCase

from veriutils import *
from myhdl import (intbv, modbv, enum, Signal, ResetSignal, instance,
                   delay, always, always_seq, Simulation, StopSimulation,
                   toVHDL)

import unittest
import copy
from itertools import chain
from random import randrange

import os
import tempfile
import shutil

import mock
from distutils import spawn

from veriutils import (SynchronousTest, myhdl_cosimulation,
                       vivado_cosimulation)


class CosimulationTestMixin(object):
    '''There should be a well defined cosimulation interface. It should
    provide the facility to use a few off-the-shelf simulation tools like
    a clock generator.
    '''

    check_mocks = True

    def setUp(self):
        self.clock = Signal(bool(1))
        self.reset = ResetSignal(bool(0), active=1, async=False)
        self.test_in = Signal(intbv(0)[10:])
        self.test_out = Signal(intbv(0)[16:])

        self.reset_cycles = 3 # Includes the initial value

        self.default_args = {'test_input': self.test_in, 'output': self.test_out, 
                             'reset': self.reset, 'clock': self.clock}

        self.default_arg_types = {'test_input': 'random', 'output': 'output', 
                                  'reset': 'init_reset', 'clock': 'clock'}
        
        self.sim_checker = mock.Mock()
        def identity_factory(test_input, output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.val))

                output.next = test_input

            return identity

        self.identity_factory = identity_factory

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs): # pragma: no cover
        raise NotImplementedError

    def test_single_clock(self):
        '''The argument lists should contain one and only one clock.
        '''
        self.assertRaisesRegex(
            ValueError, 'Missing clock', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'output': 'custom', 'reset': 'init_reset', 
             'clock': 'custom'})            

        self.assertRaisesRegex(
            ValueError, 'Multiple clocks', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'clock', 'output': 'custom', 'reset': 'init_reset', 
             'clock': 'clock'})

    def test_single_reset(self):
        '''The argument lists should contain one and only one reset.

        A reset can either be an init_reset or a custom_reset. There should
        be exactly one of either of these.
        '''
        self.assertRaisesRegex(
            ValueError, 'Missing reset', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'output': 'custom', 'reset': 'custom', 
             'clock': 'clock'})            

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'init_reset', 'output': 'custom', 
             'reset': 'init_reset', 'clock': 'clock'})

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom_reset', 'output': 'custom', 
             'reset': 'custom_reset', 'clock': 'clock'})

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom_reset', 'output': 'custom', 
             'reset': 'init_reset', 'clock': 'clock'})

    def test_init_reset_used(self):
        '''The first two output edges should yield the init reset values.
        '''
        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, self.default_arg_types)

        for signal in ('test_input', 'output'):
            self.assertEqual(
                dut_results[signal][:self.reset_cycles], 
                [self.default_args[signal]._init] * self.reset_cycles)


    def test_custom_source(self):
        '''It should be possible to specify custom sources.

        The custom sources should be a list of simulation instances which 
        should be passed to the test object at instantiation time.

        Each custom source in the list should be an 
        instantiated block with all the signals set up already.
        '''
        mod_max = 20
        def _custom_source(output, clock):
            counter = modbv(0, min=0, max=mod_max)
            reset = ResetSignal(bool(0), active=1, async=False)
            @always_seq(clock.posedge, reset=reset)
            def custom():
                counter[:] = counter + 1
                output.next = counter

            return custom

        custom_source = _custom_source(self.default_args['test_input'],
                                       self.default_args['clock'])

        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, 
            {'test_input': 'custom', 'output': 'output',
             'reset': 'init_reset', 'clock': 'clock'}, 
            custom_sources=[custom_source])
            
        test_input = [i % mod_max for i in range(sim_cycles)]
        self.assertEqual(test_input, ref_results['test_input'])
        self.assertEqual(test_input, dut_results['test_input'])

    def test_custom_reset(self):
        '''It should be possible to specify a custom reset.

        The custom reset source should be appended to the list of 
        custom_sources passed to the test object at instantiation.
        '''
        test_input = []
        def _custom_reset_source(driven_reset, clock):
            reset = ResetSignal(bool(0), active=1, async=False)
            @always_seq(clock.posedge, reset=reset)
            def custom():
                next_reset = randrange(0, 2)
                driven_reset.next = next_reset
                test_input.append(next_reset)

            return custom

        custom_source = _custom_reset_source(self.default_args['reset'],
                                             self.default_args['clock'])


        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, 
            {'test_input': 'custom', 'output': 'output',
             'reset': 'custom_reset', 'clock': 'clock'}, 
            custom_sources=[custom_source])

        # truncated test_input to be only sim_cycles long, in case extra
        # sim cycles were added at sim time
        test_input = test_input[:sim_cycles]

        # Offset the results by one since test_input has recorded one
        # earlier cycle.
        self.assertEqual(test_input[:-1], ref_results['reset'][1:])
        self.assertEqual(test_input[:-1], dut_results['reset'][1:])

    def test_ref_uses_original_output(self):
        '''It should be the ref_factory that gets the original output signal.

        This is important as it allows the output signal to be used by a
        custom source, and it is the reference that is used.
        '''
        def useless_factory(test_input, output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def useless():
                # Include test_input to stop complaints about undriven signal
                output.next = 0 * test_input

            return useless

        mod_max = 20
        def _custom_source(test_input, output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def custom():
                # Adds one to the output signal
                test_input.next = output + 1

            return custom

        custom_source = _custom_source(self.default_args['test_input'],
                                       self.default_args['output'],
                                       self.default_args['reset'],
                                       self.default_args['clock'])

        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, useless_factory, self.identity_factory, 
            self.default_args, 
            {'test_input': 'custom', 'output': 'output',
             'reset': 'init_reset', 'clock': 'clock'}, 
            custom_sources=[custom_source])

        test_dut_output = [0] * sim_cycles
        assert sim_cycles % 2 == 0 # the following works for even sim_cycles.

        # Make sure we add the reset cycles 
        test_ref_output = [0] * self.reset_cycles + list(
            chain.from_iterable((i, i) for i in range(sim_cycles//2)))

        # Then truncate it suitably
        test_ref_output = test_ref_output[:sim_cycles]

        self.assertEqual(test_ref_output, ref_results['output'])
        self.assertEqual(test_dut_output, dut_results['output'])

    def test_all_argument_types_and_args_have_same_keys(self):
        '''The arg dict should have the same keys as the arg types dict
        '''
        self.assertRaisesRegex(
            ValueError, 'Invalid argument or argument type keys', 
            self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'output': 'custom', 'reset': 'custom', 
             'foo': 'custom'})


    def test_trivial_case(self):
        '''The test object with identity factories should pass every time'''

        sim_cycles = 30
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, self.default_arg_types)

        if self.check_mocks:
            # The mock should be called twice per cycle, with the caveat that
            # it is not called at all on the reset cycles.
            assert len(self.sim_checker.call_args_list) == (
                (sim_cycles - self.reset_cycles) * 2)

            # The expected calls are found from what is recorded on the output.
            # These are recorded even during reset cycles, so we need to offset
            # those. 
            # Also we record one cycle delayed from the sim_checker mock above,
            # so we need to offset left by that too.
            dut_expected_mock_calls = [
                mock.call(each) for each in 
                dut_results['output'][self.reset_cycles:][1:]]
            ref_expected_mock_calls = [
                mock.call(each) for each in 
                ref_results['output'][self.reset_cycles:][1:]]

            # The sim checker args should be shifted up by one sample since
            # they record a sample earlier than the recorded outputs.
            out_signals = zip(self.sim_checker.call_args_list[::2][:-1],
                              self.sim_checker.call_args_list[1::2][:-1],
                              dut_expected_mock_calls,
                              ref_expected_mock_calls)

            for dut_arg, ref_arg, expected_dut, expected_ref in out_signals:
                assert dut_arg == ref_arg # Should be true (defined by the test)

                self.assertEqual(dut_arg, expected_dut)
                self.assertEqual(ref_arg, expected_ref)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_dut_factory_returning_None_raises(self):
        '''If the dut factory returns None, a ValueError should be raised.
        
        The ValueError should contain information about which factory is 
        failing. Failing to return from the factory is a common mistake.
        '''

        def none_factory(**kwargs):
            return None

        self.assertRaisesRegex(ValueError, 'The dut factory returned a None '
                               'object, not an instance',
                               self.construct_and_simulate, 30,
                               none_factory, self.identity_factory, 
                               self.default_args, self.default_arg_types)

    def test_ref_factory_returning_None_raises(self):
        '''If the ref factory returns None, a ValueError should be raised.
        
        The ValueError should contain information about which factory is 
        failing. Failing to return from the factory is a common mistake.
        '''

        def none_factory(**kwargs):
            return None

        self.assertRaisesRegex(ValueError, 'The ref factory returned a None '
                               'object, not an instance',
                               self.construct_and_simulate, 30,
                               self.identity_factory, none_factory,
                               self.default_args, self.default_arg_types)


    def test_interface_case(self):
        '''It should be possible to work with interfaces'''

        args = self.default_args.copy()

        min_val = -1000
        max_val = 1000
        enum_names = ('a', 'b', 'c', 'd', 'e')
        enum_vals = enum(*enum_names)

        class Interface(object):
            def __init__(self):
                # The attributes are sorted, so we need to run through
                # them in the correct order. 'a', 'b', 'c', 'd' is fine.
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(intbv(0, min=min_val, max=max_val))
                self.c = Signal(bool(0))
                self.d = Signal(enum_vals.a)

        def identity_factory(test_input, output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.a.val), 
                                     copy.copy(test_input.b.val),
                                     copy.copy(test_input.c.val), 
                                     copy.copy(test_input.d.val))

                output.a.next = test_input.a
                output.b.next = test_input.b
                output.c.next = test_input.c
                output.d.next = test_input.d

            return identity            

        args['test_input'] = Interface()
        args['output'] = Interface()

        sim_cycles = 31

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory, 
            args, self.default_arg_types)

        # The mock should be called twice per cycle, with the caveat that
        # it is not called at all on the reset cycles.
        assert len(self.sim_checker.call_args_list) == (
            (sim_cycles - self.reset_cycles) * 2)

        # The expected calls are found from what is recorded on the output.
        # These are recorded even during reset cycles, so we need to offset
        # those. 
        # Also we record one cycle delayed from the sim_checker mock above,
        # so we need to offset left by that too.
        dut_expected_mock_calls = [
            mock.call(each['a'], each['b'], each['c'], each['d']) 
            for each in dut_results['output'][self.reset_cycles:][1:]]

        ref_expected_mock_calls = [
            mock.call(each['a'], each['b'], each['c'], each['d']) 
            for each in ref_results['output'][self.reset_cycles:][1:]]

        # The sim checker args should be shifted up by one sample since
        # they record a sample earlier than the recorded outputs.
        out_signals = zip(self.sim_checker.call_args_list[::2][:-1],
                          self.sim_checker.call_args_list[1::2][:-1],
                          dut_expected_mock_calls,
                          ref_expected_mock_calls)

        for dut_arg, ref_arg, expected_dut, expected_ref in out_signals:
            assert dut_arg == ref_arg # Should be true (defined by the test)

            self.assertEqual(dut_arg, expected_dut)
            self.assertEqual(ref_arg, expected_ref)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_invalid_signal(self):
        '''If the arg type is not a valid type, a ValueError should be raised.
        '''
        self.assertRaisesRegex(
            ValueError, 'Invalid argument or argument types',
            self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'output': 'custom', 'reset': 'INVALID', 
             'clock': 'custom'})


    def test_failing_case(self):
        '''The test object with wrong factories should have wrong output'''

        def flipper_factory(test_input, output, reset, clock):
            '''Flips the output bits
            '''
            @always_seq(clock.posedge, reset=reset)
            def flipper():
                output.next = ~test_input

            return flipper

        
        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, flipper_factory, 
            self.default_args, self.default_arg_types)

        for signal in dut_results:

            if self.default_arg_types[signal] == 'output':
                self.assertNotEqual(dut_results[signal], 
                                    ref_results[signal])
            else:
                # Not an output, so should be the same
                self.assertEqual(dut_results[signal], 
                                    ref_results[signal])


class TestSynchronousTestClass(CosimulationTestMixin, TestCase):
    '''The SynchronousTest class should provide the core of the cosimulation.
    
    It should take four arguments: a pair of instance factories, a dict of 
    arguments, and dict of argument types (that tell the test class how to
    handle the arguments, be they inputs or outputs).
    '''

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs):

        test_obj = SynchronousTest(
            dut_factory, ref_factory, args, arg_types, **kwargs)

        return test_obj.cosimulate(sim_cycles)

    def test_dut_factory_is_None(self):
        '''It should be possible to pass None as the dut factory.

        In order that it is possible to generate a set of correct reference
        signals without a device to test, it should be possible to set the
        dut factory to None.

        In such a case, the reference should be simulated as expected, but on
        simulation, there should be no result from the dut case 
        (instead, None should returned).
        '''
        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, None, self.identity_factory, self.default_args, 
            {'test_input': 'custom', 'output': 'output',
             'reset': 'init_reset', 'clock': 'clock'})

        self.assertIs(dut_results, None)

    def test_dut_convertible_top_raises_for_insufficient_data(self):
        '''The convertible top method should raise if the sim not run first.

        In order that there is a correct test vector generated, the simulator
        should be run before the convertible top is run.

        If this has not happened, a RuntimeError should be raised.
        '''
        test_obj = SynchronousTest(
            self.identity_factory, self.identity_factory, 
            self.default_args, self.default_arg_types)

        self.assertRaisesRegex(
            RuntimeError, 'The simulator should be run before '
            'dut_convertible_top', test_obj.dut_convertible_top,
            'foobarfile')

        # Check it happened before the file was written
        assert not os.path.exists('foobarfile')

    def test_dut_convertible_top_raises_with_enum_signals(self):
        '''enum signals passed to dut_convertible_top should raise

        Whilst enum signals are not supported for conversion, they should 
        raise a proper ValueError.
        '''
        simulated_input_cycles = 20

        args = self.default_args.copy()

        enum_names = ('a', 'b', 'c', 'd', 'e')
        enum_vals = enum(*enum_names)
        args['output'] = Signal(enum_vals.a)
        args['test_input'] = Signal(enum_vals.a)

        test_obj = SynchronousTest(
            self.identity_factory, self.identity_factory, 
            args, self.default_arg_types)

        test_obj.cosimulate(simulated_input_cycles)

        self.assertRaisesRegex(
            ValueError, 'enum signals are currently unsupported', 
            test_obj.dut_convertible_top, 'foobarfile')


    def test_dut_convertible_top(self):
        '''There should be a method to get a top-level convertible dut.
        
        In order that the cosimulation class can be used to generate 
        converted code of the device under test, it should be possible to
        provide a suitable method to MyHDL's toVHDL.

        The text file to which the signal outputs should be written should 
        be the only argument to the method.
    
        The method should take no other arguments since the SynchronousTest 
        object should have all the signals internally defined.
        '''

        simulated_input_cycles = 20

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        args['test_input2'] = Signal(intbv(0)[10:])
        arg_types['test_input2'] = 'random'

        def dut(test_input, test_input2, output, reset, clock):

            @always_seq(self.clock.posedge, reset)
            def test_dut():

                output.next = test_input + test_input2

            return test_dut

        test_obj = SynchronousTest(dut, dut, args, arg_types)

        tmp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(tmp_dir, 'test_file')

        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(simulated_input_cycles)

        # remember the toVHDL.directory state
        try:
            toVHDL_directory_state = toVHDL.directory
            toVHDL.directory = tmp_dir

            toVHDL(test_obj.dut_convertible_top, temp_file)

            self.assertTrue(os.path.exists(output_file))

        finally:
            toVHDL.directory = toVHDL_directory_state
            shutil.rmtree(tmp_dir)

    def test_dut_convertible_top_with_interface(self):
        '''Convertible top duts with interfaces should be supported.
        
        The dut_convertible_top method should be able to handle interfaces,
        expanding them out as necessary.
        '''
        simulated_input_cycles = 20

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(intbv(0, min=min_val, max=max_val))
                self.c = Signal(bool(0))

        def dut(test_input, test_input2, output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def test_dut():
                # make sure output.a never overflows
                if test_input.a < max_val - 10:
                    output.a.next = test_input.a + test_input2

                output.b.next = test_input.b
                output.c.next = test_input.c

            return test_dut

        args['test_input'] = Interface()
        args['output'] = Interface()

        args['test_input2'] = Signal(intbv(0)[2:])
        arg_types['test_input2'] = 'random'

        test_obj = SynchronousTest(dut, dut, args, arg_types)

        tmp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(tmp_dir, 'test_file')

        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(simulated_input_cycles)

        # remember the toVHDL.directory state
        try:
            toVHDL_directory_state = toVHDL.directory
            toVHDL.directory = tmp_dir

            toVHDL(test_obj.dut_convertible_top, temp_file)

            self.assertTrue(os.path.exists(output_file))

        finally:
            toVHDL.directory = toVHDL_directory_state
            shutil.rmtree(tmp_dir)


class TestCosimulationFunction(TestSynchronousTestClass):
    '''In order to simplify the process of running a cosimulation, as well
    as providing a common interface for different types of cosimulation, 
    there should be a helper function that wraps a SynchronousTest object and
    calls the cosimulate method, returning what that method returns.
    '''

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs):

        return myhdl_cosimulation(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)


_vivado_executable = spawn.find_executable('vivado')

def _broken_factory(test_input, output, reset, clock):
    
    @always_seq(clock.posedge, reset=reset)
    def broken_identity():
        output.next = test_input
    
    output.driven = True
    test_input.read = True

    _broken_factory.vhdl_code = '''
garbage
'''

    return broken_identity

class TestVivadoCosimulationFunction(CosimulationTestMixin, TestCase):
    '''There should be an alternative version of the cosimulation function
    that runs the device under test through the Vivado simulator.
    '''

    check_mocks = False

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs):
        
        if _vivado_executable is None:
            raise unittest.SkipTest('Vivado executable not in path')

        return vivado_cosimulation(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

    @unittest.skipIf(_vivado_executable is None,
                     'Vivado executable not in path')
    def test_vivado_VHDL_error_raises(self):
        '''Errors with VHDL code in Vivado should raise a RuntimeError.
        '''
        sim_cycles = 30

        self.assertRaisesRegex(
            RuntimeError, 'Error running the Vivado simulator',
            vivado_cosimulation, sim_cycles, 
            _broken_factory, self.identity_factory, 
            self.default_args, self.default_arg_types)


    def test_missing_vivado_raises(self):
        '''Vivado missing from the path should raise an EnvironmentError.
        '''
        sim_cycles = 30

        existing_PATH = os.environ['PATH']
        try:
            os.environ['PATH'] = ''
            self.assertRaisesRegex(
                EnvironmentError, 'Vivado executable not in path',
                vivado_cosimulation, sim_cycles, 
                self.identity_factory, self.identity_factory, 
                self.default_args, self.default_arg_types)

        finally:
            os.environ['PATH'] = existing_PATH

    def test_interface_case(self):
        '''It should be possible to work with interfaces'''

        args = self.default_args.copy()

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                # The attributes are sorted, so we need to run through
                # them in the correct order. 'a', 'b', 'c', 'd' is fine.
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(intbv(0, min=min_val, max=max_val))
                self.c = Signal(intbv(0, min=0, max=max_val))                
                self.d = Signal(bool(0))

        def identity_factory(test_input, output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                output.a.next = test_input.a
                output.b.next = test_input.b
                output.c.next = test_input.c
                output.d.next = test_input.d

            return identity            

        args['test_input'] = Interface()
        args['output'] = Interface()

        sim_cycles = 31

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory, 
            args, self.default_arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

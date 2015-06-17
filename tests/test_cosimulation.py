from tests.base_hdl_test import HDLTestCase, TestCase

from veriutils import *
from myhdl import (intbv, modbv, enum, Signal, ResetSignal, instance,
                   delay, always, always_seq, Simulation, StopSimulation,
                   toVHDL, always_comb)

import unittest
import copy
from itertools import chain
from random import randrange

import os
import tempfile
import shutil

import mock

from veriutils import (
    VIVADO_EXECUTABLE, SynchronousTest, myhdl_cosimulation,
    vivado_vhdl_cosimulation, VivadoError, random_source)


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

        self.default_args = {'test_input': self.test_in, 
                             'test_output': self.test_out, 
                             'reset': self.reset,
                             'clock': self.clock}

        self.default_arg_types = {'test_input': 'random', 'test_output': 'output', 
                                  'reset': 'init_reset', 'clock': 'clock'}
        
        self.sim_checker = mock.Mock()
        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.val))

                test_output.next = test_input

            return identity

        self.identity_factory = identity_factory

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs): # pragma: no cover
        raise NotImplementedError

    def construct_simulate_and_munge(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs): # pragma: no cover
        raise NotImplementedError

    def results_munger(self, premunged_results):
        return premunged_results

    def test_single_clock(self):
        '''The argument lists should contain one and only one clock.
        '''
        self.assertRaisesRegex(
            ValueError, 'Missing clock', self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': 'custom', 'reset': 'init_reset', 
             'clock': 'custom'})            

        self.assertRaisesRegex(
            ValueError, 'Multiple clocks', self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'clock', 'test_output': 'custom', 'reset': 'init_reset', 
             'clock': 'clock'})

        class InterfaceWithClock(object):
            def __init__(self):
                self.clock = Signal(bool(1))

        args = self.default_args.copy()
        args['test_input'] = InterfaceWithClock()

        self.assertRaisesRegex(
            ValueError, 'Multiple clocks', self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, args,
            {'test_input': {'clock': 'clock'}, 'test_output': 'custom', 
             'reset': 'init_reset', 'clock': 'clock'})

    def test_single_reset(self):
        '''The argument lists should contain at most one reset.

        A reset can either be an init_reset or a custom_reset. There should
        be at most one of either of these.
        '''
        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'init_reset', 'test_output': 'custom', 
             'reset': 'init_reset', 'clock': 'clock'})

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom_reset', 'test_output': 'custom', 
             'reset': 'custom_reset', 'clock': 'clock'})

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom_reset', 'test_output': 'custom', 
             'reset': 'init_reset', 'clock': 'clock'})

        class InterfaceWithReset(object):
            def __init__(self):
                self.reset = ResetSignal(bool(0), active=1, async=False)

        args = self.default_args.copy()
        args['test_input'] = InterfaceWithReset()

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, args,
            {'test_input': {'reset': 'custom_reset'}, 'test_output': 'custom', 
             'reset': 'init_reset', 'clock': 'clock'})

    def test_missing_reset_ok(self):
        '''It should be possible to have no reset and everything work fine.
        '''

        sim_cycles = 20
        def no_reset_identity_factory(test_input, test_output, clock):
            @always(clock.posedge)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.val))

                test_output.next = test_input

            return identity

        del self.default_args['reset']
        del self.default_arg_types['reset']

        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, no_reset_identity_factory, no_reset_identity_factory, 
            self.default_args, self.default_arg_types)

        self.assertNotIn('reset', ref_results)
        self.assertNotIn('reset', dut_results)

        initial_output = int(self.default_args['test_output'].val)
        remaining_output = int(self.default_args['test_input'].val)

        self.assertTrue(ref_results['test_output'][0] == initial_output)

        self.assertTrue(ref_results['test_output'][1:] == 
                        ref_results['test_input'][:-1])

    def test_init_reset_used(self):
        '''The first two output edges should yield the init reset values.
        '''
        sim_cycles = 20
        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, self.default_arg_types)

        for signal in ('test_input', 'test_output'):
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
        def _custom_source(test_output, clock):
            counter = modbv(0, min=0, max=mod_max)
            reset = ResetSignal(bool(0), active=1, async=False)
            @always_seq(clock.posedge, reset=reset)
            def custom():
                counter[:] = counter + 1
                test_output.next = counter

            return custom

        custom_source = _custom_source(self.default_args['test_input'],
                                       self.default_args['clock'])

        sim_cycles = 20
        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, 
            {'test_input': 'custom', 'test_output': 'output',
             'reset': 'init_reset', 'clock': 'clock'}, 
            custom_sources=[custom_source])
            
        test_input = [i % mod_max for i in range(sim_cycles)]

        test_input = self.results_munger(test_input)
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
        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, 
            {'test_input': 'custom', 'test_output': 'output',
             'reset': 'custom_reset', 'clock': 'clock'}, 
            custom_sources=[custom_source])

        # truncated test_input to be only sim_cycles long, in case extra
        # sim cycles were added at sim time
        test_input = test_input[:sim_cycles]

        # Do any necessary munging of the results
        test_input = self.results_munger(test_input)

        # Offset the results by one since test_input has recorded one
        # earlier cycle.
        self.assertEqual(test_input[:-1], ref_results['reset'][1:])
        self.assertEqual(test_input[:-1], dut_results['reset'][1:])

    def test_all_argument_types_and_args_have_same_keys(self):
        '''The arg dict should have the same keys as the arg types dict
        '''
        self.assertRaisesRegex(
            ValueError, 'Invalid argument or argument type keys', 
            self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': 'custom', 'reset': 'custom', 
             'foo': 'custom'})


    def test_trivial_case(self):
        '''The test object with identity factories should pass every time'''

        sim_cycles = 30
        dut_results, ref_results = self.construct_simulate_and_munge(
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
                dut_results['test_output'][self.reset_cycles:][1:]]
            ref_expected_mock_calls = [
                mock.call(each) for each in 
                ref_results['test_output'][self.reset_cycles:][1:]]

            # The sim checker args should be shifted up by one sample since
            # they record a sample earlier than the recorded outputs.
            out_signals = zip(self.sim_checker.call_args_list[::2][:-1],
                              self.sim_checker.call_args_list[1::2][:-1],
                              dut_expected_mock_calls,
                              ref_expected_mock_calls)

            for dut_arg, ref_arg, expected_dut, expected_ref in out_signals:
                # Should be true (defined by the test)
                assert dut_arg == ref_arg 

                self.assertEqual(dut_arg, expected_dut)
                self.assertEqual(ref_arg, expected_ref)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_simulation_cleans_up(self):
        '''The simulation should clean up afterwards.
        
        Sensitivity lists and so on on the signals should be cleared.
        '''

        sim_cycles = 30

        args = copy.copy(self.default_args)
        arg_types = copy.copy(self.default_arg_types)

        def identity_factory(test_input, test_input2, test_output, reset, clock):

            @always_comb
            def assignment():
                test_input2.next = test_input

            @always_seq(clock.posedge, reset=reset)
            def identity():

                test_output.next = test_input2

            return identity, assignment

        args['test_input2'] = Signal(intbv(0)[10:])
        arg_types['test_input2'] = 'output'

        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, identity_factory, identity_factory, args, arg_types)

        self.assertTrue(
            len(args['test_input']._eventWaiters) == 0)

        self.assertTrue(
            len(args['clock']._posedgeWaiters) == 0)

    def test_signals_cleared_at_simulation_initialisation(self):
        '''The signals should be made their expected init values before sim.
        
        It is possible to break simulations by forcibly changing the state
        of a signal. Signals should be explicitly cleared prior to use in
        order that they behave consistently with expectations
        '''
        sim_cycles = 30
        test_input = self.default_args['test_input']
        clock = self.default_args['clock']
        reset = self.default_args['reset']

        self.default_arg_types['test_input'] = 'custom'
        seed = randrange(0, 0x5EEDF00D)

        custom_sources = [random_source(test_input, clock, reset, seed=seed)]
        _, ref_results = self.construct_simulate_and_munge(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, self.default_arg_types, 
            custom_sources=custom_sources)
        
        # Mess with the signal states
        test_input._val = intbv(5, min=test_input.min, max=test_input.max)

        custom_sources = [random_source(test_input, clock, reset, seed=seed)]
        _, ref_results2 = self.construct_simulate_and_munge(
            sim_cycles, self.identity_factory, self.identity_factory, 
            self.default_args, self.default_arg_types, 
            custom_sources=custom_sources)


        for signal in ref_results:
            # The messing should have made no difference to the sim result.
            self.assertEqual(ref_results[signal], ref_results2[signal])



    def test_dut_factory_returning_None_raises(self):
        '''If the dut factory returns None, a ValueError should be raised.
        
        The ValueError should contain information about which factory is 
        failing. Failing to return from the factory is a common mistake.
        '''

        def none_factory(**kwargs):
            return None

        self.assertRaisesRegex(ValueError, 'The dut factory returned a None '
                               'object, not an instance',
                               self.construct_simulate_and_munge, 30,
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
                               self.construct_simulate_and_munge, 30,
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

        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.a.val), 
                                     copy.copy(test_input.b.val),
                                     copy.copy(test_input.c.val), 
                                     copy.copy(test_input.d.val))

                test_output.a.next = test_input.a
                test_output.b.next = test_input.b
                test_output.c.next = test_input.c
                test_output.d.next = test_input.d

            return identity            

        args['test_input'] = Interface()
        args['test_output'] = Interface()

        sim_cycles = 31

        dut_results, ref_results = self.construct_simulate_and_munge(
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
            for each in dut_results['test_output'][self.reset_cycles:][1:]]

        ref_expected_mock_calls = [
            mock.call(each['a'], each['b'], each['c'], each['d']) 
            for each in ref_results['test_output'][self.reset_cycles:][1:]]

        # The sim checker args should be shifted up by one sample since
        # they record a sample earlier than the recorded outputs.
        out_signals = zip(self.sim_checker.call_args_list[::2][:-1],
                          self.sim_checker.call_args_list[1::2][:-1],
                          dut_expected_mock_calls,
                          ref_expected_mock_calls)

        for dut_arg, ref_arg, expected_dut, expected_ref in out_signals:
            # Should be true (defined by the test)
            assert dut_arg == ref_arg

            self.assertEqual(dut_arg, expected_dut)
            self.assertEqual(ref_arg, expected_ref)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_invalid_signal_type(self):
        '''If the arg type is not a valid type, a ValueError should be raised.
        '''
        self.assertRaisesRegex(
            ValueError, 'Invalid argument or argument types',
            self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': 'custom', 'reset': 'INVALID', 
             'clock': 'custom'})

        class Interface(object):
            def __init__(self):
                self.a = Signal(intbv(0, min=-1000, max=1000))

        self.default_args['test_output'] = Interface()

        self.assertRaisesRegex(
            ValueError, 'Invalid argument or argument types',
            self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': {'a': 'INVALID'}, 
             'reset': 'custom_reset', 'clock': 'custom'})


    def test_argtype_dict_arg_mismatch(self):
        '''All the arg types in a dict should correspond to a valid signal.
        '''
        class Interface(object):
            def __init__(self):
                self.a = Signal(intbv(0, min=-1000, max=1000))

        self.default_args['test_output'] = Interface()

        self.assertRaisesRegex(
            KeyError, 'Arg type dict references a non-existant signal',
            self.construct_simulate_and_munge, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': {'a': 'output', 'b': 'output'}, 
             'reset': 'custom_reset', 'clock': 'custom'})

    def test_interfaces_type_from_dict(self):
        '''It should be possible for interfaces to set the type from a dict.

        The dict should contain a lookup from attribute names to valid
        signal types.
        '''

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                # The attributes are sorted, so we need to run through
                # them in the correct order. 'a', 'b', 'c', 'd' is fine.
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(bool(0))

        # A bit of a hack to check the relevant signals are different
        signals = []
        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    # record the inputs
                    self.sim_checker(copy.copy(test_input.a.val),
                                     copy.copy(test_output.b.val))

                    if len(signals) < 2:
                        # need to record from both dut and ref
                        signals.append(
                            {'test_output.a': test_output.a, 
                             'test_output.b': test_output.b,
                             'test_input.a': test_input.a,
                             'test_input.b': test_input.b})

                test_output.a.next = test_input.a
                test_input.b.next = test_output.b

            return identity

        args['test_input'] = Interface()
        args['test_output'] = Interface()

        # Set up the interface types
        arg_types['test_input'] = {'a': 'random', 'b': 'output'}
        arg_types['test_output'] = {'a': 'output', 'b': 'random'}

        sim_cycles = 31

        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, identity_factory, identity_factory, 
            args, arg_types)

        # The inputs should be the same signal
        self.assertIs(signals[0]['test_output.b'], signals[1]['test_output.b'])
        self.assertIs(signals[0]['test_input.a'], signals[1]['test_input.a'])

        # The outputs should not be
        self.assertIsNot(signals[0]['test_output.a'], signals[1]['test_output.a'])
        self.assertIsNot(signals[0]['test_input.b'],
                         signals[1]['test_input.b'])

        # Check the signals are being driven properly. The random values
        # are very unlikely to be all zeros, which is what we check for here.
        self.assertFalse(
            sum([abs(each['a']) for each in ref_results['test_input']]) == 0)

        self.assertFalse(
            sum([abs(each['b']) for each in ref_results['test_output']]) == 0)

        # Also, check the output is correct
        if self.check_mocks:

            # The mock should be called twice per cycle, with the caveat that
            # it is not called at all on the reset cycles.
            assert len(self.sim_checker.call_args_list) == (
                (sim_cycles - self.reset_cycles) * 2)

            # The expected calls are found from what is recorded on the 
            # output. These are recorded even during reset cycles, so we need 
            # to offset those. 
            # Also we record one cycle delayed from the sim_checker mock 
            # above, so we need to offset left by that too.
            dut_expected_mock_calls = [
                mock.call(_out['a'], _inp['b']) for _inp, _out  in 
                zip(dut_results['test_input'][self.reset_cycles:][1:], 
                    dut_results['test_output'][self.reset_cycles:][1:])]

            ref_expected_mock_calls = [
                mock.call(_out['a'], _inp['b']) for _inp, _out  in 
                zip(ref_results['test_input'][self.reset_cycles:][1:], 
                    ref_results['test_output'][self.reset_cycles:][1:])]

            # The sim checker args should be shifted up by one sample since
            # they record a sample earlier than the recorded outputs.
            out_signals = zip(self.sim_checker.call_args_list[::2][:-1],
                              self.sim_checker.call_args_list[1::2][:-1],
                              dut_expected_mock_calls,
                              ref_expected_mock_calls)

            for dut_arg, ref_arg, expected_dut, expected_ref in out_signals:
                # Should be true (defined by the test)
                assert dut_arg == ref_arg
                self.assertEqual(dut_arg, expected_dut)
                self.assertEqual(ref_arg, expected_ref)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])
            
    def test_clock_in_interface(self):
        '''It should be possible to set the an interface signal as the clock.
        '''
        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        min_val = -1000
        max_val = 1000

        class InterfaceWithClock(object):
            def __init__(self):
                # The attributes are sorted, so we need to run through
                # them in the correct order. 'a', 'b', 'c', 'd' is fine.
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.clock = Signal(bool(0))

        def identity_factory(test_input, test_output, reset):
            @always_seq(test_input.clock.posedge, reset=reset)
            def identity():
                test_output.next = test_input.a

            return identity

        args['test_input'] = InterfaceWithClock()
        args['test_output'] = copy_signal(args['test_input'].a)

        # Set up the interface types
        arg_types['test_input'] = {'a': 'random', 'clock': 'clock'}

        # remove the clock
        del arg_types['clock']
        del args['clock']

        sim_cycles = 31

        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, identity_factory, identity_factory, 
            args, arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_reset_in_interface(self):
        '''It should be possible to set the an interface signal as the reset.
        '''
        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        min_val = -1000
        max_val = 1000

        class InterfaceWithReset(object):
            def __init__(self):
                # The attributes are sorted, so we need to run through
                # them in the correct order. 'a', 'b', 'c', 'd' is fine.
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.reset = ResetSignal(bool(0), active=1, async=False)

        def identity_factory(test_input, test_output, clock):
            @always_seq(clock.posedge, reset=test_input.reset)
            def identity():
                test_output.next = test_input.a

            return identity

        args['test_input'] = InterfaceWithReset()
        args['test_output'] = copy_signal(args['test_input'].a)

        # remove the clock
        del arg_types['reset']
        del args['reset']

        sim_cycles = 31

        # Set up the interface types
        arg_types['test_input'] = {'a': 'random', 'reset': 'init_reset'}

        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, identity_factory, identity_factory, 
            args, arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

        # Also test the custom reset
        arg_types['test_input'] = {'a': 'random', 'reset': 'custom_reset'}

        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, identity_factory, identity_factory, 
            args, arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])



    def test_failing_case(self):
        '''The test object with wrong factories should have wrong output'''

        def flipper_factory(test_input, test_output, reset, clock):
            '''Flips the output bits
            '''
            @always_seq(clock.posedge, reset=reset)
            def flipper():
                test_output.next = ~test_input

            return flipper

        
        sim_cycles = 20
        dut_results, ref_results = self.construct_simulate_and_munge(
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

    def test_non_signal_ignored_in_output(self):
        '''There should be a non-signal arg type for args that are not signals.

        Such arguments should have no representation in the results 
        dictionaries after simulation.
        '''
        def non_sig_identity_factory(
            test_input, test_output, non_sig, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                test_output.next = test_input

            return identity

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        args['non_sig'] = 10
        arg_types['non_sig'] = 'non-signal'

        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, non_sig_identity_factory, non_sig_identity_factory, 
            args, arg_types)

        self.assertNotIn('non_sig', dut_results)
        self.assertNotIn('non_sig', ref_results)


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


    def construct_simulate_and_munge(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs):

        dut_outputs, ref_outputs = self.construct_and_simulate(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

        for each in arg_types:

            if dut_outputs is not None:
                dut_outputs[each] = self.results_munger(dut_outputs[each])

            if ref_outputs is not None:
                ref_outputs[each] = self.results_munger(ref_outputs[each])

        return dut_outputs, ref_outputs

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
        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, None, self.identity_factory, self.default_args, 
            {'test_input': 'custom', 'test_output': 'output',
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

    def test_dut_convertible_top_raises_for_None_dut(self):
        '''If the dut is None, an exception should be raise.

        It should be possible to set the device under test to be None when
        constructing the test class, which would yield a nonsense 
        dut_convertible_top. This situation should cause the 
        dut_convertible_top function raise with a suitable error.
        '''


        test_obj = SynchronousTest(
            None, self.identity_factory, 
            self.default_args, self.default_arg_types)
        test_obj.cosimulate(20)

        self.assertRaisesRegex(
            RuntimeError, 'The dut was configured to be None in construction',
            test_obj.dut_convertible_top, 'foobarfile')

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
        args['test_output'] = Signal(enum_vals.a)
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

        def dut(test_input, test_input2, test_output, reset, clock):

            @always_seq(self.clock.posedge, reset)
            def test_dut():

                test_output.next = test_input + test_input2

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

    def test_dut_convertible_top_with_long_boolean_output(self):
        '''Output booleans with long type vals (0, 1) should be handled.

        That is, code in which output booleans have had their value set 
        using '1' rather than True should convert fine.
        '''

        simulated_input_cycles = 20

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        args['test_output'] = Signal(bool(0))

        args['test_output'].next = 1
        args['test_output']._update()

        del args['test_input']
        del arg_types['test_input']

        def dut(test_output, reset, clock):

            @always_seq(self.clock.posedge, reset)
            def test_dut():
                test_output.next = 1

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

        def dut(test_input, test_input2, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def test_dut():
                # make sure test_output.a never overflows
                if test_input.a < max_val - 10:
                    test_output.a.next = test_input.a + test_input2

                test_output.b.next = test_input.b
                test_output.c.next = test_input.c

            return test_dut

        args['test_input'] = Interface()
        args['test_output'] = Interface()

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

    def test_ref_uses_original_output(self):
        '''It should be the ref_factory that gets the original output signal.

        This is important as it allows the output signal to be used by a
        custom source, and it is the reference that is used.
        '''
        def useless_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def useless():
                # Include test_input to stop complaints about undriven signal
                test_output.next = 0 * test_input

            return useless

        mod_max = 20
        def _custom_source(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def custom():
                # Adds one to the output signal
                test_input.next = test_output + 1

            return custom

        custom_source = _custom_source(self.default_args['test_input'],
                                       self.default_args['test_output'],
                                       self.default_args['reset'],
                                       self.default_args['clock'])

        sim_cycles = 20
        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, useless_factory, self.identity_factory, 
            self.default_args, 
            {'test_input': 'custom', 'test_output': 'output',
             'reset': 'init_reset', 'clock': 'clock'}, 
            custom_sources=[custom_source])

        test_dut_output = [0] * sim_cycles
        assert sim_cycles % 2 == 0 # the following works for even sim_cycles.

        # Make sure we add the reset cycles 
        test_ref_output = [0] * self.reset_cycles + list(
            chain.from_iterable((i, i) for i in range(sim_cycles//2)))

        # Then truncate it suitably
        test_ref_output = test_ref_output[:sim_cycles]

        self.assertEqual(test_ref_output, ref_results['test_output'])
        self.assertEqual(test_dut_output, dut_results['test_output'])

    def test_should_convert_with_non_signal_in_args(self):
        '''The conversion should happen when a non-signal was in the args.
        '''
        def dut(
            test_input, test_output, non_sig, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                test_output.next = test_input

            return identity

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        args['non_sig'] = 10
        arg_types['non_sig'] = 'non-signal'

        sim_cycles = 20

        test_obj = SynchronousTest(dut, dut, args, arg_types)

        tmp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(tmp_dir, 'test_file')

        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(sim_cycles)

        # remember the toVHDL.directory state
        try:
            toVHDL_directory_state = toVHDL.directory
            toVHDL.directory = tmp_dir

            toVHDL(test_obj.dut_convertible_top, temp_file)

            self.assertTrue(os.path.exists(output_file))

        finally:
            toVHDL.directory = toVHDL_directory_state
            shutil.rmtree(tmp_dir)




class TestCosimulationFunction(CosimulationTestMixin, TestCase):
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

    def construct_simulate_and_munge(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs):

        dut_outputs, ref_outputs = self.construct_and_simulate(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

        for each in arg_types:
            if dut_outputs is not None:
                dut_outputs[each] = self.results_munger(dut_outputs[each])

            if ref_outputs is not None:
                ref_outputs[each] = self.results_munger(ref_outputs[each])

        return dut_outputs, ref_outputs

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
        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, None, self.identity_factory, self.default_args, 
            {'test_input': 'custom', 'test_output': 'output',
             'reset': 'init_reset', 'clock': 'clock'})

        self.assertIs(dut_results, None)


def _broken_factory(test_input, test_output, reset, clock):
    
    @always_seq(clock.posedge, reset=reset)
    def broken_identity():
        test_output.next = test_input
    
    test_output.driven = 'reg'
    test_input.read = True

    _broken_factory.vhdl_code = '''
    garbage
    '''
    _broken_factory.verilog_code = '''
    garbage
    '''
    return broken_identity

class VivadoCosimulationFunctionTests(CosimulationTestMixin):
    # Common code for Vivado cosimulation tests.

    check_mocks = False

    def vivado_sim_wrapper(self, sim_cycles, dut_factory, ref_factory, 
                           args, arg_types, **kwargs):

        raise NotImplementedError

    def results_munger(self, premunged_results):
        # Chop off the first value which might be undefined.
        return premunged_results[1:]

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs):

        if VIVADO_EXECUTABLE is None:
            raise unittest.SkipTest('Vivado executable not in path')

        return self.vivado_sim_wrapper(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

    def construct_simulate_and_munge(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types, 
        **kwargs):
        
        if VIVADO_EXECUTABLE is None:
            raise unittest.SkipTest('Vivado executable not in path')

        dut_outputs, ref_outputs = self.construct_and_simulate(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

        # We've used an asynchronous reset, so the output will be undefined
        # at the first clock edge. Therefore we prune the first sample from
        # all the recorded values
        for each in arg_types:
            dut_outputs[each] = self.results_munger(dut_outputs[each])
            ref_outputs[each] = self.results_munger(ref_outputs[each])

        return dut_outputs, ref_outputs


    @unittest.skipIf(VIVADO_EXECUTABLE is None,
                     'Vivado executable not in path')
    def test_keep_tmp_files(self):
        '''It should be possible to keep the temporary files after simulation.
        '''
        sim_cycles = 30
        
        # This method is slightly flaky - it's quite implementation dependent
        # and may break if mkdtemp is imported into the namespace of
        # cosimulation rather than tempfile, or if multiple calls are
        # made to mkdtemp.
        import tempfile, sys
        orig_mkdtemp = tempfile.mkdtemp

        dirs = []
        def mkdtemp_wrapper():
            new_dir = orig_mkdtemp()
            dirs.append(new_dir)

            return new_dir

        try:
            tempfile.mkdtemp = mkdtemp_wrapper

            # We also want to drop the helpful output message to keep
            # the test clean.
            sys.stdout = open(os.devnull, "w")
            self.vivado_sim_wrapper(
                sim_cycles, self.identity_factory, self.identity_factory, 
                self.default_args, self.default_arg_types,
                keep_temp_files=True)
            
            self.assertTrue(os.path.exists(dirs[0]))

        finally:
            # clean up
            tempfile.mkdtemp = orig_mkdtemp
            sys.stdout = sys.__stdout__
            try:
                shutil.rmtree(dirs[0])
            except OSError:
                pass

    def test_missing_vivado_raises(self):
        '''Vivado missing from the path should raise an EnvironmentError.
        '''
        sim_cycles = 30

        existing_PATH = os.environ['PATH']
        import veriutils
        existing_VIVADO_EXECUTABLE = veriutils.VIVADO_EXECUTABLE
        veriutils.cosimulation.VIVADO_EXECUTABLE = None
        try:
            os.environ['PATH'] = ''
            self.assertRaisesRegex(
                EnvironmentError, 'Vivado executable not in path',
                self.vivado_sim_wrapper, sim_cycles, 
                self.identity_factory, self.identity_factory, 
                self.default_args, self.default_arg_types)

        finally:
            os.environ['PATH'] = existing_PATH
            veriutils.cosimulation.VIVADO_EXECUTABLE = (
                existing_VIVADO_EXECUTABLE)

    @unittest.skipIf(VIVADO_EXECUTABLE is None,
                     'Vivado executable not in path')
    def test_missing_xci_file_raises(self):
        '''An EnvironmentError should be raised for a missing xci IP file.

        If the settings stipulate an xci file should be included, but it 
        is not there, an EnvironmentError should be raised.
        '''
        self.identity_factory.ip_dependencies = ['some_other_ip']
        sim_cycles = 10
        self.assertRaisesRegex(
            EnvironmentError, 'An expected xci IP file is missing', 
            self.vivado_sim_wrapper, sim_cycles, self.identity_factory, 
            self.identity_factory, self.default_args, self.default_arg_types)

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

        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                test_output.a.next = test_input.a
                test_output.b.next = test_input.b
                test_output.c.next = test_input.c
                test_output.d.next = test_input.d

            return identity            

        args['test_input'] = Interface()
        args['test_output'] = Interface()

        sim_cycles = 31

        dut_results, ref_results = self.construct_simulate_and_munge(
            sim_cycles, identity_factory, identity_factory, 
            args, self.default_arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

class TestVivadoVHDLCosimulationFunction(VivadoCosimulationFunctionTests, 
                                         TestCase):
    '''There should be an alternative version of the cosimulation function
    that runs the device under test through the Vivado VHDL simulator.
    '''

    def vivado_sim_wrapper(self, sim_cycles, dut_factory, ref_factory, 
                           args, arg_types, **kwargs):

        return vivado_vhdl_cosimulation(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

    @unittest.skipIf(VIVADO_EXECUTABLE is None,
                     'Vivado executable not in path')
    def test_missing_hdl_file_raises(self):
        '''An EnvironmentError should be raised for a missing HDL file.

        If the settings stipulate a HDL file should be included, but it 
        is not there, an EnvironmentError should be raised.
        '''
        self.identity_factory.vhdl_dependencies = ['a_missing_file.vhd']
        sim_cycles = 10
        self.assertRaisesRegex(
            EnvironmentError, 'An expected HDL file is missing', 
            self.vivado_sim_wrapper, sim_cycles, self.identity_factory, 
            self.identity_factory, self.default_args, self.default_arg_types)

    @unittest.skipIf(VIVADO_EXECUTABLE is None,
                     'Vivado executable not in path')
    def test_vivado_VHDL_error_raises(self):
        '''Errors with VHDL code in Vivado should raise a RuntimeError.
        '''
        sim_cycles = 30

        self.assertRaisesRegex(
            VivadoError, 'Error running the Vivado VHDL simulator',
            self.vivado_sim_wrapper, sim_cycles, 
            _broken_factory, self.identity_factory, 
            self.default_args, self.default_arg_types)

class TestVivadoVerilogCosimulationFunction(VivadoCosimulationFunctionTests, 
                                            TestCase):
    '''There should be an alternative version of the cosimulation function
    that runs the device under test through the Vivado verilog simulator.
    '''

    def vivado_sim_wrapper(self, sim_cycles, dut_factory, ref_factory, 
                           args, arg_types, **kwargs):

        return vivado_verilog_cosimulation(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

    @unittest.skipIf(VIVADO_EXECUTABLE is None,
                     'Vivado executable not in path')
    def test_missing_hdl_file_raises(self):
        '''An EnvironmentError should be raised for a missing HDL file.

        If the settings stipulate a HDL file should be included, but it 
        is not there, an EnvironmentError should be raised.
        '''
        self.identity_factory.verilog_dependencies = ['a_missing_file.v']
        sim_cycles = 10
        self.assertRaisesRegex(
            EnvironmentError, 'An expected HDL file is missing', 
            self.vivado_sim_wrapper, sim_cycles, self.identity_factory, 
            self.identity_factory, self.default_args, self.default_arg_types)

    @unittest.skipIf(VIVADO_EXECUTABLE is None,
                     'Vivado executable not in path')
    def test_vivado_verilog_error_raises(self):
        '''Errors with Verilog code in Vivado should raise a RuntimeError.
        '''
        sim_cycles = 30

        self.assertRaisesRegex(
            VivadoError, 'Error running the Vivado Verilog simulator',
            self.vivado_sim_wrapper, sim_cycles, 
            _broken_factory, self.identity_factory, 
            self.default_args, self.default_arg_types)

from veriutils.tests.base_hdl_test import HDLTestCase, TestCase

from veriutils import *
from myhdl import (intbv, modbv, enum, Signal, ResetSignal, instance,
                   delay, always, always_seq, Simulation, StopSimulation,
                   always_comb, block, BlockError)

import unittest
import copy
from itertools import chain
from random import randrange

import os
import tempfile
import shutil

import mock

from veriutils import SynchronousTest, myhdl_cosimulation, random_source


class CosimulationTestMixin(object):
    '''There should be a well defined cosimulation interface. It should
    provide the facility to use a few off-the-shelf simulation tools like
    a clock generator.
    '''

    check_mocks = True

    def setUp(self):
        self.clock = Signal(bool(1))
        self.reset = ResetSignal(bool(0), active=1, isasync=False)
        self.test_in = Signal(intbv(0)[10:])
        self.test_out = Signal(intbv(0)[16:])

        self.reset_cycles = 3 # Includes the initial value

        self.default_args = {'test_input': self.test_in,
                             'test_output': self.test_out,
                             'reset': self.reset,
                             'clock': self.clock}

        self.default_arg_types = {'test_input': 'random',
                                  'test_output': 'output',
                                  'reset': 'init_reset',
                                  'clock': 'clock'}

        self.sim_checker = mock.Mock()
        @block
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

    def test_single_clock(self):
        '''The argument lists should contain one and only one clock.
        '''
        self.assertRaisesRegex(
            ValueError, 'Missing clock', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': 'custom', 'reset': 'init_reset',
             'clock': 'custom'})

        self.assertRaisesRegex(
            ValueError, 'Multiple clocks', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'clock', 'test_output': 'custom', 'reset': 'init_reset',
             'clock': 'clock'})

        class InterfaceWithClock(object):
            def __init__(self):
                self.clock = Signal(bool(1))

        args = self.default_args.copy()
        args['test_input'] = InterfaceWithClock()

        self.assertRaisesRegex(
            ValueError, 'Multiple clocks', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, args,
            {'test_input': {'clock': 'clock'}, 'test_output': 'custom',
             'reset': 'init_reset', 'clock': 'clock'})

    def test_single_reset(self):
        '''The argument lists should contain at most one reset.

        A reset can either be an init_reset or a custom_reset. There should
        be at most one of either of these.
        '''
        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'init_reset', 'test_output': 'custom',
             'reset': 'init_reset', 'clock': 'clock'})

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom_reset', 'test_output': 'custom',
             'reset': 'custom_reset', 'clock': 'clock'})

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom_reset', 'test_output': 'custom',
             'reset': 'init_reset', 'clock': 'clock'})

        class InterfaceWithReset(object):
            def __init__(self):
                self.reset = ResetSignal(bool(0), active=1, isasync=False)

        args = self.default_args.copy()
        args['test_input'] = InterfaceWithReset()

        self.assertRaisesRegex(
            ValueError, 'Multiple resets', self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, args,
            {'test_input': {'reset': 'custom_reset'}, 'test_output': 'custom',
             'reset': 'init_reset', 'clock': 'clock'})

    def test_missing_reset_ok(self):
        '''It should be possible to have no reset and everything work fine.
        '''

        sim_cycles = 20
        @block
        def no_reset_identity_factory(test_input, test_output, clock):
            @always(clock.posedge)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.val))

                test_output.next = test_input

            return identity

        del self.default_args['reset']
        del self.default_arg_types['reset']

        dut_results, ref_results = self.construct_and_simulate(
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
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args, self.default_arg_types)

        for signal in ('test_input', 'test_output'):
            self.assertEqual(
                dut_results[signal][:self.reset_cycles],
                [self.default_args[signal]._init] * self.reset_cycles)

    def test_simulation_exception_still_clears_state(self):
        '''If an exception occurs during calls to the myhdl simulator, the
        global simulator state should still be valid - that is, it should be
        possible to run correct subsequent simulations.
        '''
        sim_cycles = 30

        self.assertRaises(
            Exception, self.construct_and_simulate,
            ['garbage cycles'], self.identity_factory, self.identity_factory,
            self.default_args, self.default_arg_types)

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args, self.default_arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])


    def test_custom_source(self):
        '''It should be possible to specify custom sources.

        The custom sources should be a list of simulation instances which
        should be passed to the test object at instantiation time.

        Each custom source in the list should be an
        instantiated block with all the signals set up already.
        '''
        mod_max = 20
        @block
        def _custom_source(test_output, clock):
            counter = modbv(0, min=0, max=mod_max)
            reset = ResetSignal(bool(0), active=1, isasync=False)
            @always_seq(clock.posedge, reset=reset)
            def custom():
                counter[:] = counter + 1
                test_output.next = counter

            return custom

        custom_source = (_custom_source,
                         (self.default_args['test_input'],
                          self.default_args['clock']), {})

        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args,
            {'test_input': 'custom', 'test_output': 'output',
             'reset': 'init_reset', 'clock': 'clock'},
            custom_sources=[custom_source])

        test_input = [i % mod_max for i in range(sim_cycles)]

        self.assertEqual(test_input, ref_results['test_input'])
        self.assertEqual(test_input, dut_results['test_input'])

    def test_malformed_custom_source_args(self):
        '''custom_sources should be checked for being of the form
        (block, *args, **kwargs) and a ValueError should be raised if
        they are not.
        '''
        mod_max = 20
        @block
        def _custom_source(test_output, clock):
            counter = modbv(0, min=0, max=mod_max)
            reset = ResetSignal(bool(0), active=1, isasync=False)
            @always_seq(clock.posedge, reset=reset)
            def custom():
                counter[:] = counter + 1
                test_output.next = counter

            return custom

        custom_source = (_custom_source,
                         (self.default_args['test_input'],
                          self.default_args['clock']), {})

        call_args = (None, self.identity_factory, self.identity_factory,
                     self.default_args,
                     {'test_input': 'custom', 'test_output': 'output',
                      'reset': 'init_reset', 'clock': 'clock'})

        self.assertRaisesRegex(
            ValueError, 'Malformed custom source',
            self.construct_and_simulate, *call_args,
            custom_sources=
            ([_custom_source, self.default_args['test_input'], {}],))

        self.assertRaisesRegex(
            ValueError, 'Malformed custom source',
            self.construct_and_simulate, *call_args,
            custom_sources=
            [(_custom_source, (self.default_args['test_input'],), None)])

    def test_custom_reset(self):
        '''It should be possible to specify a custom reset.

        The custom reset source should be appended to the list of
        custom_sources passed to the test object at instantiation.
        '''
        test_input = []
        @block
        def _custom_reset_source(driven_reset, clock):
            reset = ResetSignal(bool(0), active=1, isasync=False)
            @always_seq(clock.posedge, reset=reset)
            def custom():
                next_reset = randrange(0, 2)
                driven_reset.next = next_reset
                test_input.append(next_reset)

            return custom

        custom_source = (
            _custom_reset_source,
            (self.default_args['reset'], self.default_args['clock']), {})


        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args,
            {'test_input': 'custom', 'test_output': 'output',
             'reset': 'custom_reset', 'clock': 'clock'},
            custom_sources=[custom_source])

        # truncated test_input to be only sim_cycles long, in case extra
        # sim cycles were added at sim time
        test_input = test_input[:sim_cycles]

        # Offset the results by one since test_input has recorded one
        # earlier cycle.
        self.assertEqual(test_input[:-1], ref_results['reset'][1:])
        self.assertEqual(test_input[:-1], dut_results['reset'][1:])

    def test_axi_stream_out_argument(self):
        '''It should be possible to set an argument type to ``axi_stream_out``
        in which case the AXI4 stream packets are output in addition to the
        signals.

        The output should be a dictionary with two keys, ``packets``,
        ``incomplete_packets`` and ``signals``. ``packets`` should be the
        completed packetised outputs (for which ``TLAST`` was asserted).
        ``incomplete_packet`` should be the most recent AXI data for which
        no ``TLAST`` was asserted, and ``signals`` should be the raw signal
        outputs.
        '''
        self.clock = Signal(bool(1))
        self.test_in = AxiStreamInterface()
        self.test_out = AxiStreamInterface()

        max_packet_length = 20
        max_new_packets = 50
        max_val = 2**(8 * self.test_out.bus_width)

        def val_gen():
            # Generates Nones about half the time probability
            val = random.randrange(0, max_val*2)
            if val >= max_val:
                return None
            else:
                return val

        packet_list = [
            [val_gen() for m
             in range(random.randrange(0, max_packet_length))] for n
            in range(random.randrange(0, max_new_packets))]

        self.default_args = {'axi_interface_in': self.test_in,
                             'axi_interface_out': self.test_out,
                             'clock': self.clock}

        self.default_arg_types = {
            'axi_interface_in': {'TDATA': 'custom',
                                 'TVALID': 'custom',
                                 'TREADY': 'output',
                                 'TLAST': 'custom'},
            'axi_interface_out': 'axi_stream_out',
            'clock': 'clock'}

        @block
        def axi_identity(clock, axi_interface_in, axi_interface_out):

            @always_comb
            def assign_signals():
                axi_interface_in.TREADY.next = axi_interface_out.TREADY
                axi_interface_out.TVALID.next = axi_interface_in.TVALID
                axi_interface_out.TLAST.next = axi_interface_in.TLAST
                axi_interface_out.TDATA.next = axi_interface_in.TDATA

            return assign_signals


        sim_cycles = sum(len(packet) for packet in packet_list) + 1

        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        master_bfm = AxiStreamMasterBFM()
        custom_sources = [(master_bfm.model, (self.clock, self.test_in), {})]

        # Calling several times should work just fine
        master_bfm.add_data(packet_list)
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, axi_identity, axi_identity,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            ref_results['axi_interface_out']['packets'], trimmed_packets)

        self.assertEqual(
            ref_results['axi_interface_out']['incomplete_packet'], [])

        self.assertEqual(
            dut_results['axi_interface_out']['packets'], trimmed_packets)

        self.assertEqual(
            dut_results['axi_interface_out']['incomplete_packet'], [])

    def test_axi_stream_out_with_incomplete_packet(self):
        '''It should be possible to use an ``axi_stream_out`` with an
        incomplete last packet, in which case the incomplete packet is set
        to the ``incomplete_packet`` key of the output dictionary.
        '''
        self.clock = Signal(bool(1))
        self.test_in = AxiStreamInterface()
        self.test_out = AxiStreamInterface()

        max_packet_length = 10
        max_new_packets = 20
        max_val = 2**(8 * self.test_out.bus_width)

        def val_gen():
            # Generates Nones about half the time probability
            val = random.randrange(0, max_val*2)
            if val >= max_val:
                return None
            else:
                return val

        packet_list = [
            [val_gen() for m
             in range(random.randrange(3, max_packet_length))] for n
            in range(random.randrange(3, max_new_packets))]

        # force the last packet to always have at least one value in
        # (otherwise the trimming below will break)
        packet_list[-1][0] = random.randrange(0, max_val)

        self.default_args = {'axi_interface_in': self.test_in,
                             'axi_interface_out': self.test_out,
                             'clock': self.clock}

        self.default_arg_types = {
            'axi_interface_in': {'TDATA': 'custom',
                                 'TVALID': 'custom',
                                 'TREADY': 'output',
                                 'TLAST': 'custom'},
            'axi_interface_out': 'axi_stream_out',
            'clock': 'clock'}

        @block
        def axi_identity(clock, axi_interface_in, axi_interface_out):

            @always_comb
            def assign_signals():
                axi_interface_in.TREADY.next = axi_interface_out.TREADY
                axi_interface_out.TVALID.next = axi_interface_in.TVALID
                axi_interface_out.TLAST.next = axi_interface_in.TLAST
                axi_interface_out.TDATA.next = axi_interface_in.TDATA

            return assign_signals


        sim_cycles = sum(len(packet) for packet in packet_list) + 10

        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        master_bfm = AxiStreamMasterBFM()
        custom_sources = [(master_bfm.model, (self.clock, self.test_in), {})]

        # Calling several times should work just fine
        master_bfm.add_data(packet_list, incomplete_last_packet=True)
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, axi_identity, axi_identity,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            ref_results['axi_interface_out']['packets'], trimmed_packets[:-1])

        self.assertEqual(
            ref_results['axi_interface_out']['incomplete_packet'],
            trimmed_packets[-1])

        self.assertEqual(
            dut_results['axi_interface_out']['packets'], trimmed_packets[:-1])

        self.assertEqual(
            dut_results['axi_interface_out']['incomplete_packet'],
            trimmed_packets[-1])

    def test_axi_stream_out_no_TLAST_argument(self):
        '''It should be possible to use an axi stream interface with no TLAST
        for an `axi_stream_out` type argument.
        '''
        self.clock = Signal(bool(1))
        self.test_in = AxiStreamInterface(use_TLAST=False)
        self.test_out = AxiStreamInterface(use_TLAST=False)

        max_packet_length = 20
        max_new_packets = 50
        max_val = 2**(8 * self.test_out.bus_width)

        def val_gen():
            # Generates Nones about half the time probability
            val = random.randrange(0, max_val*2)
            if val >= max_val:
                return None
            else:
                return val

        packet_list = [
            [val_gen() for m
             in range(random.randrange(0, max_packet_length))] for n
            in range(random.randrange(0, max_new_packets))]

        self.default_args = {'axi_interface_in': self.test_in,
                             'axi_interface_out': self.test_out,
                             'clock': self.clock}

        self.default_arg_types = {
            'axi_interface_in': {'TDATA': 'custom',
                                 'TVALID': 'custom',
                                 'TREADY': 'output'},
            'axi_interface_out': 'axi_stream_out',
            'clock': 'clock'}

        @block
        def axi_identity(clock, axi_interface_in, axi_interface_out):

            @always_comb
            def assign_signals():
                axi_interface_in.TREADY.next = axi_interface_out.TREADY
                axi_interface_out.TVALID.next = axi_interface_in.TVALID
                axi_interface_out.TDATA.next = axi_interface_in.TDATA

            return assign_signals


        sim_cycles = sum(len(packet) for packet in packet_list) + 1

        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        master_bfm = AxiStreamMasterBFM()
        custom_sources = [(master_bfm.model, (self.clock, self.test_in), {})]

        # Calling several times should work just fine
        master_bfm.add_data(packet_list)
        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, axi_identity, axi_identity,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)

        all_data = [val for packet in trimmed_packets for val in packet]

        self.assertEqual(
            ref_results['axi_interface_out']['packets'], [])

        self.assertEqual(
            ref_results['axi_interface_out']['incomplete_packet'], all_data)

        self.assertEqual(
            dut_results['axi_interface_out']['packets'], [])

        self.assertEqual(
            dut_results['axi_interface_out']['incomplete_packet'], all_data)

    def test_axi_stream_in_argument(self):
        '''It should be possible to set an argument to `axi_stream_in`, in
        which case it is required that argument is an interface providing a
        suitable subset of the AXI4 Stream interface.

        Though it should not be enforced, an `axi_stream_in` interface
        should be driven through a user defined `custom_source` block.

        If the axi stream master sets TVALID to False at any point, this
        should be played back as well.
        '''

        # It seems the way in which sensitivity of initial values is
        # different between Verilog and VHDL. Assigning clock to '1' with
        # verilog means the posedge clock sensitivity is triggered. This seems
        # odd to me but is certainly true for at least the Vivado verilog
        # simulator.
        #
        # Anyway, the upshot of this is we need to choose a start signal that
        # means the result is the same for VHDL and Verilog, so clock should
        # be initialised to 0.

        self.clock = Signal(bool(0))
        self.test_in = AxiStreamInterface()
        self.test_out = AxiStreamInterface()

        max_packet_length = 20
        max_new_packets = 50
        max_val = 2**(8 * self.test_out.bus_width) - 1

        def val_gen():
            # Generates Nones about half the time probability
            val = random.randrange(0, max_val*2)
            if val >= max_val:
                return None
            else:
                return val

        packet_list = [
            [val_gen() for m
             in range(random.randrange(3, max_packet_length))] for n
            in range(random.randrange(3, max_new_packets))]

        self.default_args = {'axi_interface_in': self.test_in,
                             'axi_interface_out': self.test_out,
                             'clock': self.clock}

        self.default_arg_types = {'axi_interface_in': 'axi_stream_in',
                                  'axi_interface_out': 'axi_stream_out',
                                  'clock': 'clock'}

        axi_output_monitor = AxiStreamSlaveBFM()

        @block
        def axi_identity(clock, axi_interface_in, axi_interface_out):

            @always_comb
            def assign_signals():
                axi_interface_in.TREADY.next = axi_interface_out.TREADY
                axi_interface_out.TVALID.next = axi_interface_in.TVALID
                axi_interface_out.TLAST.next = axi_interface_in.TLAST
                axi_interface_out.TDATA.next = axi_interface_in.TDATA

            return assign_signals

        # A test dut block that munges the signal and delays it by a cycle
        @block
        def axi_offset_increment(clock, axi_interface_in, axi_interface_out):

            internal_TVALID = Signal(False)
            internal_TDATA = Signal(intbv(0)[len(axi_interface_in.TDATA):])
            internal_TLAST = Signal(False)

            # This works because axi_interface_out.TREADY is always True.
            @always(clock.posedge)
            def assign_signals():

                internal_TVALID.next = axi_interface_in.TVALID
                internal_TDATA.next = axi_interface_in.TDATA
                internal_TLAST.next = axi_interface_in.TLAST

                axi_interface_in.TREADY.next = True
                axi_interface_out.TVALID.next = internal_TVALID
                axi_interface_out.TLAST.next = internal_TLAST
                axi_interface_out.TDATA.next = internal_TDATA + 1

            return assign_signals

        master_bfm = AxiStreamMasterBFM()
        custom_sources = [
            (master_bfm.model, (self.clock, self.test_in), {}),
            (axi_output_monitor.model, (self.clock, self.test_out),
             {'TREADY_probability': None})]


        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        incremented_trimmed_packets = [
            [val + 1 for val in packet] for packet in trimmed_packets]

        sim_cycles = sum(len(packet) for packet in packet_list) + 3

        master_bfm.add_data(packet_list)

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, axi_offset_increment, axi_identity,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            ref_results['axi_interface_out']['packets'], trimmed_packets)

        self.assertEqual(
            dut_results['axi_interface_out']['packets'],
            incremented_trimmed_packets)

        # Now check the invalids were set appropriately
        flattened_packet_list = [
            val for packet in packet_list for val in packet]

        # We ignore the first 3 cycles in the dut results. This corresponds
        # to the pipeline delay from turn on to visibility at the output
        # for axi_offset_increment above.
        dut_out_invalids = [
            each['TVALID'] for each in
            dut_results['axi_interface_out']['signals'][3:]]

        packet_invalids = [
            False if val is None else True for val in flattened_packet_list]

        self.assertEqual(dut_out_invalids, packet_invalids)

    def test_axi_stream_in_no_TLAST_argument(self):
        '''It should be possible to use an axi stream interface with no TLAST
        for an `axi_stream_in` type argument.
        '''

        self.clock = Signal(bool(1))
        self.test_in = AxiStreamInterface(use_TLAST=False)
        self.test_out = AxiStreamInterface()

        max_packet_length = 20
        max_new_packets = 50
        max_val = 2**(8 * self.test_out.bus_width) - 1

        def val_gen():
            # Generates Nones about half the time probability
            val = random.randrange(0, max_val*2)
            if val >= max_val:
                return None
            else:
                return val

        packet_list = [
            [val_gen() for m
             in range(random.randrange(3, max_packet_length))] for n
            in range(random.randrange(3, max_new_packets))]

        self.default_args = {'axi_interface_in': self.test_in,
                             'axi_interface_out': self.test_out,
                             'clock': self.clock}

        self.default_arg_types = {'axi_interface_in': 'axi_stream_in',
                                  'axi_interface_out': 'axi_stream_out',
                                  'clock': 'clock'}

        @block
        def axi_identity(clock, axi_interface_in, axi_interface_out):

            @always_comb
            def assign_signals():
                axi_interface_in.TREADY.next = axi_interface_out.TREADY
                axi_interface_out.TVALID.next = axi_interface_in.TVALID
                axi_interface_out.TLAST.next = False
                axi_interface_out.TDATA.next = axi_interface_in.TDATA

            return assign_signals

        # A test dut block that munges the signal and delays it by a cycle
        @block
        def axi_offset_increment(clock, axi_interface_in, axi_interface_out):

            internal_TVALID = Signal(False)
            internal_TDATA = Signal(intbv(0)[len(axi_interface_in.TDATA):])

            # This works because axi_interface_out.TREADY is always True.
            @always(clock.posedge)
            def assign_signals():

                internal_TVALID.next = axi_interface_in.TVALID
                internal_TDATA.next = axi_interface_in.TDATA

                axi_interface_in.TREADY.next = True
                axi_interface_out.TVALID.next = internal_TVALID
                axi_interface_out.TLAST.next = False
                axi_interface_out.TDATA.next = internal_TDATA + 1

            return assign_signals

        master_bfm = AxiStreamMasterBFM()
        custom_sources = [(master_bfm.model, (self.clock, self.test_in), {})]


        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        incremented_trimmed_packets = [
            [val + 1 for val in packet] for packet in trimmed_packets]

        sim_cycles = sum(len(packet) for packet in packet_list) + 3

        master_bfm.add_data(packet_list)

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, axi_offset_increment, axi_identity,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)

        flattened_data = [val for packet in trimmed_packets for val in packet]

        self.assertEqual(ref_results['axi_interface_out']['packets'], [])

        self.assertEqual(
            ref_results['axi_interface_out']['incomplete_packet'],
            flattened_data)

        flattened_incremented_data = [
            val for packet in incremented_trimmed_packets for val in packet]

        self.assertEqual(dut_results['axi_interface_out']['packets'], [])

        self.assertEqual(
            dut_results['axi_interface_out']['incomplete_packet'],
            flattened_incremented_data)


    def test_axi_stream_in_with_incomplete_packet(self):
        '''It should be possible for an axi_stream_in argument to handle
        an incomplete final packet.
        '''
        self.clock = Signal(bool(1))
        self.test_in = AxiStreamInterface()
        self.test_out = AxiStreamInterface()

        max_packet_length = 10
        max_new_packets = 20
        max_val = 2**(8 * self.test_out.bus_width) - 1

        def val_gen():
            # Generates Nones about half the time probability
            val = random.randrange(0, max_val*2)
            if val >= max_val:
                return None
            else:
                return val

        packet_list = [
            [val_gen() for m
             in range(random.randrange(3, max_packet_length))] for n
            in range(random.randrange(3, max_new_packets))]

        # force the last packet to always have at least one value in
        # (otherwise the trimming below will break)
        packet_list[-1][0] = random.randrange(0, max_val)

        self.default_args = {'axi_interface_in': self.test_in,
                             'axi_interface_out': self.test_out,
                             'clock': self.clock}

        self.default_arg_types = {'axi_interface_in': 'axi_stream_in',
                                  'axi_interface_out': 'axi_stream_out',
                                  'clock': 'clock'}

        @block
        def axi_identity(clock, axi_interface_in, axi_interface_out):

            @always_comb
            def assign_signals():
                axi_interface_in.TREADY.next = axi_interface_out.TREADY
                axi_interface_out.TVALID.next = axi_interface_in.TVALID
                axi_interface_out.TLAST.next = axi_interface_in.TLAST
                axi_interface_out.TDATA.next = axi_interface_in.TDATA

            return assign_signals

        @block
        def axi_offset_increment(clock, axi_interface_in, axi_interface_out):

            internal_TVALID = Signal(False)
            internal_TDATA = Signal(intbv(0)[len(axi_interface_in.TDATA):])
            internal_TLAST = Signal(False)

            # This works because axi_interface_out.TREADY is always True.
            @always(clock.posedge)
            def assign_signals():

                internal_TVALID.next = axi_interface_in.TVALID
                internal_TDATA.next = axi_interface_in.TDATA
                internal_TLAST.next = axi_interface_in.TLAST

                axi_interface_in.TREADY.next = True
                axi_interface_out.TVALID.next = internal_TVALID
                axi_interface_out.TLAST.next = internal_TLAST
                axi_interface_out.TDATA.next = internal_TDATA + 1

            return assign_signals

        master_bfm = AxiStreamMasterBFM()
        custom_sources = [(master_bfm.model, (self.clock, self.test_in), {})]

        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        incremented_trimmed_packets = [
            [val + 1 for val in packet] for packet in trimmed_packets]

        sim_cycles = sum(len(packet) for packet in packet_list) + 3

        master_bfm.add_data(packet_list, incomplete_last_packet=True)

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, axi_offset_increment, axi_identity,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            ref_results['axi_interface_out']['packets'], trimmed_packets[:-1])

        self.assertEqual(
            dut_results['axi_interface_out']['packets'],
            incremented_trimmed_packets[:-1])

        self.assertEqual(
            ref_results['axi_interface_out']['incomplete_packet'],
            trimmed_packets[-1])

        self.assertEqual(
            dut_results['axi_interface_out']['incomplete_packet'],
            incremented_trimmed_packets[-1])

    def test_all_argument_types_and_args_have_same_keys(self):
        '''The arg dict should have the same keys as the arg types dict
        '''
        self.assertRaisesRegex(
            ValueError, 'Invalid argument or argument type keys',
            self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': 'custom', 'reset': 'custom',
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

    def test_boolean_data_case(self):
        '''The test object with identity factories and a boolean signal
        should pass every time'''

        sim_cycles = 30
        self.test_in = Signal(bool(0))
        self.test_out = Signal(bool(0))

        self.default_args['test_input'] = self.test_in
        self.default_args['test_output'] = self.test_out

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

    def test_single_bit_vector_data_case(self):
        '''The test object with identity factories and a single bit intbv
        (i.e. not a bool type) should pass every time'''

        sim_cycles = 30
        self.test_in = Signal(intbv(0)[1:])
        self.test_out = Signal(intbv(0)[1:])

        self.default_args['test_input'] = self.test_in
        self.default_args['test_output'] = self.test_out

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

    def test_disagreeing_outputs(self):
        '''When the factories disagree, the results should not be the same.
        '''

        sim_cycles = 30

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        N = 20
        n = 8
        input_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for _ in range(1, N+1)]

        output_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for _ in range(1, N+1)]

        args['test_input_list'] = input_signal_list
        args['test_output_list'] = output_signal_list
        arg_types['test_input_list'] = 'random'
        arg_types['test_output_list'] = 'output'

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(intbv(0, min=min_val, max=max_val))

        args['test_input_interface'] = Interface()
        args['test_output_interface'] = Interface()
        arg_types['test_input_interface'] = 'random'
        arg_types['test_output_interface'] = 'output'

        @block
        def identity_factory(
            test_input, test_input_list, test_input_interface,
            test_output, test_output_list, test_output_interface,
            reset, clock):

            @always_seq(clock.posedge, reset=reset)
            def identity():

                test_output.next = test_input

                for n in range(N):
                    test_output_list[n].next = test_input_list[n]

                test_output_interface.a.next = test_input_interface.a
                test_output_interface.b.next = test_input_interface.b


            return identity

        @block
        def not_identity_factory(
            test_input, test_input_list, test_input_interface,
            test_output, test_output_list, test_output_interface,
            reset, clock):

            @always_seq(clock.posedge, reset=reset)
            def not_identity():

                test_output.next = test_input - test_input

                for n in range(N):
                    test_output_list[n].next = (
                        test_input_list[n] - test_input_list[n])

                test_output_interface.a.next = (
                    test_input_interface.a - test_input_interface.a)
                test_output_interface.b.next = (
                    test_input_interface.b - test_input_interface.b)


            return not_identity


        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, not_identity_factory, identity_factory,
            args, arg_types)

        for signal in (
            'test_output', 'test_output_interface', 'test_output_list'):
            self.assertNotEqual(dut_results[signal], ref_results[signal])

    def test_simulation_cleans_up(self):
        '''The simulation should clean up afterwards.

        Sensitivity lists and so on on the signals should be cleared.
        '''

        sim_cycles = 30

        args = copy.copy(self.default_args)
        arg_types = copy.copy(self.default_arg_types)

        @block
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

        dut_results, ref_results = self.construct_and_simulate(
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

        custom_sources = [
            (random_source, (test_input, clock, reset), {'seed':seed})]
        _, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)

        # Mess with the signal states
        test_input._val = intbv(5, min=test_input.min, max=test_input.max)

        custom_sources = [
            (random_source, (test_input, clock, reset), {'seed':seed})]
        _, ref_results2 = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args, self.default_arg_types,
            custom_sources=custom_sources)


        for signal in ref_results:
            # The messing should have made no difference to the sim result.
            self.assertEqual(ref_results[signal], ref_results2[signal])



    def test_dut_factory_returning_invalid_raises(self):
        '''If the dut factory returns something invalid, a
        BlockError should be raised.

        The BlockError should contain information about which factory is
        failing. Failing to return from the factory is a common mistake.
        '''

        @block
        def none_factory(**kwargs):
            return None

        self.assertRaisesRegex(BlockError, 'The dut factory returned an '
                               'invalid object',
                               self.construct_and_simulate, 30,
                               none_factory, self.identity_factory,
                               self.default_args, self.default_arg_types)

    def test_ref_factory_returning_invalid_raises(self):
        '''If the ref factory returns something invalid, a
        BlockError should be raised.

        The BlockError should contain information about which factory is
        failing. Failing to return from the factory is a common mistake.
        '''

        @block
        def none_factory(**kwargs):
            return None

        self.assertRaisesRegex(BlockError, 'The ref factory returned an '
                               'invalid object',
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

        @block
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
        # Also we record one cycl#e delayed from the sim_checker mock above,
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


    def test_interface_with_non_signal_attribute(self):
        '''It should be possible to work with interfaces that contain an
        attribute that is not a Signal.'''

        args = self.default_args.copy()

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                self.a = 'not a signal'
                self.b = 'not a signal'
                self.c = 'not a signal'
                self.d = 'not a signal'
                self.e = 'not a signal'
                self.f = 'not a signal'
                self.g = 'not a signal'
                self.h = 'not a signal'
                self.sig = Signal(intbv(0, min=min_val, max=max_val))

        @block
        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.sig.val))

                test_output.sig.next = test_input.sig

            return identity

        args['test_input'] = Interface()
        args['test_output'] = Interface()

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
        # Also we record one cycl#e delayed from the sim_checker mock above,
        # so we need to offset left by that too.
        dut_expected_mock_calls = [
            mock.call(each['sig'])
            for each in dut_results['test_output'][self.reset_cycles:][1:]]

        ref_expected_mock_calls = [
            mock.call(each['sig'])
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

    def test_unused_signal_in_interface(self):
        '''It should be possible to work with interfaces that contain a
        Signal that is not declared in the arg types, in which case it is
        simply ignored.'''

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                self.unused_sig = Signal(intbv(0)[10:])
                self.sig = Signal(intbv(0, min=min_val, max=max_val))

        @block
        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    self.sim_checker(copy.copy(test_input.sig.val))

                test_output.sig.next = test_input.sig

            return identity

        args['test_input'] = Interface()
        args['test_output'] = Interface()

        arg_types['test_output'] = {'sig': 'output'}
        arg_types['test_input'] = {'sig': 'random'}

        sim_cycles = 31

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory,
            args, arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_signal_list_arg(self):
        '''It should be possible to work with lists of signals.

        If the list contains non-signals, they are ignored.
        '''

        args = self.default_args.copy()

        N = 20
        input_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for n in range(1, N+1)]

        # In the test we stick a non-signal at the end of the list to
        # make sure it is handled ok.
        input_signal_list.append('not a signal')

        output_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for n in range(1, N+1)]

        output_signal_list.append('not a signal')

        @block
        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                if __debug__:
                    # The last value in the list is not a Signal
                    input_vals = (
                        copy.copy(each.val) for each in test_input[:-1])

                    self.sim_checker(*input_vals)

                for i in range(N):
                    test_output[i].next = test_input[i]

            return identity

        args['test_input'] = input_signal_list
        args['test_output'] = output_signal_list

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
            mock.call(*(each_sig for each_sig in each))
            for each in dut_results['test_output'][self.reset_cycles:][1:]]

        ref_expected_mock_calls = [
            mock.call(*(each_sig for each_sig in each))
            for each in dut_results['test_output'][self.reset_cycles:][1:]]

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
            self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom', 'test_output': 'custom', 'reset': 'INVALID',
             'clock': 'custom'})

        class Interface(object):
            def __init__(self):
                self.a = Signal(intbv(0, min=-1000, max=1000))

        self.default_args['test_output'] = Interface()

        self.assertRaisesRegex(
            ValueError, 'Invalid argument or argument types',
            self.construct_and_simulate, 30,
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
            self.construct_and_simulate, 30,
            self.identity_factory, self.identity_factory, self.default_args,
            {'test_input': 'custom',
             'test_output': {'a': 'output', 'b': 'output'},
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
        @block
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

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory,
            args, arg_types)

        # Neither the inputs nor the outputs should be the same signal
        self.assertIsNot(signals[0]['test_output.b'],
                         signals[1]['test_output.b'])
        self.assertIsNot(signals[0]['test_input.a'],
                         signals[1]['test_input.a'])
        self.assertIsNot(signals[0]['test_output.a'],
                         signals[1]['test_output.a'])
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

        @block
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

        dut_results, ref_results = self.construct_and_simulate(
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
                self.reset = ResetSignal(bool(0), active=1, isasync=False)

        @block
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

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory,
            args, arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

        # Also test the custom reset
        arg_types['test_input'] = {'a': 'random', 'reset': 'custom_reset'}

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory,
            args, arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])



    def test_failing_case(self):
        '''The test object with wrong factories should have wrong output'''

        @block
        def flipper_factory(test_input, test_output, reset, clock):
            '''Flips the output bits
            '''
            @always_seq(clock.posedge, reset=reset)
            def flipper():
                test_output.next = ~test_input

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

    def test_non_signal_ignored_in_output(self):
        '''There should be a non-signal arg type for args that are not signals.

        Such arguments should have no representation in the results
        dictionaries after simulation.
        '''
        @block
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

    def test_StopSimulation_case(self):
        '''It should be possible to call StopSimulation to truncate the sim
        time
        '''

        sim_cycles = 30

        @block
        def stopper(clock):

            count = [0]
            # We count in the middle of a cycle
            @always(clock.negedge)
            def inst():
                count[0] += 1

                if count[0] > 20:
                    raise StopSimulation

            return inst

        custom_source = (stopper, (self.default_args['clock'],), {})

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args, self.default_arg_types,
            custom_sources=[custom_source])


        for signal in dut_results:
            self.assertTrue(len(ref_results[signal]) == 20)
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_None_cycles_case(self):
        '''It should be possible to set cycles to None during a simulation,
        in which the case the simulation will run until StopSimulation is
        raised.
        '''

        sim_cycles = None

        @block
        def stopper(clock):

            count = [0]
            # We count in the middle of a cycle
            @always(clock.negedge)
            def inst():
                count[0] += 1

                if count[0] > 20:
                    raise StopSimulation

            return inst

        custom_source = (stopper, (self.default_args['clock'],), {})

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, self.identity_factory, self.identity_factory,
            self.default_args, self.default_arg_types,
            custom_sources=[custom_source])


        for signal in dut_results:
            self.assertTrue(len(ref_results[signal]) == 20)
            self.assertEqual(dut_results[signal], ref_results[signal])


class TestSynchronousTestClass(CosimulationTestMixin, TestCase):
    '''The SynchronousTest class should provide the core of the cosimulation.

    It should take four arguments: a pair of instance factories, a dict of
    arguments, and dict of argument types (that tell the test class how to
    handle the arguments, be they inputs or outputs).
    '''

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types,
        **kwargs):

        try:
            vcd_name = kwargs['vcd_name']
            del kwargs['vcd_name']
        except KeyError:
            vcd_name = None

        test_obj = SynchronousTest(
            dut_factory, ref_factory, args, arg_types, **kwargs)

        return test_obj.cosimulate(sim_cycles, vcd_name=vcd_name)

    def test_axi_stream_out_with_multiple_cosimulate_calls(self):
        '''If multiple calls are made to cosimulate, the signals that are
        set to be axi_stream_out should not contain outputs from previous
        calls.
        '''
        self.clock = Signal(bool(1))
        self.test_in = AxiStreamInterface()
        self.test_out = AxiStreamInterface()

        max_packet_length = 20
        max_new_packets = 50
        max_val = 2**(8 * self.test_out.bus_width) - 1

        def val_gen():
            # Generates Nones about half the time probability
            val = random.randrange(0, max_val*2)
            if val >= max_val:
                return None
            else:
                return val

        packet_list = [
            [val_gen() for m
             in range(random.randrange(3, max_packet_length))] for n
            in range(random.randrange(3, max_new_packets))]

        self.default_args = {'axi_interface_in': self.test_in,
                             'axi_interface_out': self.test_out,
                             'clock': self.clock}

        self.default_arg_types = {'axi_interface_in': 'axi_stream_in',
                                  'axi_interface_out': 'axi_stream_out',
                                  'clock': 'clock'}

        @block
        def axi_identity(clock, axi_interface_in, axi_interface_out):

            @always_comb
            def assign_signals():
                axi_interface_in.TREADY.next = axi_interface_out.TREADY
                axi_interface_out.TVALID.next = axi_interface_in.TVALID
                axi_interface_out.TLAST.next = axi_interface_in.TLAST
                axi_interface_out.TDATA.next = axi_interface_in.TDATA

            return assign_signals

        master_bfm = AxiStreamMasterBFM()
        custom_sources = [(master_bfm.model, (self.clock, self.test_in), {})]

        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        incremented_trimmed_packets = [
            [val + 1 for val in packet] for packet in trimmed_packets]

        sim_cycles = sum(len(packet) for packet in packet_list) + 1

        test_obj = SynchronousTest(axi_identity, axi_identity,
                                   self.default_args, self.default_arg_types,
                                   custom_sources=custom_sources)

        for n in range(3):
            master_bfm.add_data(packet_list)

            dut_results, ref_results = test_obj.cosimulate(sim_cycles)

            self.assertEqual(
                ref_results['axi_interface_out']['packets'], trimmed_packets)

            self.assertEqual(
                dut_results['axi_interface_out']['packets'], trimmed_packets)

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
        provide a block upon which `convert()` can be called.

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

        @block
        def dut(test_input, test_input2, test_output, reset, clock):

            @always_seq(self.clock.posedge, reset)
            def test_dut():

                test_output.next = test_input + test_input2

            return test_dut

        test_obj = SynchronousTest(dut, dut, args, arg_types)

        tmp_dir = tempfile.mkdtemp()
        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(simulated_input_cycles)

        try:

            top = test_obj.dut_convertible_top(tmp_dir)
            top.convert(hdl='VHDL', path=tmp_dir)

            top2 = test_obj.dut_convertible_top(tmp_dir)
            top2.convert(hdl='Verilog', path=tmp_dir)

            self.assertTrue(os.path.exists(output_file))

        finally:
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

        @block
        def dut(test_output, reset, clock):

            @always_seq(self.clock.posedge, reset)
            def test_dut():
                test_output.next = 1

            return test_dut

        test_obj = SynchronousTest(dut, dut, args, arg_types)

        tmp_dir = tempfile.mkdtemp()

        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(simulated_input_cycles)

        try:
            top = test_obj.dut_convertible_top(tmp_dir)
            top.convert(hdl='VHDL', path=tmp_dir)

            self.assertTrue(os.path.exists(output_file))

        finally:
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

        @block
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

        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(simulated_input_cycles)

        try:
            top = test_obj.dut_convertible_top(tmp_dir)
            top.convert(hdl='VHDL', path=tmp_dir)

            self.assertTrue(os.path.exists(output_file))

        finally:
            shutil.rmtree(tmp_dir)

    def test_dut_convertible_top_with_signal_list(self):
        '''Convertible top duts with signal lists should be supported.

        The dut_convertible_top method should be able to handle signal lists.
        Non-signals in the list should be ignored, and the signals can be
        of different sizes.
        '''
        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        N = 5
        missing_sig_idx = 3
        input_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for n in range(1, N+1)]

        input_signal_list[missing_sig_idx] = 'not a signal'

        output_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for n in range(1, N+1)]

        output_signal_list[missing_sig_idx] = 'also not a signal'

        @block
        def dut(test_input, test_output, reset, clock):
            # We're dealing with the more general case of arbitrary
            # values in the list.
            # The specific problem of lists in the convertible code is a
            # MyHDL problem.

            @block
            def sig_copy(single_test_input, single_test_output, reset, clock):

                @always_seq(clock.posedge, reset=reset)
                def sig_copy_inst():
                    single_test_output.next = single_test_input

                return sig_copy_inst

            instances = []
            for i in range(N):
                if i is not missing_sig_idx:
                    instances.append(
                        sig_copy(test_input[i], test_output[i], reset, clock))

            return instances

        args['test_input'] = input_signal_list
        args['test_output'] = output_signal_list

        simulated_input_cycles = 20

        test_obj = SynchronousTest(dut, dut, args, arg_types)

        tmp_dir = tempfile.mkdtemp()

        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(simulated_input_cycles)

        try:
            top = test_obj.dut_convertible_top(tmp_dir)
            top.convert(hdl='VHDL', path=tmp_dir)

            self.assertTrue(os.path.exists(output_file))

        finally:
            shutil.rmtree(tmp_dir)

    def test_ref_uses_original_output(self):
        '''It should be the ref_factory that gets the original output signal.

        This is important as it allows the output signal to be used by a
        custom source, and it is the reference that is used.
        '''

        @block
        def useless_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def useless():
                # Include test_input to stop complaints about undriven signal
                test_output.next = 0 * test_input

            return useless

        mod_max = 20
        @block
        def _custom_source(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def custom():
                # Adds one to the output signal
                test_input.next = test_output + 1

            return custom

        custom_source = [
            _custom_source,
            (self.default_args['test_input'],
             self.default_args['test_output'],
             self.default_args['reset'],
             self.default_args['clock']), {}]

        sim_cycles = 20
        dut_results, ref_results = self.construct_and_simulate(
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
        @block
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

        output_file = os.path.join(tmp_dir, 'dut_convertible_top.vhd')

        test_obj.cosimulate(sim_cycles)

        try:
            top = test_obj.dut_convertible_top(tmp_dir)
            top.convert(hdl='VHDL', path=tmp_dir)

            self.assertTrue(os.path.exists(output_file))

        finally:
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
            {'test_input': 'custom', 'test_output': 'output',
             'reset': 'init_reset', 'clock': 'clock'})

        self.assertIs(dut_results, None)



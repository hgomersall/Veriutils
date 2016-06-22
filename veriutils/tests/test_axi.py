
from unittest import TestCase
from veriutils import *
from myhdl import *
import myhdl

from collections import deque
import random

import os
import tempfile
import shutil


class TestAxiStreamInterface(TestCase):
    '''There should be an AXI4 Stream object that encapsulates all the AXI
    stream signals.
    '''
    def test_bus_width_property(self):
        '''There should be a bus width property which is an integer set
        by the first position ``bus_width`` keyword argument, defaulting to 4.
        '''
        interface = AxiStreamInterface()
        self.assertEqual(interface.bus_width, 4)

        interface = AxiStreamInterface(8)
        self.assertEqual(interface.bus_width, 8)

        interface = AxiStreamInterface('6')
        self.assertEqual(interface.bus_width, 6)

        interface = AxiStreamInterface(bus_width=16)
        self.assertEqual(interface.bus_width, 16)

    def test_TDATA(self):
        '''There should be a TDATA attribute that is an unsigned intbv Signal
        that is 8*bus_width bits wide.
        '''
        interface = AxiStreamInterface()
        self.assertTrue(isinstance(interface.TDATA, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TDATA._val, intbv))
        self.assertEqual(len(interface.TDATA._val), interface.bus_width*8)

        interface = AxiStreamInterface(bus_width='5')
        self.assertEqual(len(interface.TDATA._val), interface.bus_width*8)

    def test_TSTRB(self):
        '''There should be an optional TSTRB attribute that is an unsigned
        intbv Signal that is bus_width bits wide and is full range.
        '''
        # The default case is not to include it
        interface = AxiStreamInterface()
        self.assertFalse(hasattr(interface, 'TSTRB'))

        interface = AxiStreamInterface(use_TSTRB=True)
        self.assertTrue(isinstance(interface.TSTRB, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TSTRB._val, intbv))
        self.assertEqual(len(interface.TSTRB._val), interface.bus_width)
        self.assertEqual(interface.TSTRB.min, 0)
        self.assertEqual(interface.TSTRB.max, 2**(interface.bus_width))

        interface = AxiStreamInterface(bus_width='6', use_TSTRB=True)
        self.assertEqual(len(interface.TSTRB._val), interface.bus_width)

    def test_TKEEP(self):
        '''There should be an optional TKEEP attribute that is an unsigned
        intbv Signal that is bus_width bits wide and is full range.
        '''
        # The default case is not to include it
        interface = AxiStreamInterface()
        self.assertFalse(hasattr(interface, 'TKEEP'))

        interface = AxiStreamInterface(use_TKEEP=True)
        self.assertTrue(isinstance(interface.TKEEP, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TKEEP._val, intbv))
        self.assertEqual(len(interface.TKEEP._val), interface.bus_width)
        self.assertEqual(interface.TKEEP.min, 0)
        self.assertEqual(interface.TKEEP.max, 2**(interface.bus_width))

        interface = AxiStreamInterface(bus_width=8, use_TKEEP=True)
        self.assertEqual(len(interface.TKEEP._val), interface.bus_width)

    def test_TVALID(self):
        '''There should be a TVALID attribute that is a boolean Signal.
        '''
        interface = AxiStreamInterface()
        self.assertTrue(isinstance(interface.TVALID, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TVALID._val, (intbv, bool)))
        self.assertEqual(len(interface.TVALID), 1)

    def test_TREADY(self):
        '''There should be a TREADY attribute that is a boolean Signal.
        '''
        interface = AxiStreamInterface()
        self.assertTrue(isinstance(interface.TREADY, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TREADY._val, (intbv, bool)))
        self.assertEqual(len(interface.TREADY), 1)

    def test_TLAST(self):
        '''There should be a TLAST attribute that is a boolean Signal.
        '''
        interface = AxiStreamInterface()
        self.assertTrue(isinstance(interface.TLAST, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TLAST._val, (intbv, bool)))
        self.assertEqual(len(interface.TLAST), 1)

    def test_TID_width_property(self):
        '''There should be a TID_width property which is set by the
        ``TID_width`` keyword argument, the default of which is ``None``.
        '''
        interface = AxiStreamInterface()
        self.assertIs(interface.TID_width, None)

        interface = AxiStreamInterface(TID_width=10)
        self.assertEqual(interface.TID_width, 10)

        interface = AxiStreamInterface(TID_width='6')
        self.assertEqual(interface.TID_width, 6)

    def test_TID(self):
        '''There should be an optional TID attribute that is an intbv Signal
        of width set by the ``TID_width`` argument. If ``TID_width`` is
        ``None`` or not set then the attribute should not exist.
        '''
        interface = AxiStreamInterface()
        with self.assertRaises(AttributeError):
            interface.TID

        interface = AxiStreamInterface(TID_width=None)
        with self.assertRaises(AttributeError):
            interface.TID

        interface = AxiStreamInterface(TID_width=10)
        self.assertTrue(isinstance(interface.TID, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TID._val, intbv))
        self.assertEqual(len(interface.TID._val), interface.TID_width)

    def test_TDEST_width_property(self):
        '''There should be a TDEST_width property which is set by the
        ``TDEST_width`` keyword argument, the default of which is ``None``.
        '''
        interface = AxiStreamInterface()
        self.assertIs(interface.TDEST_width, None)

        interface = AxiStreamInterface(TDEST_width=10)
        self.assertEqual(interface.TDEST_width, 10)

        interface = AxiStreamInterface(TDEST_width='6')
        self.assertEqual(interface.TDEST_width, 6)

    def test_TDEST(self):
        '''There should be an optional TDEST attribute that is an intbv Signal
        of width set by the ``TDEST_width`` argument. If ``TDEST_width`` is
        ``None`` or not set then the attribute should not exist.
        '''
        interface = AxiStreamInterface()
        with self.assertRaises(AttributeError):
            interface.TDEST

        interface = AxiStreamInterface(TDEST_width=None)
        with self.assertRaises(AttributeError):
            interface.TDEST

        interface = AxiStreamInterface(TDEST_width=10)
        self.assertTrue(isinstance(interface.TDEST, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TDEST._val, intbv))
        self.assertEqual(len(interface.TDEST._val), interface.TDEST_width)

    def test_TUSER_width_property(self):
        '''There should be a TUSER_width property which is set by the
        ``TUSER_width`` keyword argument, the default of which is ``None``.
        '''
        interface = AxiStreamInterface()
        self.assertIs(interface.TUSER_width, None)

        interface = AxiStreamInterface(TUSER_width=10)
        self.assertEqual(interface.TUSER_width, 10)

        interface = AxiStreamInterface(TUSER_width='6')
        self.assertEqual(interface.TUSER_width, 6)

    def test_TUSER(self):
        '''There should be an optional TUSER attribute that is an intbv Signal
        of width set by the ``TUSER_width`` argument. If ``TUSER_width`` is
        ``None`` or not set then the attribute should not exist.
        '''
        interface = AxiStreamInterface()
        with self.assertRaises(AttributeError):
            interface.TUSER

        interface = AxiStreamInterface(TUSER_width=None)
        with self.assertRaises(AttributeError):
            interface.TUSER

        interface = AxiStreamInterface(TUSER_width=10)
        self.assertTrue(isinstance(interface.TUSER, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TUSER._val, intbv))
        self.assertEqual(len(interface.TUSER._val), interface.TUSER_width)

    def test_TVALID_init(self):
        '''It should be possible to set an initial value for TVALID through
        an __init__ argument, TVALID_init.
        '''
        interface = AxiStreamInterface()
        self.assertEqual(interface.TVALID, 0)

        interface = AxiStreamInterface(TVALID_init=True)
        self.assertEqual(interface.TVALID, 1)

        interface = AxiStreamInterface(TVALID_init=1)
        self.assertEqual(interface.TVALID, 1)

        interface = AxiStreamInterface(TVALID_init=False)
        self.assertEqual(interface.TVALID, 0)

    def test_TREADY_init(self):
        '''It should be possible to set an initial value for TREADY through
        an __init__ argument, TREADY_init.
        '''
        interface = AxiStreamInterface()
        self.assertEqual(interface.TREADY, 0)

        interface = AxiStreamInterface(TREADY_init=True)
        self.assertEqual(interface.TREADY, 1)

        interface = AxiStreamInterface(TREADY_init=1)
        self.assertEqual(interface.TREADY, 1)

        interface = AxiStreamInterface(TREADY_init=False)
        self.assertEqual(interface.TREADY, 0)

def _get_next_val(packet_list, instance_data):

    try:
        try:
            assert isinstance(instance_data['packet'], deque)
            next_val = instance_data['packet'].popleft()
        except KeyError:
            raise IndexError

    except IndexError:
        instance_data['packet'] = []
        while len(instance_data['packet']) == 0:
            if len(packet_list) == 0:
                return None

            else:
                instance_data['packet'] = packet_list.popleft()

        next_val = instance_data['packet'].popleft()

    return next_val

def _add_packets_to_stream(stream, packet_list):
    '''Adds the supplied packets to the stream and returns them.
    '''
    packet_list = deque(deque(packet) for packet in packet_list)
    stream.add_data(packet_list)
    return packet_list

def _add_random_packets_to_stream(
    stream, max_packet_length, max_new_packets, max_val):
    '''Adds a load of random data to the stream and returns
    the list of added packets.

    Each packet is of random length between 0 and max_packet_length
    and there are a random number between 0 and max_new_packets of
    them.
    '''
    packet_list = deque(
        [deque([random.randrange(0, max_val) for m
                in range(random.randrange(0, max_packet_length))]) for n
         in range(random.randrange(0, max_new_packets))])

    return _add_packets_to_stream(stream, packet_list)

def _generate_random_packets_with_Nones(
    data_byte_width, max_packet_length, max_new_packets):

    def val_gen(data_byte_width):
        # Generates Nones about half the time probability
        val = random.randrange(0, 2**(8 * data_byte_width))
        if val > 2**(8 * data_byte_width - 1):
            return None
        else:
            return val

    packet_list = deque(
        [deque([
            val_gen(data_byte_width) for m
            in range(random.randrange(0, max_packet_length))]) for n
            in range(random.randrange(0, max_new_packets))])

    total_data_len = sum(len(each) for each in packet_list)

    None_trimmed_packet_list = [
        [val for val in packet if val is not None] for packet in
        packet_list]

    trimmed_packets = [
        packet for packet in None_trimmed_packet_list if len(packet) > 0]

    return packet_list, trimmed_packets, total_data_len

class TestAxiStreamMasterBFM(TestCase):
    '''There should be an AXI Stream Bus Functional Model that implements
    a programmable AXI4 Stream protocol from the master side.
    '''

    def setUp(self):

        self.data_byte_width = 8
        self.max_packet_length = 10
        self.max_new_packets = 5
        self.max_rand_val = 2**(8 * self.data_byte_width)

        self.stream = AxiStreamMasterBFM()
        self.interface = AxiStreamInterface(self.data_byte_width)
        clock = Signal(bool(0))

        self.args = {'clock': clock}
        self.arg_types = {'clock': 'clock'}

    def test_single_stream_data(self):
        '''It should be possible to set the data for a single stream.

        When data is available, TVALID should be set. When TVALID is not set
        it should indicate the data is to be ignored.
        '''

        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {}
            @always(clock.posedge)
            def inst():
                self.interface.TREADY.next = True

                if self.interface.TVALID:
                    next_expected_val = _get_next_val(packet_list, inst_data)

                    assert self.interface.TDATA == next_expected_val
                    cycle_count[0] += 1

                else:
                    # Stop if there is nothing left to process
                    if len(packet_list) == 0:
                        raise StopSimulation

                    elif all(len(each) == 0 for each in packet_list):
                        raise StopSimulation


            return inst, bfm

        for n in range(30):
            packet_list = _add_random_packets_to_stream(
                self.stream, self.max_packet_length, self.max_new_packets,
                self.max_rand_val)

            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertEqual(total_data_len, cycle_count[0])

    def test_TLAST_asserted_correctly(self):
        '''TLAST should be raised for the last word in a packet and must
        be deasserted before the beginning of the next packet.

        When data is available, TVALID should be set. When TVALID is not set
        it should indicate the data is to be ignored.
        '''

        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {}
            @always(clock.posedge)
            def inst():
                self.interface.TREADY.next = True

                if self.interface.TVALID:
                    next_expected_val = _get_next_val(packet_list, inst_data)

                    if len(inst_data['packet']) == 0:
                        # The last word in the packet
                        assert self.interface.TLAST
                    else:
                        assert not self.interface.TLAST

                    cycle_count[0] += 1

                else:
                    # TVALID being false is a condition of the test
                    assert not self.interface.TVALID

                    # Stop if there is nothing left to process
                    if len(packet_list) == 0:
                        raise StopSimulation

                    elif all(len(each) == 0 for each in packet_list):
                        raise StopSimulation

            return inst, bfm

        #run the test several times to better sample the test space
        for n in range(30):
            packet_list = _add_random_packets_to_stream(
                self.stream, self.max_packet_length, self.max_new_packets,
                self.max_rand_val)
            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertEqual(total_data_len, cycle_count[0])

    def test_add_new_packets_during_simulation(self):
        '''It should be possible to add packets whilst a simulation is running
        '''

        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {
                'available_delay': random.randrange(0, 10),
                'tried_adding_during_run': False}

            @always(clock.posedge)
            def inst():
                self.interface.TREADY.next = True
                if self.interface.TVALID:
                    next_expected_val = _get_next_val(packet_list, inst_data)

                    assert self.interface.TDATA == next_expected_val
                    if len(inst_data['packet']) == 0:
                        assert self.interface.TLAST
                    else:
                        assert not self.interface.TLAST

                    if not inst_data['tried_adding_during_run']:
                        if inst_data['available_delay'] == 0:
                            new_packets = add_packets_to_stream()

                            packet_list.extend(new_packets)
                            total_data_len[0] += (
                                sum(len(each) for each in new_packets))

                            inst_data['tried_adding_during_run'] = True

                        else:
                            inst_data['available_delay'] -= 1

                    cycle_count[0] += 1

                else:

                    if len(packet_list) == 0:
                        raise StopSimulation

                    elif all(len(each) == 0 for each in packet_list):
                        raise StopSimulation


            return inst, bfm

        def checks():
            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            # A few test sanity checks.
            self.assertEqual(sum(len(packet) for packet in packet_list), 0)
            self.assertTrue(cycle_count > total_data_len[0])

        # A few explicit cases
        explicit_cases = (
            [[],[],[]],
            [[10], [], [10]],
            [[], [], [10]],
            [[10], [], []])

        for _packet_list in explicit_cases:
            add_packets_to_stream = lambda: _add_packets_to_stream(
                self.stream, _packet_list)
            packet_list = add_packets_to_stream()
            total_data_len = [0]
            cycle_count = [0]
            checks()

        #run the test several times to better sample test space
        add_packets_to_stream = lambda: _add_random_packets_to_stream(
            self.stream, self.max_packet_length, self.max_new_packets,
            self.max_rand_val)

        for n in range(30):
            packet_list = add_packets_to_stream()
            total_data_len = [sum(len(each) for each in packet_list)]
            cycle_count = [0]
            checks()

    def test_add_new_packets_after_data_exhausted(self):
        '''It should be possible to add packets when the existing data is
        exhausted.
        '''

        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {
                'empty_delay': random.randrange(0, 10),
                'tried_adding_when_empty': False}

            @always(clock.posedge)
            def inst():
                self.interface.TREADY.next = True
                if self.interface.TVALID:
                    next_expected_val = _get_next_val(packet_list, inst_data)

                    assert self.interface.TDATA == next_expected_val
                    if len(inst_data['packet']) == 0:
                        assert self.interface.TLAST
                    else:
                        assert not self.interface.TLAST

                    cycle_count[0] += 1

                else:
                    if not inst_data['tried_adding_when_empty']:
                        if inst_data['empty_delay'] == 0:
                            new_packets = add_packets_to_stream()

                            packet_list.extend(new_packets)

                            total_data_len[0] += (
                                sum(len(each) for each in new_packets))

                            inst_data['tried_adding_when_empty'] = True

                        else:
                            inst_data['empty_delay'] -= 1

                    elif len(packet_list) == 0:
                        raise StopSimulation

                    elif all(len(each) == 0 for each in packet_list):
                        raise StopSimulation


            return inst, bfm

        def checks():
            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            # A few test sanity checks.
            self.assertEqual(sum(len(packet) for packet in packet_list), 0)
            self.assertTrue(cycle_count > total_data_len[0])

        # A few explicit edge cases
        explicit_cases = (
            [[],[],[]],
            [[10], [], [10]],
            [[], [], [10]],
            [[10], [], []],
            [[10], [20], [30]])

        for _packet_list in (explicit_cases):
            add_packets_to_stream = lambda: _add_packets_to_stream(
                self.stream, _packet_list)
            packet_list = add_packets_to_stream()
            total_data_len = [0]
            cycle_count = [0]
            checks()

        #run the test several times to better sample test space
        add_packets_to_stream = lambda: _add_random_packets_to_stream(
            self.stream, self.max_packet_length, self.max_new_packets,
            self.max_rand_val)

        for n in range(30):
            packet_list = add_packets_to_stream()
            total_data_len = [sum(len(each) for each in packet_list)]
            cycle_count = [0]
            checks()

    def test_run_new_uninitialised_model(self):
        '''It should be possible run the simulation without first adding any
        data to the model'''

        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            @always(clock.posedge)
            def inst():
                self.interface.TREADY.next = True

                # Nothing should be available
                assert not self.interface.TVALID

            return inst, bfm

        # Make sure we have a new stream
        self.stream = AxiStreamMasterBFM()
        myhdl_cosimulation(
            10, None, testbench, self.args, self.arg_types)

    def test_TREADY_False_pauses_valid_transfer(self):
        '''When the slave sets TREADY to False, no data should be sent, but
        the data should not be lost. Transfers should continue again as soon
        as TREADY is True.
        '''

        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {'packet': deque([])}
            @always(clock.posedge)
            def inst():

                if random.random() < ready_probability:
                    # Set TREADY True
                    self.interface.TREADY.next = True
                else:
                    # Set TREADY False
                    self.interface.TREADY.next = False


                if self.interface.TVALID and self.interface.TREADY:
                    next_expected_val = _get_next_val(packet_list, inst_data)

                    assert self.interface.TDATA == next_expected_val
                    cycle_count[0] += 1

                else:
                    # Stop if there is nothing left to process
                    if len(inst_data['packet']) == 0:
                        if (len(packet_list) == 0):
                            raise StopSimulation

                        elif all(len(each) == 0 for each in packet_list):
                            raise StopSimulation



            return inst, bfm

        for n in range(5):
            ready_probability = 0.2 * (n + 1)

            packet_list = _add_random_packets_to_stream(
                self.stream, self.max_packet_length, self.max_new_packets,
                self.max_rand_val)

            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            dut_output, ref_output = myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertTrue(cycle_count[0] == total_data_len)

    def test_None_in_packets_sets_TVALID_False(self):
        '''Inserting a ``None`` into a packet should cause a cycle in which
        the ``TVALID`` flag is set ``False``.
        '''
        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {'first_run': True,
                         'packet': deque([])}

            @always(clock.posedge)
            def inst():
                self.interface.TREADY.next = True

                if inst_data['first_run']:
                    assert not self.interface.TVALID
                    inst_data['first_run'] = False

                else:
                    next_expected_val = _get_next_val(packet_list, inst_data)

                    if next_expected_val is None:
                        assert not self.interface.TVALID
                        cycle_count[0] += 1

                    else:
                        assert self.interface.TVALID
                        assert self.interface.TDATA == next_expected_val
                        cycle_count[0] += 1

                # Stop if there is nothing left to process
                if len(inst_data['packet']) == 0:
                    if (len(packet_list) == 0):
                        raise StopSimulation

                    elif all(len(each) == 0 for each in packet_list):
                        raise StopSimulation

            return inst, bfm

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        def val_gen(data_byte_width):
            # Generates Nones about half the time probability
            val = random.randrange(0, 2**(8 * data_byte_width))
            if val > 2**(8 * data_byte_width - 1):
                return None
            else:
                return val

        for n in range(30):

            packet_list = deque(
                [deque([
                    val_gen(self.data_byte_width) for m
                    in range(random.randrange(0, max_packet_length))]) for n
                    in range(random.randrange(0, max_new_packets))])

            _add_packets_to_stream(self.stream, packet_list)

            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertEqual(total_data_len, cycle_count[0])

    def test_None_at_end_of_packets_moves_TLAST(self):
        '''If one or several Nones are set at the end of a packet, TLAST
        should be asserted for the last valid value.
        '''
        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {'first_run': True,
                         'packet': deque([])}

            @always(clock.posedge)
            def inst():
                self.interface.TREADY.next = True

                if inst_data['first_run']:
                    inst_data['first_run'] = False

                else:
                    next_expected_val = _get_next_val(packet_list, inst_data)

                    if all([each is None for each in inst_data['packet']]):
                        assert self.interface.TLAST

                    cycle_count[0] += 1

                # Stop if there is nothing left to process
                if len(inst_data['packet']) == 0:
                    if (len(packet_list) == 0):
                        raise StopSimulation

                    elif all(len(each) == 0 for each in packet_list):
                        raise StopSimulation

            return inst, bfm

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        def val_gen(data_byte_width):
            # Generates Nones about half the time probability
            val = random.randrange(0, 2**(8 * data_byte_width))
            if val > 2**(8 * data_byte_width - 1):
                return None
            else:
                return val

        for n in range(30):

            # Use fixed packet lengths
            packet_list = deque(
                [deque([
                    val_gen(self.data_byte_width) for m
                    in range(10)]) for n in range(10)])

            # Add a random number of Nones to the packet (at least 1).
            for each_packet in packet_list:
                each_packet.extend([None] * random.randrange(1, 5))

            _add_packets_to_stream(self.stream, packet_list)

            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertEqual(total_data_len, cycle_count[0])

    def test_None_in_packets_for_one_cycle_only(self):
        '''If the data was ``None``, corresponding to setting
        ``TVALID = False``, it should always only last for a single clock
        cycle before it is discarded.
        '''

        @block
        def testbench(clock):

            bfm = self.stream.model(clock, self.interface)
            inst_data = {'first_run': True,
                         'packet': deque([]),
                         'stored_val': None}

            @always(clock.posedge)
            def inst():

                if random.random() < ready_probability:
                    # Set TREADY True
                    self.interface.TREADY.next = True
                else:
                    # Set TREADY False
                    self.interface.TREADY.next = False

                if inst_data['first_run']:
                    assert not self.interface.TVALID
                    inst_data['first_run'] = False

                else:
                    if inst_data['stored_val'] is None:
                        next_expected_val = (
                            _get_next_val(packet_list, inst_data))

                    else:
                        next_expected_val = inst_data['stored_val']

                    if next_expected_val is None:
                        assert not self.interface.TVALID
                        cycle_count[0] += 1

                    else:
                        if not self.interface.TREADY:
                            inst_data['stored_val'] = next_expected_val

                        else:
                            inst_data['stored_val'] = None
                            assert self.interface.TVALID
                            assert self.interface.TDATA == next_expected_val
                            cycle_count[0] += 1

                # Stop if there is nothing left to process
                if (inst_data['stored_val'] is None and
                    len(inst_data['packet']) == 0):

                    if (len(packet_list) == 0):
                        raise StopSimulation

                    elif all(len(each) == 0 for each in packet_list):
                        raise StopSimulation

            return inst, bfm

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        def val_gen(data_byte_width):
            # Generates Nones about half the time probability
            val = random.randrange(0, 2**(8 * self.data_byte_width))
            if val > 2**(8 * self.data_byte_width - 1):
                return None
            else:
                return val

        for n in range(5):
            ready_probability = 0.2 * (n + 1)

            packet_list = deque(
                [deque([
                    val_gen(self.data_byte_width) for m
                    in range(random.randrange(0, max_packet_length))]) for n
                    in range(random.randrange(0, max_new_packets))])

            _add_packets_to_stream(self.stream, packet_list)

            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertEqual(total_data_len, cycle_count[0])


#    def test_alternative_ID_and_destinations(self):
#        '''It should be possible to set the ID and destination with the
#        ``add_data`` method.
#
#        All the data set for each pairing of ID and destination should
#        exist on a separate FIFO and the data should be interleaved
#        randomly.
#        '''
#        raise NotImplementedError
#        @block
#        def testbench(clock):
#
#            bfm = self.stream.model(clock, self.interface)
#            inst_data = {'first_run': True,
#                         'packet': []}
#
#            @always(clock.posedge)
#            def inst():
#                self.interface.TREADY.next = True
#
#                if inst_data['first_run']:
#                    assert not self.interface.TVALID
#                    inst_data['first_run'] = False
#
#                else:
#                    next_expected_val = _get_next_val(packet_list, inst_data)
#
#                    if next_expected_val is None:
#                        assert not self.interface.TVALID
#                        cycle_count[0] += 1
#
#                    else:
#                        assert self.interface.TVALID
#                        assert self.interface.TDATA == next_expected_val
#                        cycle_count[0] += 1
#
#                # Stop if there is nothing left to process
#                if len(inst_data['packet']) == 0:
#                    if (len(packet_list) == 0):
#                        raise StopSimulation
#
#                    elif all(len(each) == 0 for each in packet_list):
#                        raise StopSimulation
#
#            return inst, bfm
#
#        for n in range(30):
#            packet_list = _add_random_packets_to_stream(
#                self.stream, self.max_packet_length, self.max_new_packets,
#                self.max_rand_val)
#
#            total_data_len = sum(len(each) for each in packet_list)
#            cycle_count = [0]
#
#            myhdl_cosimulation(
#                None, None, testbench, self.args, self.arg_types)
#
#            self.assertEqual(total_data_len, cycle_count[0])


class TestAxiStreamSlaveBFM(TestCase):
    '''There should be an AXI Stream Bus Functional Model that implements
    a programmable AXI4 Stream protocol from the slave side.
    '''

    def setUp(self):

        self.data_byte_width = 8
        self.max_packet_length = 20
        self.max_new_packets = 10
        self.max_rand_val = 2**(8 * self.data_byte_width)

        self.source_stream = AxiStreamMasterBFM()
        self.test_sink = AxiStreamSlaveBFM()

        self.interface = AxiStreamInterface(self.data_byte_width)
        clock = Signal(bool(0))

        self.args = {'clock': clock}
        self.arg_types = {'clock': 'clock'}

    def test_completed_packets_property(self):
        '''There should be a ``completed_packets`` property that records all
        the complete packets that have been received.

        This property should not contain not yet completed packets.
        '''
        @block
        def testbench(clock):

            test_sink = self.test_sink

            master = self.source_stream.model(clock, self.interface)
            slave = test_sink.model(clock, self.interface)

            check_packet_next_time = Signal(False)
            checker_data = {'packets_to_check': 0}

            @always(clock.posedge)
            def checker():

                if self.interface.TLAST:
                    check_packet_next_time.next = True
                    checker_data['packets_to_check'] += 1

                if check_packet_next_time:
                    packets_to_check = checker_data['packets_to_check']
                    for ref_packet, test_packet in zip(
                        trimmed_packet_list[:packets_to_check],
                        test_sink.completed_packets[:packets_to_check]):

                        self.assertTrue(all(ref == test for ref, test in
                                            zip(ref_packet, test_packet)))


                    if packets_to_check >= len(trimmed_packet_list):
                        raise StopSimulation

                if len(trimmed_packet_list) == 0:
                    # The no data case
                    raise StopSimulation


            return master, slave, checker

        for n in range(30):
            # lots of test cases

            # We need new BFMs for every run
            self.source_stream = AxiStreamMasterBFM()
            self.test_sink = AxiStreamSlaveBFM()

            packet_list = _add_random_packets_to_stream(
                self.source_stream, self.max_packet_length,
                self.max_new_packets, self.max_rand_val)

            trimmed_packet_list = [
                packet for packet in packet_list if len(packet) > 0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

    def test_TREADY_probability(self):
        '''There should be a TREADY_probability argument to the model
        that dictates the probability of TREADY being True.
        '''
        @block
        def testbench(clock):

            test_sink = self.test_sink

            master = self.source_stream.model(clock, self.interface)
            slave = test_sink.model(
                clock, self.interface, TREADY_probability=TREADY_probability)

            check_packet_next_time = Signal(False)
            checker_data = {'packets_to_check': 0,
                            'TREADY_False_count': 0}

            @always(clock.posedge)
            def checker():

                if self.interface.TVALID and self.interface.TREADY:
                    if self.interface.TLAST:
                        check_packet_next_time.next = True
                        checker_data['packets_to_check'] += 1

                if not self.interface.TREADY:
                    checker_data['TREADY_False_count'] += 1

                if check_packet_next_time:
                    packets_to_check = checker_data['packets_to_check']
                    for ref_packet, test_packet in zip(
                        trimmed_packet_list[:packets_to_check],
                        test_sink.completed_packets[:packets_to_check]):

                        self.assertTrue(all(ref == test for ref, test in
                                            zip(ref_packet, test_packet)))


                    if packets_to_check >= len(trimmed_packet_list):
                        # The chance of this being false should be very very
                        # low
                        self.assertTrue(
                            checker_data['TREADY_False_count'] > 3)
                        raise StopSimulation

                if len(trimmed_packet_list) == 0:
                    # The no data case
                    raise StopSimulation


            return master, slave, checker

        for TREADY_percentage_probability in range(10, 90, 10):

            TREADY_probability = TREADY_percentage_probability/100.0
            # We need new BFMs for every run
            self.source_stream = AxiStreamMasterBFM()
            self.test_sink = AxiStreamSlaveBFM()

            # Use fixed length packets so it is very likely to be
            packet_list = deque(
                [deque([random.randrange(0, self.max_rand_val) for m
                        in range(20)]) for n in range(10)])

            packet_list = _add_packets_to_stream(
                self.source_stream, packet_list)

            trimmed_packet_list = [
                packet for packet in packet_list if len(packet) > 0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

    def test_TREADY_None(self):
        '''There should be possible to set TREADY_probability to None which
        prevents TREADY being driven.
        '''
        @block
        def testbench(clock, use_slave=True):

            test_sink = self.test_sink

            master = self.source_stream.model(clock, self.interface)
            test_sniffer = test_sink.model(
                clock, self.interface, TREADY_probability=None)

            slave = alt_test_sink.model(
                clock, self.interface, TREADY_probability=0.5)

            @always(clock.posedge)
            def stopper():
                if (len(trimmed_packet_list) ==
                    len(alt_test_sink.completed_packets)):
                    raise StopSimulation

            if use_slave:
                return master, slave, test_sniffer, stopper
            else:
                return master, test_sniffer, stopper

        # We need new BFMs for every run
        self.source_stream = AxiStreamMasterBFM()
        self.test_sink = AxiStreamSlaveBFM()

        # We create another sink that actually does twiddle TREADY
        alt_test_sink = AxiStreamSlaveBFM()

        # Use fixed length packets so it is very likely to be
        packet_list = deque(
            [deque([random.randrange(0, self.max_rand_val) for m
                    in range(random.randrange(0, 20))]) for n in range(10)])

        packet_list = _add_packets_to_stream(
            self.source_stream, packet_list)

        trimmed_packet_list = [
            packet for packet in packet_list if len(packet) > 0]

        myhdl_cosimulation(
            None, None, testbench, self.args, self.arg_types)

        self.assertEqual(
            alt_test_sink.completed_packets, self.test_sink.completed_packets)

        # Also check TREADY is not being driven.
        self.args['use_slave'] = False
        self.arg_types['use_slave'] = 'non-signal'
        self.test_sink = AxiStreamSlaveBFM()
        myhdl_cosimulation(
            100, None, testbench, self.args, self.arg_types)

        self.assertTrue(len(self.test_sink.completed_packets) == 0)
        self.assertTrue(len(self.test_sink.current_packet) == 0)

    def test_current_packet_property(self):
        '''There should be a ``current_packet`` property that returns the
        packet that is currently being recorded and has not yet completed.
        '''
        @block
        def testbench(clock):

            test_sink = self.test_sink

            master = self.source_stream.model(clock, self.interface)
            slave = test_sink.model(clock, self.interface)

            check_packet_next_time = Signal(False)
            checker_data = {
                'data_in_packet': 0,
                'current_packet_idx': 0}

            @always(clock.posedge)
            def checker():
                if (len(test_sink.completed_packets) ==
                    len(trimmed_packet_list)):
                    raise StopSimulation

                if (self.interface.TVALID and self.interface.TREADY
                    and not self.interface.TLAST):

                    checker_data['data_in_packet'] += 1

                    expected_length = checker_data['data_in_packet']
                    packet_length = len(test_sink.current_packet)

                    # depending on whether this has run first or the dut
                    # has run first, we might be one value difference in
                    # length
                    self.assertTrue(
                        packet_length == expected_length
                        or packet_length == (expected_length - 1))

                    packet_idx = checker_data['current_packet_idx']
                    expected_packet = (
                        trimmed_packet_list[packet_idx][:packet_length])

                    self.assertTrue(
                        all(ref == test for ref, test in
                            zip(expected_packet, test_sink.current_packet)))

                elif self.interface.TLAST:
                    checker_data['data_in_packet'] = 0
                    checker_data['current_packet_idx'] += 1

            return master, slave, checker

        for n in range(30):
            # lots of test cases

            # We need new BFMs for every run
            self.source_stream = AxiStreamMasterBFM()
            self.test_sink = AxiStreamSlaveBFM()

            packet_list = _add_random_packets_to_stream(
                self.source_stream, self.max_packet_length,
                self.max_new_packets, self.max_rand_val)

            trimmed_packet_list = [
                list(packet) for packet in packet_list if len(packet) > 0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

    def test_TVALID_low_not_recorded(self):
        '''If TVALID is unset on the master interface the values on the line
        should not be recorded.
        '''
        @block
        def testbench(clock):

            test_sink = self.test_sink

            master = self.source_stream.model(clock, self.interface)
            slave = test_sink.model(
                clock, self.interface, TREADY_probability=TREADY_probability)

            @always(clock.posedge)
            def stopper():

                if len(test_sink.completed_packets) == len(packet_list):
                    raise StopSimulation

            return master, slave, stopper

        for TREADY_percentage_probability in (90,):#range(10, 90, 10):

            TREADY_probability = TREADY_percentage_probability/100.0
            # We need new BFMs for every run
            self.source_stream = AxiStreamMasterBFM()
            self.test_sink = AxiStreamSlaveBFM()

            packet_list = deque([])
            trimmed_packet_list = []
            for n in range(10):
                packet = deque([])
                trimmed_packet = []
                for m in range(20):
                    val = random.randrange(0, self.max_rand_val * 2)
                    if val > self.max_rand_val:
                        val = None

                    else:
                        trimmed_packet.append(val)

                    packet.append(val)

                packet_list.append(packet)
                trimmed_packet_list.append(trimmed_packet)

            _add_packets_to_stream(self.source_stream, packet_list)

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertEqual(
                trimmed_packet_list, self.test_sink.completed_packets)

    def test_reset_method(self):
        '''There should be a reset method that when called clears all the
        recorded packets.
        '''
        @block
        def testbench(clock):

            test_sink = self.test_sink

            master = self.source_stream.model(clock, self.interface)
            slave = test_sink.model(clock, self.interface)

            return master, slave

        self.source_stream = AxiStreamMasterBFM()
        self.test_sink = AxiStreamSlaveBFM()

        packet_list = _add_random_packets_to_stream(
            self.source_stream, self.max_packet_length,
            self.max_new_packets, self.max_rand_val)

        trimmed_packet_list = [
            list(packet) for packet in packet_list if len(packet) > 0]

        cycles = sum(len(packet) for packet in packet_list) + 1

        myhdl_cosimulation(
            cycles, None, testbench, self.args, self.arg_types)

        assert self.test_sink.completed_packets == trimmed_packet_list

        packet_list = _add_random_packets_to_stream(
            self.source_stream, self.max_packet_length,
            self.max_new_packets, self.max_rand_val)

        added_trimmed_packet_list = [
            list(packet) for packet in packet_list if len(packet) > 0]

        cycles = sum(len(packet) for packet in packet_list) + 1

        self.test_sink.reset()

        myhdl_cosimulation(
            cycles, None, testbench, self.args, self.arg_types)

        self.assertEqual(self.test_sink.completed_packets,
                         added_trimmed_packet_list)


class TestAxiStreamBuffer(TestCase):
    '''There should be a block that interfaces with an AXI stream, buffering
    it as necessary if the output side is not ready. It should provide
    both a slave and a master interface.
    '''
    def setUp(self):
        self.data_byte_width = 8
        self.max_packet_length = 20
        self.max_new_packets = 10
        self.max_rand_val = 2**(8 * self.data_byte_width)

        self.source_stream = AxiStreamMasterBFM()
        self.test_sink = AxiStreamSlaveBFM()

        self.axi_stream_in = AxiStreamInterface(self.data_byte_width)
        self.axi_stream_out = AxiStreamInterface(self.data_byte_width)

        self.clock = Signal(bool(0))

        self.args = {'clock': self.clock}
        self.arg_types = {'clock': 'clock'}

    def test_zero_latency_non_passive_case(self):
        '''In the case where there is no need to buffer the signal (e.g.
        because the axi sink is always ready) there should be no latency
        in the outputs.

        This should happen when the buffer is not in passive mode (i.e. when
        TREADY is always set by the axi_stream_buffer block).
        '''

        @block
        def testbench(clock, axi_in, axi_out):

            buffer_block = axi_stream_buffer(
                clock, axi_in, axi_out, passive_sink_mode=False)

            @always(clock.posedge)
            def compare_sink():

                if axi_in.TVALID:
                    self.assertTrue(axi_out.TVALID)
                    self.assertEqual(axi_out.TDATA, axi_in.TDATA)
                    self.assertEqual(axi_out.TLAST, axi_in.TLAST)

            return buffer_block, compare_sink

        self.args['axi_in'] = self.axi_stream_in
        self.args['axi_out'] = self.axi_stream_out

        self.arg_types['axi_in'] = {
            'TDATA': 'custom', 'TLAST': 'custom', 'TVALID': 'custom',
            'TREADY': 'custom'}

        self.arg_types['axi_out'] = {
            'TDATA': 'output', 'TLAST': 'output', 'TVALID': 'output',
            'TREADY': 'output'}

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        packet_list, trimmed_packet_list, data_len = (
            _generate_random_packets_with_Nones(
                self.data_byte_width, self.max_packet_length,
                self.max_new_packets))

        self.source_stream.add_data(packet_list)

        custom_sources = [
            (self.source_stream.model, (self.clock, self.axi_stream_in), {}),
            (self.test_sink.model,
             (self.clock, self.axi_stream_out, 1.0), {})]

        cycles = data_len + 1

        myhdl_cosimulation(
            cycles, None, testbench, self.args, self.arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            trimmed_packet_list, self.test_sink.completed_packets)

    def test_zero_latency_passive_case(self):
        '''In the case where there is no need to buffer the signal (e.g.
        because the axi sink is always ready) there should be no latency
        in the outputs.

        This should happen when the buffer is in passive mode (i.e. when
        TREADY is set by a block other than that axi_stream_buffer block).
        '''

        @block
        def testbench(clock, axi_in, axi_out):

            buffer_block = axi_stream_buffer(
                clock, axi_in, axi_out, passive_sink_mode=True)

            @always(clock.posedge)
            def compare_sink():

                axi_out.TREADY.next = True

                if axi_in.TVALID:
                    self.assertTrue(axi_out.TVALID)
                    self.assertEqual(axi_out.TDATA, axi_in.TDATA)
                    self.assertEqual(axi_out.TLAST, axi_in.TLAST)

            return buffer_block, compare_sink

        self.args['axi_in'] = self.axi_stream_in
        self.args['axi_out'] = self.axi_stream_out

        self.arg_types['axi_in'] = {
            'TDATA': 'custom', 'TLAST': 'custom', 'TVALID': 'custom',
            'TREADY': 'output'}

        self.arg_types['axi_out'] = {
            'TDATA': 'output', 'TLAST': 'output', 'TVALID': 'output',
            'TREADY': 'output'}

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        packet_list, trimmed_packet_list, data_len = (
            _generate_random_packets_with_Nones(
                self.data_byte_width, self.max_packet_length,
                self.max_new_packets))

        self.source_stream.add_data(packet_list)

        TREADY_probability = 1.0
        custom_sources = [
            (self.source_stream.model, (self.clock, self.axi_stream_in), {}),
            (self.test_sink.model,
             (self.clock, self.axi_stream_in, TREADY_probability), {})]

        cycles = data_len + 1

        myhdl_cosimulation(
            cycles, None, testbench, self.args, self.arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            trimmed_packet_list, self.test_sink.completed_packets)

    def test_buffering_in_non_passive_case(self):
        '''In the case where the TREADY on the output bus is not the same
        as the TREADY on the input bus, the data should be buffered so
        it is not lost.

        This should happen when the buffer is in non passive mode (i.e. when
        TREADY is always set by the axi_stream_buffer block).
        '''

        @block
        def testbench(clock, axi_in, axi_out):

            buffer_block = axi_stream_buffer(
                clock, axi_in, axi_out, passive_sink_mode=False)

            return buffer_block

        self.args['axi_in'] = self.axi_stream_in
        self.args['axi_out'] = self.axi_stream_out

        self.arg_types['axi_in'] = {
            'TDATA': 'custom', 'TLAST': 'custom', 'TVALID': 'custom',
            'TREADY': 'custom'}

        self.arg_types['axi_out'] = {
            'TDATA': 'output', 'TLAST': 'output', 'TVALID': 'output',
            'TREADY': 'output'}

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        packet_list, trimmed_packet_list, data_len = (
            _generate_random_packets_with_Nones(
                self.data_byte_width, self.max_packet_length,
                self.max_new_packets))

        self.source_stream.add_data(packet_list)

        ref_sink = AxiStreamSlaveBFM()

        TREADY_probability = 0.2

        custom_sources = [
            (self.source_stream.model, (self.clock, self.axi_stream_in), {}),
            (self.test_sink.model,
             (self.clock, self.axi_stream_out, TREADY_probability), {})]

        # Have lots of cycles so we can be pretty sure we'll get all the data.
        cycles = data_len * 20 + 1

        myhdl_cosimulation(
            cycles, None, testbench, self.args, self.arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            trimmed_packet_list, self.test_sink.completed_packets)

    def test_buffering_in_passive_case(self):
        '''In the case where the TREADY on the output bus is not the same
        as the TREADY on the input bus, the data should be buffered so
        it is not lost.

        This should happen when the buffer is in passive mode (i.e. when
        TREADY is set by a block other than that axi_stream_buffer block).
        '''

        @block
        def testbench(clock, axi_in, axi_out):

            buffer_block = axi_stream_buffer(
                clock, axi_in, axi_out, passive_sink_mode=True)

            return buffer_block

        self.args['axi_in'] = self.axi_stream_in
        self.args['axi_out'] = self.axi_stream_out

        self.arg_types['axi_in'] = {
            'TDATA': 'custom', 'TLAST': 'custom', 'TVALID': 'custom',
            'TREADY': 'custom'}

        self.arg_types['axi_out'] = {
            'TDATA': 'output', 'TLAST': 'output', 'TVALID': 'output',
            'TREADY': 'output'}

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        packet_list, trimmed_packet_list, data_len = (
            _generate_random_packets_with_Nones(
                self.data_byte_width, self.max_packet_length,
                self.max_new_packets))

        self.source_stream.add_data(packet_list)

        ref_sink = AxiStreamSlaveBFM()

        TREADY_probability = 0.2

        custom_sources = [
            (self.source_stream.model, (self.clock, self.axi_stream_in), {}),
            (self.test_sink.model,
             (self.clock, self.axi_stream_out, TREADY_probability), {}),
            (ref_sink.model,
             (self.clock, self.axi_stream_in, 1.0), {})]

        # Have lots of cycles so we can be pretty sure we'll get all the data.
        cycles = data_len * 20 + 1

        myhdl_cosimulation(
            cycles, None, testbench, self.args, self.arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            trimmed_packet_list, self.test_sink.completed_packets)

    def test_zero_latency_after_buffering_case(self):
        '''In the case where the signal is buffered but then has time to
        catch up (i.e. because no valid transactions are present on the input)
        there should be once again no latency in the outputs.
        '''

        dump_sink = AxiStreamSlaveBFM()

        @block
        def testbench(clock, axi_in, axi_out):

            buffer_block = axi_stream_buffer(
                clock, axi_in, axi_out, passive_sink_mode=True)

            states = enum('initial_data', 'catchup', 'zero_latency')
            state = Signal(states.initial_data)

            @always(clock.posedge)
            def compare_sink():

                if state == states.initial_data:
                    if (self.test_sink.completed_packets ==
                        trimmed_packet_list):

                        state.next = states.catchup
                        axi_out.TREADY.next = True

                    else:
                        axi_out.TREADY.next = False

                elif state == states.catchup:
                    axi_out.TREADY.next = True
                    if dump_sink.completed_packets == trimmed_packet_list:
                        state.next = states.zero_latency

                else:
                    if axi_in.TVALID:
                        self.assertTrue(axi_out.TVALID)
                        self.assertEqual(axi_out.TDATA, axi_in.TDATA)
                        self.assertEqual(axi_out.TLAST, axi_in.TLAST)

            return buffer_block, compare_sink

        self.args['axi_in'] = self.axi_stream_in
        self.args['axi_out'] = self.axi_stream_out

        self.arg_types['axi_in'] = {
            'TDATA': 'custom', 'TLAST': 'custom', 'TVALID': 'custom',
            'TREADY': 'output'}

        self.arg_types['axi_out'] = {
            'TDATA': 'output', 'TLAST': 'output', 'TVALID': 'output',
            'TREADY': 'output'}

        max_packet_length = self.max_packet_length
        max_new_packets = self.max_new_packets

        packet_list, trimmed_packet_list, data_len = (
            _generate_random_packets_with_Nones(
                self.data_byte_width, self.max_packet_length,
                self.max_new_packets))

        self.source_stream.add_data(packet_list)

        TREADY_probability = 1.0
        custom_sources = [
            (self.source_stream.model, (self.clock, self.axi_stream_in), {}),
            (self.test_sink.model,
             (self.clock, self.axi_stream_in, TREADY_probability), {}),
            (dump_sink.model,
             (self.clock, self.axi_stream_out, None), {})]

        cycles = data_len * 3 + 1

        myhdl_cosimulation(
            cycles, None, testbench, self.args, self.arg_types,
            custom_sources=custom_sources)

        self.assertEqual(
            trimmed_packet_list, self.test_sink.completed_packets)

class TestAxiMasterPlaybackBlock(TestCase):
    '''There should be a convertible AXI master block that simply plays back
    the packets it is passed.
    '''

    def setUp(self):

        self.data_byte_width = 8
        self.max_rand_val = 2**(8 * self.data_byte_width)

        self.axi_slave = AxiStreamSlaveBFM()

        self.axi_interface = AxiStreamInterface(self.data_byte_width)
        self.clock = Signal(bool(0))

        self.args = {
            'clock': self.clock, 'axi_interface': self.axi_interface,
            'packets': None}

        self.arg_types = {
            'clock': 'clock',
            'axi_interface': {'TVALID': 'output', 'TREADY': 'custom',
                              'TDATA': 'output', 'TLAST': 'output'},
            'packets': 'non-signal'}

    def sim_wrapper(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types,
        **kwargs):

        return myhdl_cosimulation(
            sim_cycles, dut_factory, ref_factory, args, arg_types, **kwargs)

    def test_playback_of_packets(self):
        '''The packets should be a list of lists and should be properly
        handleable by a valid AXI slave.
        '''
        max_packet_length = 20
        max_new_packets = 50
        max_val = self.max_rand_val

        packet_list = [
            [random.randrange(0, max_val) for m
             in range(random.randrange(0, max_packet_length))] for n
            in range(random.randrange(0, max_new_packets))]

        self.args['packets'] = packet_list

        non_empty_packets = [
            packet for packet in packet_list if len(packet) > 0]
        non_empty_packet_lengths = [
            len(packet) for packet in non_empty_packets]

        max_cycles = 50 * max_packet_length * max_new_packets

        @block
        def exit_checker(clock):

            cycles = [0]
            @always(clock.posedge)
            def checker():
                # A sanity check to make sure we don't hang
                assert cycles[0] < max_cycles
                cycles[0] += 1

                if (len(self.axi_slave.completed_packets) >=
                    len(non_empty_packet_lengths)):
                    raise StopSimulation

            return checker

        custom_sources = [
            (exit_checker, (self.clock,), {}),
            (self.axi_slave.model, (self.clock, self.axi_interface, 0.5), {})]

        self.sim_wrapper(
            None, axi_master_playback, axi_master_playback, self.args,
            self.arg_types, custom_sources=custom_sources)

        self.assertEqual(self.axi_slave.completed_packets, non_empty_packets)

    def test_None_sets_TVALID_False(self):
        '''Values of None in the packets should set TVALID to False for a
        cycle.
        '''
        max_packet_length = 20
        max_new_packets = 50
        max_val = self.max_rand_val

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

        # Make sure we have at least one packet with None at its end.
        packet_list.append([random.randrange(0, max_val) for m in range(10)])
        packet_list[-1].append(None)

        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        trimmed_packets = [
            packet for packet in None_trimmed_packet_list if len(packet) > 0]

        self.args['packets'] = packet_list

        trimmed_packet_lengths = [len(packet) for packet in trimmed_packets]

        max_cycles = 10 * max_packet_length * max_new_packets

        @block
        def exit_checker(clock):

            cycles = [0]
            @always(clock.posedge)
            def checker():
                # A sanity check to make sure we don't hang
                try:
                    assert cycles[0] < max_cycles
                    cycles[0] += 1
                except AssertionError:
                    raise StopSimulation

                if (len(self.axi_slave.completed_packets) >=
                    len(trimmed_packet_lengths)):
                    raise StopSimulation

            return checker

        # Firstly check it with the slave always ready. This means we can
        # count the clock cycles to infer the TVALID going false.
        custom_sources = [
            (exit_checker, (self.clock,), {}),
            (self.axi_slave.model, (self.clock, self.axi_interface, 1.0), {})]

        self.sim_wrapper(
            None, axi_master_playback, axi_master_playback, self.args,
            self.arg_types, custom_sources=custom_sources)

        self.assertEqual(self.axi_slave.completed_packets, trimmed_packets)

    def test_block_converts(self):
        '''The axi_master_playback block should convert to both VHDL and
        Verilog.
        '''
        max_packet_length = 20
        max_new_packets = 50
        max_val = self.max_rand_val

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

        # Make sure we have at least one packet with None at its end.
        packet_list.append([random.randrange(0, max_val) for m in range(10)])
        packet_list[-1].append(None)

        None_trimmed_packet_list = [
            [val for val in packet if val is not None] for packet in
            packet_list]

        self.args['packets'] = packet_list

        tmp_dir = tempfile.mkdtemp()
        try:
            instance = axi_master_playback(**self.args)
            instance.convert('VHDL', path=tmp_dir)
            self.assertTrue(os.path.exists(
                os.path.join(tmp_dir, 'axi_master_playback.vhd')))

            instance = axi_master_playback(**self.args)
            instance.convert('Verilog', path=tmp_dir)
            self.assertTrue(os.path.exists(
                os.path.join(tmp_dir, 'axi_master_playback.v')))
        finally:
            shutil.rmtree(tmp_dir)



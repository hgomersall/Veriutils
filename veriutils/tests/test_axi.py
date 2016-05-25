
from unittest import TestCase
from veriutils import *
from myhdl import *
import myhdl

from collections import deque
import random


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
        '''There should be a TSTRB attribute that is an unsigned intbv Signal
        that is bus_width bits wide and is full range.
        '''
        interface = AxiStreamInterface()
        self.assertTrue(isinstance(interface.TSTRB, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TSTRB._val, intbv))
        self.assertEqual(len(interface.TSTRB._val), interface.bus_width)
        self.assertEqual(interface.TSTRB.min, 0)
        self.assertEqual(interface.TSTRB.max, 2**(interface.bus_width))

        interface = AxiStreamInterface(bus_width='6')
        self.assertEqual(len(interface.TSTRB._val), interface.bus_width)

    def test_TKEEP(self):
        '''There should be a TKEEP attribute that is an unsigned intbv Signal
        that is bus_width bits wide and is full range.
        '''
        interface = AxiStreamInterface()
        self.assertTrue(isinstance(interface.TKEEP, myhdl._Signal._Signal))
        self.assertTrue(isinstance(interface.TKEEP._val, intbv))
        self.assertEqual(len(interface.TKEEP._val), interface.bus_width)
        self.assertEqual(interface.TKEEP.min, 0)
        self.assertEqual(interface.TKEEP.max, 2**(interface.bus_width))

        interface = AxiStreamInterface(bus_width=8)
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
            val = random.randrange(0, 2**(8 * self.data_byte_width))
            if val > 2**(8 * self.data_byte_width - 1):
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
            val = random.randrange(0, 2**(8 * self.data_byte_width))
            if val > 2**(8 * self.data_byte_width - 1):
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
        self.source_test_sink = AxiStreamSlaveBFM()

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

            test_sink = self.source_test_sink

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
            self.source_test_sink = AxiStreamSlaveBFM()
            
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

            test_sink = self.source_test_sink

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
            self.source_test_sink = AxiStreamSlaveBFM()

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

    
    def test_current_packet_property(self):
        '''There should be a ``current_packet`` property that returns the
        packet that is currently being recorded and has not yet completed.
        '''
        @block
        def testbench(clock):

            test_sink = self.source_test_sink

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
            self.source_test_sink = AxiStreamSlaveBFM()
            
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

            test_sink = self.source_test_sink

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
            self.source_test_sink = AxiStreamSlaveBFM()

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
                trimmed_packet_list, self.source_test_sink.completed_packets)

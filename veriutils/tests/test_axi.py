
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

class TestAxiStreamMasterBFM(TestCase):
    '''There should be an AXI Stream Bus Functional Model that implements
    a programmable AXI4 Stream protocol from the master side.
    '''

    def setUp(self):
        
        self.data_byte_width = 8
        self.max_packet_length = 10
        self.max_new_packets = 5

        self.stream = AxiStreamMasterBFM()
        self.interface = AxiStreamInterface(self.data_byte_width)
        clock = Signal(bool(0))

        self.args = {'clock': clock}
        self.arg_types = {'clock': 'clock'}

    def add_packets_to_stream(self, packet_list):
        '''Adds the supplied packets to the stream and returns them.
        '''
        packet_list = deque(deque(packet) for packet in packet_list)
        self.stream.add_data(packet_list)
        return packet_list

    def add_random_packets_to_stream(
        self, max_packet_length, max_new_packets):
        '''Adds a load of random data to the stream and returns 
        the list of added packets.

        Each packet is of random length between 0 and max_packet_length
        and there are a random number between 0 and max_new_packets of 
        them.
        '''
        packet_list = deque(
            [deque([
                random.randrange(0, 2**(8 * self.data_byte_width)) for m 
                in range(random.randrange(0, max_packet_length))]) for n 
             in range(random.randrange(0, max_new_packets))])

        return self.add_packets_to_stream(packet_list)


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
            packet_list = self.add_random_packets_to_stream(
                self.max_packet_length, self.max_new_packets)

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
            packet_list = self.add_random_packets_to_stream(
                self.max_packet_length, self.max_new_packets)
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
            add_packets_to_stream = lambda: self.add_packets_to_stream(
                _packet_list)
            packet_list = add_packets_to_stream()
            total_data_len = [0]
            cycle_count = [0]
            checks()

        #run the test several times to better sample test space
        add_packets_to_stream = lambda: self.add_random_packets_to_stream(
            self.max_packet_length, self.max_new_packets)

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
            add_packets_to_stream = lambda: self.add_packets_to_stream(
                _packet_list)
            packet_list = add_packets_to_stream()
            total_data_len = [0]
            cycle_count = [0]
            checks()

        #run the test several times to better sample test space
        add_packets_to_stream = lambda: self.add_random_packets_to_stream(
            self.max_packet_length, self.max_new_packets)

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

    def test_TREADY_False_pauses_transfer(self):
        '''When the slave sets TREADY to False, no data should be sent, but
        the data should not be lost. Transfers should continue again as soon as
        TREADY is True.
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

            packet_list = self.add_random_packets_to_stream(
                self.max_packet_length, self.max_new_packets)

            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            dut_output, ref_output = myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertTrue(cycle_count[0] == total_data_len)

    def test_alternative_ID_and_destinations(self):
        '''It should be possible to set the ID and destination with the
        ``add_data`` method.

        All the data set for each pairing of ID and destination should
        exist on a separate FIFO and the data should be interleaved 
        randomly.
        '''
        raise NotImplementedError
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
            packet_list = self.add_random_packets_to_stream(
                self.max_packet_length, self.max_new_packets)

            total_data_len = sum(len(each) for each in packet_list)
            cycle_count = [0]

            myhdl_cosimulation(
                None, None, testbench, self.args, self.arg_types)

            self.assertEqual(total_data_len, cycle_count[0])

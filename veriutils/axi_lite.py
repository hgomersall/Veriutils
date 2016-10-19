from myhdl import *
import copy
import random
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

class AxiLiteWriteAddressChannel(object):
    '''The AXI lite write address channel definition

    AXI provides access permissions signals that can be used to protect
    against illegal transactions. AWPROT defines the access permissions for
    write accesses.

    +--------+-------+---------------------+
    | AWPROT | Value | Function            |
    +========+=======+=====================+
    | [0]    | 0     | Unprivileged access |
    |        | 1     | Privileged access   |
    | [1]    | 0     | Secure access       |
    |        | 1     | Non-secure access   |
    | [2]    | 0     | Data access         |
    |        | 1     | Instruction access  |
    +--------+----------+------------------+
    See the AMBA AXI and ACE protocol spec section A4.7 for more details.
    '''

    def __init__(self, addr_width):
        self.AWVALID = Signal(bool(0))
        self.AWREADY = Signal(bool(0))
        self.AWADDR = Signal(intbv(0)[addr_width:])
        self.AWPROT = Signal(intbv(0)[3:])

class AxiLiteWriteDataChannel(object):
    '''The AXI lite write data channel definition

    AXI4-Lite has a fixed data bus width and all transactions are the same
    width as the data bus. The data bus width must be, either 32-bits or
    64-bits.

    The WSTRB[n:0] signals when HIGH, specify the byte lanes of the data bus
    that contain valid information. There is one write strobe for each eight
    bits of the write data bus, therefore WSTRB[n] corresponds to
    WDATA[(8n)+7: (8n)].

    A master must ensure that the write strobes are HIGH only for byte lanes
    that contain valid data.

    When WVALID is LOW, the write strobes can take any value, although this
    specification recommends that they are either driven LOW or held at their
    previous value.

    All AXI4-Lite master interfaces and interconnect components must provide
    correct write strobes.

    Any AXI4-Lite slave component can choose whether to use the write strobes.
    The options permitted are:
        - To make full use of the write strobes
        - To ignore the write strobes and treat all write accesses as being the
        full data bus width
        - To detect write strobe combinations that are not supported and
        provide an error response.
    '''

    def __init__(self, data_width=32):

        # Check that the data_width is a valid size.
        if (data_width != 32 and data_width != 64):
            raise ValueError('data_width must be 32 bits or 64 bits')

        # There must be one strobe line for each byte lane of the data bus.
        wstrb_width = data_width//8

        self.WVALID = Signal(bool(0))
        self.WREADY = Signal(bool(0))
        self.WDATA = Signal(intbv(0)[data_width:])
        self.WSTRB = Signal(intbv(0)[wstrb_width:])

class AxiLiteWriteResponseChannel(object):
    '''The AXI lite write response channel definition

    The AXI lite protocol provides response signaling for both read and write
    transactions. For write transactions the response information is signaled
    on the write response channel.

    +-------+----------+-----------------------+
    | BRESP | Response | Desciption            |
    +=======+==========+=======================+
    | 0b00  | OKAY     | Normal access success |
    | 0b10  | SLVERR   | Slave error           |
    | 0b11  | DECERR   | Decode error          |
    +-------+----------+-----------------------+
    See the AMBA AXI and ACE protocol spec section A3.4.4 for more details.
    '''

    def __init__(self):
        self.BVALID = Signal(bool(0))
        self.BREADY = Signal(bool(0))
        self.BRESP = Signal(intbv(0)[2:])

class AxiLiteReadAddressChannel(object):
    '''The AXI lite read address channel definition

    AXI provides access permissions signals that can be used to protect
    against illegal transactions. ARPROT defines the access permissions for
    read accesses.

    +--------+-------+---------------------+
    | ARPROT | Value | Function            |
    +========+=======+=====================+
    | [0]    | 0     | Unprivileged access |
    |        | 1     | Privileged access   |
    | [1]    | 0     | Secure access       |
    |        | 1     | Non-secure access   |
    | [2]    | 0     | Data access         |
    |        | 1     | Instruction access  |
    +--------+----------+------------------+
    See the AMBA AXI and ACE protocol spec section A4.7 for more details.
    '''

    def __init__(self, addr_width):
        self.ARVALID = Signal(bool(0))
        self.ARREADY = Signal(bool(0))
        self.ARADDR = Signal(intbv(0)[addr_width:])
        self.ARPROT = Signal(intbv(0)[3:])

class AxiLiteReadDataChannel(object):
    '''The AXI lite read data channel definition

    AXI4-Lite has a fixed data bus width and all transactions are the same
    width as the data bus. The data bus width must be, either 32-bits or
    64-bits.

    The AXI lite protocol provides response signaling for both read and write
    transactions. For read transactions the response information from the
    slave is signaled on the read data channel.

    +-------+----------+-----------------------+
    | RRESP | Response | Desciption            |
    +=======+==========+=======================+
    | 0b00  | OKAY     | Normal access success |
    | 0b10  | SLVERR   | Slave error           |
    | 0b11  | DECERR   | Decode error          |
    +-------+----------+-----------------------+
    See the AMBA AXI and ACE protocol spec section A3.4.4 for more details.
    '''

    def __init__(self, data_width=32):

        # Check that the data_width is a valid size.
        if (data_width != 32 and data_width != 64):
            raise ValueError('data_width must be 32 bits or 64 bits')

        self.RVALID = Signal(bool(0))
        self.RREADY = Signal(bool(0))
        self.RDATA = Signal(intbv(0)[data_width:])
        self.RRESP = Signal(intbv(0)[2:])

class AxiLiteInterface(object):
    '''The AXI lite interface definition

    Creates an AXI4 lite interface object. The signals and parameters
    are exactly as described in the AMBA AXI and ACE protocol spec.

    For transaction dependencies see AMBA AXI and ACE protocol spec section
    A3.3.1.
    '''

    def __init__(self, data_width, addr_width):

        self.WriteAddrChannel = AxiLiteWriteAddressChannel(addr_width)
        self.WriteDataChannel = AxiLiteWriteDataChannel(data_width)
        self.WriteRespChannel = AxiLiteWriteResponseChannel()
        self.ReadAddrChannel = AxiLiteReadAddressChannel(addr_width)
        self.ReadDataChannel = AxiLiteReadDataChannel(data_width)

class AxiLiteMasterBFM(object):
    def __init__(self):
        '''Create an AXI Lite master bus functional model (BFM).

        Read and write transactions can be triggered using the
        ``add_read_transaction`` and ``add_write_transaction`` respectively.
        '''
        # Add write or read transactions to this BFM. Read transactions
        # comprise:
        #     read_address
        #     read_protection
        #     address_delay
        #     data_delay
        # Write transactions comprise:
        #     write_address
        #     write_data
        #     write_strobes
        #     write_protection
        #     address_delay
        #     data_delay
        #     response_delay

        self.write_transactions = Queue()
        self.write_responses = Queue()
        self.read_transactions = Queue()
        self.read_responses = Queue()

    def add_write_transaction(
        self, write_address, write_data, write_strobes, write_protection,
        address_delay=0, data_delay=0, response_ready_delay=0):
        '''Add write transactions to the BFM.
        '''

        self.write_transactions.put({'wr_addr': write_address,
                                     'wr_data': write_data,
                                     'wr_strbs': write_strobes,
                                     'wr_prot': write_protection,
                                     'address_delay': address_delay,
                                     'data_delay': data_delay,
                                     'response_ready_delay': (
                                         response_ready_delay),})

    def add_read_transaction(self, read_address, read_protection,
                             address_delay=0, data_delay=0):
        ''' Add read transactions to the BFM.
        '''

        self.read_transactions.put({'rd_addr': read_address,
                                    'rd_prot': read_protection,
                                    'address_delay': address_delay,
                                    'data_delay': data_delay,})

    @block
    def model(self, clock, nreset, axi_lite_interface):

        # Define and create the write state machines
        t_write_state = enum('IDLE', 'DELAY', 'SEND')
        write_address_state = Signal(t_write_state.IDLE)
        write_data_state = Signal(t_write_state.IDLE)
        write_response_state = Signal(t_write_state.IDLE)

        # The data required for the write state machines
        write_data = {'current_transaction': None,
                      'start_transaction': False,}

        # Define and create the read state machines
        t_read_state = enum('IDLE', 'DELAY', 'SEND')
        read_address_state = Signal(t_read_state.IDLE)
        read_data_state = Signal(t_read_state.IDLE)

        # The data required for the read state machines
        read_data = {'current_transaction': None,
                     'start_transaction': False,}

        @always(clock.posedge)
        def write():

            if not nreset:
                # Axi reset so drive control signals low and return to idle.
                axi_lite_interface.WriteAddrChannel.AWVALID.next = False
                write_address_state.next = t_write_state.IDLE
                axi_lite_interface.WriteDataChannel.WVALID.next = False
                write_data_state.next = t_write_state.IDLE
                axi_lite_interface.WriteRespChannel.BREADY.next = False
                write_response_state.next = t_write_state.IDLE

            else:

                if (write_address_state == t_write_state.IDLE and
                    write_data_state == t_write_state.IDLE and
                    write_response_state == t_write_state.IDLE and
                    self.write_transactions.qsize() > 0):
                    # All state machines are ready for the next transaction
                    # and there is one in the queue.
                    write_data['current_transaction'] = (
                        self.write_transactions.get(False))
                    write_data['start_transaction'] = True
                else:
                    write_data['start_transaction'] = False

                # Address handshaking state machine
                # ---------------------------------
                if write_address_state == t_write_state.IDLE:
                    if write_data['start_transaction']:
                        if write_data[
                            'current_transaction']['address_delay'] == 0:
                            # Commence the transaction. Set the address, valid
                            # and protections.
                            axi_lite_interface.WriteAddrChannel.AWVALID.next =(
                                True)
                            axi_lite_interface.WriteAddrChannel.AWADDR.next = (
                                write_data['current_transaction']['wr_addr'])
                            axi_lite_interface.WriteAddrChannel.AWPROT.next = (
                                write_data['current_transaction']['wr_prot'])
                            write_address_state.next = t_write_state.SEND
                        else:
                            # Delay the transaction
                            write_data[
                                'current_transaction']['address_delay'] -= 1
                            write_address_state.next = t_write_state.DELAY

                if write_address_state == t_write_state.DELAY:
                    if write_data[
                        'current_transaction']['address_delay'] == 0:
                        # Commence the transaction. Set the address, valid and
                        # protections.
                        axi_lite_interface.WriteAddrChannel.AWVALID.next = (
                            True)
                        axi_lite_interface.WriteAddrChannel.AWADDR.next = (
                            write_data['current_transaction']['wr_addr'])
                        axi_lite_interface.WriteAddrChannel.AWPROT.next = (
                            write_data['current_transaction']['wr_prot'])
                        write_address_state.next = t_write_state.SEND
                    else:
                        # Delay the transaction
                        write_data[
                            'current_transaction']['address_delay'] -= 1

                if write_address_state == t_write_state.SEND:
                    if axi_lite_interface.WriteAddrChannel.AWREADY:
                        # Wait until handshake has completed and address has
                        # been received
                        axi_lite_interface.WriteAddrChannel.AWVALID.next = (
                            False)
                        write_address_state.next = t_write_state.IDLE

                # Data handshaking state machine
                # ------------------------------
                if write_data_state == t_write_state.IDLE:
                    if write_data['start_transaction']:
                        if write_data[
                            'current_transaction']['data_delay'] == 0:
                            # Commence the transaction. Set the data, valid
                            # and strobes.
                            axi_lite_interface.WriteDataChannel.WVALID.next =(
                                True)
                            axi_lite_interface.WriteDataChannel.WDATA.next = (
                                write_data['current_transaction']['wr_data'])
                            axi_lite_interface.WriteDataChannel.WSTRB.next = (
                                write_data['current_transaction']['wr_strbs'])
                            write_data_state.next = t_write_state.SEND
                        else:
                            # Delay the transaction
                            write_data[
                                'current_transaction']['data_delay'] -= 1
                            write_data_state.next = t_write_state.DELAY

                if write_data_state == t_write_state.DELAY:
                    if write_data['current_transaction']['data_delay'] == 0:
                        # Commence the transaction. Set the data, valid and
                        # strobes.
                        axi_lite_interface.WriteDataChannel.WVALID.next = True
                        axi_lite_interface.WriteDataChannel.WDATA.next = (
                            write_data['current_transaction']['wr_data'])
                        axi_lite_interface.WriteDataChannel.WSTRB.next = (
                            write_data['current_transaction']['wr_strbs'])
                        write_data_state.next = t_write_state.SEND
                    else:
                        # Delay the transaction
                        write_data[
                            'current_transaction']['data_delay'] -= 1

                if write_data_state == t_write_state.SEND:
                    if axi_lite_interface.WriteDataChannel.WREADY:
                        # Wait until handshake has completed and data has been
                        # received
                        axi_lite_interface.WriteDataChannel.WVALID.next = (
                            False)
                        write_data_state.next = t_write_state.IDLE

                # Response handshaking state machine
                # ----------------------------------
                if write_response_state == t_write_state.IDLE:
                    if write_data['start_transaction']:
                        if write_data[
                            'current_transaction'][
                                'response_ready_delay'] == 0:
                            # Set the ready flag high
                            axi_lite_interface.WriteRespChannel.BREADY.next =(
                                True)
                            write_response_state.next = t_write_state.SEND
                        else:
                            # Delay the transaction
                            write_data[
                                'current_transaction'][
                                    'response_ready_delay'] -= 1
                            write_response_state.next = t_write_state.DELAY

                if write_response_state == t_write_state.DELAY:
                    if write_data[
                        'current_transaction']['response_ready_delay'] == 0:
                        # Set the ready flag high
                        axi_lite_interface.WriteRespChannel.BREADY.next = True
                        write_response_state.next = t_write_state.SEND
                    else:
                        # Delay the transaction
                        write_data[
                            'current_transaction'][
                                'response_ready_delay'] -= 1

                if write_response_state == t_write_state.SEND:
                    if axi_lite_interface.WriteRespChannel.BVALID:
                        # Add the response to the write_response_queue
                        self.write_responses.put({'wr_resp': copy.copy(
                            axi_lite_interface.WriteRespChannel.BRESP.val)})
                        # Wait until response is valid (this means the
                        # handshake is complete).
                        axi_lite_interface.WriteRespChannel.BREADY.next = (
                            False)
                        write_response_state.next = t_write_state.IDLE

        @always(clock.posedge)
        def read():

            if not nreset:
                # Axi reset so drive control signals low and return to idle.
                axi_lite_interface.ReadAddrChannel.ARVALID.next = False
                read_address_state.next = t_read_state.IDLE
                axi_lite_interface.ReadDataChannel.RREADY.next = False
                read_data_state.next = t_read_state.IDLE

            else:

                if (read_address_state == t_read_state.IDLE and
                    read_data_state == t_read_state.IDLE and
                    self.read_transactions.qsize() > 0):
                    # All state machines are ready for the next transaction
                    # and there is one in the queue.
                    read_data['current_transaction'] = (
                        self.read_transactions.get(False))
                    read_data['start_transaction'] = True
                else:
                    read_data['start_transaction'] = False

                # Address handshaking state machine
                # ---------------------------------
                if read_address_state == t_read_state.IDLE:
                    if read_data['start_transaction']:
                        if read_data[
                            'current_transaction']['address_delay'] == 0:
                            # Commence the transaction. Set the address, valid
                            # and protections.
                            axi_lite_interface.ReadAddrChannel.ARVALID.next =(
                                True)
                            axi_lite_interface.ReadAddrChannel.ARADDR.next = (
                                read_data['current_transaction']['rd_addr'])
                            axi_lite_interface.ReadAddrChannel.ARPROT.next = (
                                read_data['current_transaction']['rd_prot'])
                            read_address_state.next = t_read_state.SEND
                        else:
                            # Delay the transaction
                            read_data[
                                'current_transaction']['address_delay'] -= 1
                            read_address_state.next = t_read_state.DELAY

                if read_address_state == t_read_state.DELAY:
                    if read_data['current_transaction']['address_delay'] == 0:
                        # Commence the transaction. Set the address, valid and
                        # protections.
                        axi_lite_interface.ReadAddrChannel.ARVALID.next = True
                        axi_lite_interface.ReadAddrChannel.ARADDR.next = (
                            read_data['current_transaction']['rd_addr'])
                        axi_lite_interface.ReadAddrChannel.ARPROT.next = (
                            read_data['current_transaction']['rd_prot'])
                        read_address_state.next = t_read_state.SEND
                    else:
                        # Delay the transaction
                        read_data[
                            'current_transaction']['address_delay'] -= 1

                if read_address_state == t_read_state.SEND:
                    if axi_lite_interface.ReadAddrChannel.ARREADY:
                        # Wait until handshake has completed and address has
                        # been received
                        axi_lite_interface.ReadAddrChannel.ARVALID.next = (
                            False)
                        read_address_state.next = t_read_state.IDLE

                # Data handshaking state machine
                # ------------------------------
                if read_data_state == t_read_state.IDLE:
                    if read_data['start_transaction']:
                        if read_data[
                            'current_transaction']['data_delay'] == 0:
                            # Commence the transaction. Set the data, valid
                            # and protections.
                            axi_lite_interface.ReadDataChannel.RREADY.next = (
                                True)
                            read_data_state.next = t_read_state.SEND
                        else:
                            # Delay the transaction
                            read_data[
                                'current_transaction']['data_delay'] -= 1
                            read_data_state.next = t_read_state.DELAY

                if read_data_state == t_read_state.DELAY:
                    if read_data['current_transaction']['data_delay'] == 0:
                        # Commence the transaction. Set the data, valid and
                        # protections.
                        axi_lite_interface.ReadDataChannel.RREADY.next = True
                        read_data_state.next = t_read_state.SEND
                    else:
                        # Delay the transaction
                        read_data[
                            'current_transaction']['data_delay'] -= 1

                if read_data_state == t_read_state.SEND:
                    if axi_lite_interface.ReadDataChannel.RVALID:
                        # Add the response to the read_response_queue
                        self.read_responses.put(
                            {'rd_data': copy.copy(
                                axi_lite_interface.ReadDataChannel.RDATA.val),
                             'rd_resp': copy.copy(
                                 axi_lite_interface.ReadDataChannel.RRESP.val)
                            })
                        # Wait until handshake has completed and data has been
                        # received
                        axi_lite_interface.ReadDataChannel.RREADY.next = False
                        read_data_state.next = t_read_state.IDLE

        return write, read
from myhdl import *
from collections import deque

class AxiStreamInterface(object):
    '''The AXI stream interface definition'''

    @property
    def bus_width(self):
        return self._bus_width

    @property
    def TID_width(self):
        return self._TID_width

    @property
    def TDEST_width(self):
        return self._TDEST_width

    @property
    def TUSER_width(self):
        return self._TUSER_width

    def __init__(self, bus_width=4, TID_width=None, TDEST_width=None, 
                 TUSER_width=None):
        '''Creates an AXI4 Stream interface object. The signals and parameters
        are exactly as described in the AMBA 4 AXI4 Stream Protocol
        Specification.

        For a full understanding of the protocol, that document should be
        read (it is quite accessible and easy to read).

        ``bus_width`` gives the width of the data bus, ``TDATA``, in bytes.
        This by extension gives the width in bits of the byte qualifiers,
        ``TSTRB`` and ``TKEEP``.

        If ``TID_width`` is not ``None``, then the stream identifier signal,
        ``TID``, is enabled and has width ``TID_width`` bits. The AXI stream
        protocol specification recommends that ``TID_width`` not be larger than
        8.

        It ``TID_width`` is ``None``, then no ``TID`` signal is available.

        Similarly to ``TID_width``, ``TDEST_width`` and ``TUSER_width`` if not
        ``None`` set the width in bits of ``TDEST`` (providing routing
        information) and ``TUSER`` (providing user defined sideband
        information) respectively.

        If either are ``None``, then as with ``TID_width``, their respective
        signals are not available.

        The AXI stream protocol specification recommends that ``TDEST_width``
        not be larger than 4, and ``TUSER_width`` be an integer multiple of
        the interface width in bytes.

        None of the recommendations are enforced in the interface and can
        be implemented differently. There may be additional constraints on the
        size of the interfaces that need to be considered.
        '''
        self._bus_width = int(bus_width)

        self.TVALID = Signal(bool(0))
        self.TREADY = Signal(bool(0))        
        self.TDATA = Signal(intbv(0)[8*self.bus_width:])
        self.TSTRB = Signal(intbv(0)[self.bus_width:])
        self.TKEEP = Signal(intbv(0)[self.bus_width:]) 
        self.TLAST = Signal(bool(0))
        
        if TID_width is not None:
            self._TID_width = int(TID_width)
            self.TID = Signal(intbv(0)[self.TID_width:])
        else:
            self._TID_width = None

        if TDEST_width is not None:
            self._TDEST_width = int(TDEST_width)
            self.TDEST = Signal(intbv(0)[self.TDEST_width:])
        else:
            self._TDEST_width = None

        if TUSER_width is not None:
            self._TUSER_width = int(TUSER_width)
            self.TUSER = Signal(intbv(0)[self.TUSER_width:])
        else:
            self._TUSER_width = None

class AxiStreamMasterBFM(object):
    
    def __init__(self):
        '''Create an AXI4 Stream master bus functional model (BFM).

        Data is added to the stream using the ``add_data`` method, at 
        which point all the parameters can be set up for a particular sequence
        of transfers.

        Currently ``TUSER`` is ignored.
        '''
        self._data = {}

    def add_data(self, data, stream_ID=0, stream_destination=0):
        '''Add data to this BFM. ``data`` is a list of lists, each sublist of
        which comprises a packet (terminated by ``TKEEP`` being asserted).

        The ``stream_ID`` and ``stream_destination`` parameters are used to 
        set the ``TID`` and ``TDEST`` signals respectively for the data 
        provided.
        '''
        try:
            self._data[(stream_ID, stream_destination)].extend(
                deque([deque(packet) for packet in data]))

        except KeyError:
            self._data[(stream_ID, stream_destination)] = deque(
                [deque(packet) for packet in data])


    @block
    def model(self, clock, interface):

        model_rundata = {}

        @always(clock.posedge)
        def model_inst():
            
            # We need to try to update either when a piece of data has been 
            # propagated (TVALID and TREADY) or when we previously didn't
            # have any data (not TVALID)
            if ((interface.TVALID and interface.TREADY) or 
                not interface.TVALID):

                if 'packet' not in model_rundata:
                    model_rundata['packet'] = []
                    while len(model_rundata['packet']) == 0:

                        try:
                            if len(self._data[(0, 0)]) > 0:
                                model_rundata['packet'] = (
                                    self._data[(0, 0)].popleft())

                            else:
                                # Nothing left to get, so we drop out.
                                break

                        except KeyError:
                            break

                if len(model_rundata['packet']) > 1:
                    interface.TDATA.next = model_rundata['packet'].popleft()
                    interface.TLAST.next = False
                    interface.TVALID.next = True

                elif len(model_rundata['packet']) == 1:
                    # End of a packet
                    interface.TDATA.next = model_rundata['packet'].popleft()
                    interface.TLAST.next = True
                    interface.TVALID.next = True

                    # Nothing left in the packet
                    del model_rundata['packet']

                else:
                    interface.TVALID.next = False
                    # no data, so simply remove the packet for initialisation 
                    # next time
                    del model_rundata['packet']


        return model_inst

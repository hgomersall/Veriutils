from myhdl import *
import myhdl

from random import randrange
import random
import copy

from math import log, floor

from .utils import check_reset_signal

__all__ = ['random_source', 'clock_source', 'init_reset_source',
           'recorder_sink', 'handler_sink', 'copy_signal',
           'lut_signal_driver', 'AVAILABLE_TIME_UNITS']

# These are the available time units. VHDL can also handle 'hr', 'min', 'sec'
# and 'fs'. These extra time units can be added if required.
AVAILABLE_TIME_UNITS = ['ms', 'us', 'ns', 'ps']

def copy_signal(signal_obj):

    if isinstance(signal_obj, ResetSignal):
        new_signal = ResetSignal(copy.copy(signal_obj._init),
                                 active=signal_obj.active,
                                 isasync=signal_obj.isasync)

        new_signal._val = copy.copy(signal_obj.val)
        return new_signal

    if isinstance(signal_obj, myhdl._Signal._Signal):
        new_signal = Signal(copy.copy(signal_obj._init))
        new_signal._val = copy.copy(signal_obj.val)
        return new_signal

    else:
        new_signal_obj = copy.copy(signal_obj)

        for each in new_signal_obj.__dict__:
            if isinstance(new_signal_obj.__dict__[each],
                          myhdl._Signal._Signal):

                # Call recursively
                new_signal_obj.__dict__[each] = copy_signal(
                    new_signal_obj.__dict__[each])

        return new_signal_obj

clock_source_block_count = 0

@block
def clock_source(clock, period, time_units='ns'):

    if not isinstance(clock, myhdl._Signal._Signal):
        raise ValueError('The passed clock signal is not a signal')

    if time_units not in AVAILABLE_TIME_UNITS:
        raise ValueError(
            'Invalid time unit. Please select from: ' +
            ', '.join(AVAILABLE_TIME_UNITS))

    global clock_source_block_count

    inst_count = clock_source_block_count
    clock_source_block_count += 1

    even_period = period//2
    odd_period = period - even_period

    start_val = int(clock.val)
    not_start_val = int(not clock.val)

    clock_state = Signal(clock.val)

    @instance
    def clockgen():

        while True:
            yield(delay(even_period))
            clock.next = not clock_state
            clock_state.next = not clock_state
            yield(delay(odd_period))
            clock.next = not clock_state
            clock_state.next = not clock_state

    clock_source.verilog_code = '''
initial begin: CLOCK_SOURCE_CLOCKGEN_$inst_count
    while (1'b1) begin
        # $even_period;
        $clock <= (!$clock_state);
        $clock_state <= (!$clock_state);
        # $odd_period;
        $clock <= (!$clock_state);
        $clock_state <= (!$clock_state);
    end
end
'''

    clock_source.vhdl_code = '''
CLOCK_SOURCE_CLOCKGEN_$inst_count: process is
begin
while True loop
    wait for $even_period $time_units;
    $clock <= not $clock_state;
    $clock_state <= not $clock_state;
    wait for $odd_period $time_units;
    $clock <= not $clock_state;
    $clock_state <= not $clock_state;
end loop;
wait;
end process CLOCK_SOURCE_CLOCKGEN_$inst_count;
'''

    # These are required so myhdl knows to create the clock and clock_state
    # signals
    clock.driven = 'reg'
    clock_state.driven = 'reg'

    # This tells myhdl that clock_state is read within the verilog and vhdl
    # code
    clock_state.read = True

    return clockgen

@block
def init_reset_source(reset, clock, edge_sensitivity='posedge'):

    check_reset_signal(reset, 'reset', isasync=reset.isasync,
                       active=reset.active)

    active_edges = 2
    active_reset = reset.active

    # Rather annoyingly, the code becomes non-convertible when the the edge
    # to be yielded is an assigned value rather than clock.posedge or
    # clock.negedge. The consequence is two versions need to be written out.
    if edge_sensitivity == 'posedge':
        @instance
        def init_reset():

            reset.next = active_reset
            yield clock.posedge

            for n in range(active_edges):
                reset.next = active_reset
                yield clock.posedge

            while True:
                reset.next = not active_reset
                yield clock.posedge

    elif edge_sensitivity == 'negedge':
        @instance
        def init_reset():

            reset.next = active_reset
            yield clock.negedge

            for n in range(active_edges):
                reset.next = active_reset
                yield clock.negedge

            while True:
                reset.next = not active_reset
                yield clock.negedge

    else:
        raise ValueError('Invalid edge sensitivity')

    return init_reset

@block
def _signal_random_source(output_signal, clock, reset,
                          edge_sensitivity='posedge'):


    initial_random_state = random.getstate()

    if isinstance(output_signal.val, intbv):

        min_val = output_signal.val.min
        max_val = output_signal.val.max

        next_val_function = lambda: random.randrange(min_val, max_val)

    elif isinstance(output_signal._init, bool):
        min_val = 0
        max_val = 2

        next_val_function = lambda: bool(random.randrange(min_val, max_val))

    elif isinstance(output_signal.val, EnumItemType):

        _enum = output_signal.val._type
        next_val_function = lambda: getattr(_enum,
                                            random.choice(_enum._names))

    else:
        raise ValueError('Invalid signal type: The signal type is not '
                         'supported by the random source.')

    if edge_sensitivity == 'posedge':
        edge = clock.posedge
    elif edge_sensitivity == 'negedge':
        edge = clock.negedge
    else:
        raise ValueError('Invalid edge sensitivity')

    random_state = [initial_random_state]

    @always_seq(edge, reset)
    def source():
        random.setstate(random_state[0])
        output_signal.next = next_val_function()
        random_state[0] = random.getstate()

    return source

@block
def random_source(output_signal, clock, reset, seed=None,
                  edge_sensitivity='posedge'):
    '''Generate random signals on each clock edge - the specific
    clock edge to use is given by ``edge_sensitivity`` and can be either
    `posedge` for positive edge or `negedge` for negative edge.

    The seed to be used can be specified by ``seed``.

    Interfaces are supported and the output should be deterministic if
    seed is specified.
    '''

    if seed is not None:
        random.seed(seed)
    else:
        # Make sure we've moved the random state away from other calls to
        # this function.
        random.seed(randrange(0, 0x5EEDF00D))

    if isinstance(output_signal, myhdl._Signal._Signal):
        return _signal_random_source(output_signal, clock, reset,
                                     edge_sensitivity)

    else:
        signal_list = []

        if isinstance(output_signal, list):
            for each_signal in output_signal:
                if isinstance(each_signal, myhdl._Signal._Signal):
                    signal_list.append(each_signal)

        else:
            attribute_names = sorted(output_signal.__dict__)
            for attribute_name in attribute_names:
                attribute = getattr(output_signal, attribute_name)
                if isinstance(attribute, myhdl._Signal._Signal):
                    signal_list.append(attribute)

        # We need to get the random state in order that we can set it
        # on the first loop iteration.
        random_state = random.getstate()

        sources = []
        for each_signal in signal_list:

            # We only want to generate on the signals.
            random.setstate(random_state)

            random.seed(randrange(0, 0x5EEDF00D))

            random_state = random.getstate()

            sources.append(
                _signal_random_source(each_signal, clock, reset,
                                      edge_sensitivity=edge_sensitivity))


        return sources

@block
def recorder_sink(signal, clock, recorded_output_list,
                  edge_sensitivity='posedge'):
    '''Record the value on signal on each clock edge. The edge
    sensitivity is given by `edge_sensitivity` and can be either `posedge`
    for positive edge or `negedge` for negative edge.

    A list is passed in as `recorded_output_list` which is appended on
    each clock cycle with the next value given on `signal`

    If the signal is a list, then each value appended is a list, with
    entries given only by the Signals in the list, in the same order.
    Non-signals are ignored.

    If the signal is an interface, each value appended is a dictionary, with
    keys provided by the attribute names making up the interface. Only
    one level of interface is currently supported.

    Only attributes in object's __dict__ are supported on the interface.
    '''

    if edge_sensitivity == 'posedge':
        edge = clock.posedge
    elif edge_sensitivity == 'negedge':
        edge = clock.negedge
    else:
        raise ValueError('Invalid edge sensitivity')


    reset_signal = ResetSignal(bool(0), active=1, isasync=False)

    if isinstance(signal, myhdl._Signal._Signal):
        @always_seq(edge, reset_signal)
        def recorder():
            _recorded_output = copy.copy(signal.val)
            recorded_output_list.append(_recorded_output)

    else:

        if isinstance(signal, list):

            @always_seq(edge, reset_signal)
            def recorder():
                _recorded_output = [
                    copy.copy(each_sig.val) for each_sig in signal if
                    isinstance(each_sig, myhdl._Signal._Signal)]
                recorded_output_list.append(_recorded_output)

        else:

            @always_seq(edge, reset_signal)
            def recorder():
                interface_signals = {
                    key: signal.__dict__[key] for key in signal.__dict__ if
                    isinstance(signal.__dict__[key], myhdl._Signal._Signal)}

                _recorded_output = {key: copy.copy(interface_signals[key].val)
                                    for key in interface_signals}
                recorded_output_list.append(_recorded_output)

    return recorder

@block
def handler_sink(
    signal, clock, handler, edge_sensitivity='posedge'):
    '''Passes the value on `signal` on each clock edge to a handler. The edge
    sensitivity is given by `edge_sensitivity` and can be either `posedge`
    for positive edge or `negedge` for negative edge.

    On each clock edge, `handler` will be called, which should be a callable
    that takes one argument which is the signal value on that clock cycle.

    It is up to the handler what it does with the value.

    If `signal` is not an instance of `Signal`, a ValueError will be raised.
    '''

    if edge_sensitivity == 'posedge':
        edge = clock.posedge
    elif edge_sensitivity == 'negedge':
        edge = clock.negedge
    else:
        raise ValueError('Invalid edge sensitivity')

    @always(edge)
    def signal_handler():
        handler(copy.copy(signal.val))

    return signal_handler

@block
def _signal_driver_name_annotation(signal, name):

    @always_comb
    def non_block():
        signal

    annotation = '<name_annotation> $signal %s' % name
    _signal_driver_name_annotation.vhdl_code = '-- %s' % annotation
    _signal_driver_name_annotation.verilog_code = '// %s' % annotation

    return non_block

@block
def lut_signal_driver(sig, drive_lut, clock, edge_sensitivity='posedge',
                     signal_name=None):
    '''Drive the output from a look-up table. The lookup table is defined by
    `lut` which should be an iterable object.

    `sig` is updated on each positive or negative clock edge from the
    next value in the lookup table.

    The lookup table will wrap around when all the values are exhausted.

    The clock edge sensitivity is set by the ``edge_sensitivity`` argument and
    can be either `posedge` for positive edge or `negedge` for negative edge.

    If ``signal_name`` is a string, then an annotation is made to the
    output of the conversion. This is a comment containing:
        ``<name_annotation> internal_converted_name signal_name``

    ``internal_converted_name`` is whatever name MyHDL assigns the signal
    in the converted file and ``signal_name`` is whatever is passed to this
    function. This is a bit of a hack on MyHDL to allow calling code to
    explicitly denote what the signal lookup should be.
    '''

    if edge_sensitivity not in ('posedge', 'negedge'):
        raise ValueError('Invalid edge sensitivity')

    drive_lut = tuple(int(each) for each in drive_lut)

    if len(drive_lut) == 0:
        raise ValueError('Invalid zero length lut: The lut should not be '
                         'empty')

    lut_length = len(drive_lut)

    if edge_sensitivity == 'posedge':
        @instance
        def lut_driver():
            lut_idx = intbv(0, min=0, max=len(drive_lut))
            while True:
                sig.next = drive_lut[lut_idx]
                yield clock.posedge
                if lut_idx + 1 >= lut_length:
                    lut_idx[:] = 0
                else:
                    lut_idx[:] = lut_idx + 1

    else:
        @instance
        def lut_driver():
            lut_idx = intbv(0, min=0, max=len(drive_lut))
            while True:
                sig.next = drive_lut[lut_idx]
                yield clock.negedge
                if lut_idx + 1 >= lut_length:
                    lut_idx[:] = 0
                else:
                    lut_idx[:] = lut_idx + 1

    if signal_name is not None:
        return _signal_driver_name_annotation(sig, signal_name), lut_driver
    else:
        return lut_driver


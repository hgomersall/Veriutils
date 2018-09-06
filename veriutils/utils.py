
from myhdl import intbv
import myhdl
from math import log, floor

__all__ = ['check_intbv_signal', 'check_bool_signal', 'check_reset_signal',
           'signed_intbv_list_to_unsigned', 'unsigned_intbv_list_to_signed',
           'signed_int_list_to_unsigned', 'unsigned_int_list_to_signed']

def check_intbv_signal(test_signal, name, correct_width=None, signed=None,
                       val_range=None, range_test='inside'):
    '''Check the passed signal is a satisfactory convertible signal. If it
    is not, raise a ValueError with a suitable error message.

    The range is set from one of either ``correct_width`` and (optionally)
    ``signed`` or ``val_range``.

    The three possible values for ``range_test`` are ``'inside'``,
    ``'outside'`` and ``'exact'``. For values ``val_range = (n, p)``, each
    asserts the following is true:
        ``'inside'``: ``test_signal.min >= n``, ``test_signal.max <= p``
        ``'outside'``: ``test_signal.min <= n``, ``test_signal.max >= p``
        ``'exact'``: ``test_signal.min == n``, ``test_signal.max == p``

    ``correct_width`` checks the signal is of a specific correct width. If
    ``signed`` is set, it also checks the signedness of the signal.
    '''

    if correct_width is None and val_range is None:
        raise ValueError('There should be at least a correct_width or a '
                         'val_range set in the arguments.')

    if not isinstance(test_signal, myhdl._Signal._Signal):
        raise ValueError('Port %s should be an intbv Signal' % (name,))

    if correct_width is None:
        # assume the correct width is given by the signal
        correct_width = len(test_signal)

    if isinstance(test_signal.val, bool):
        signal_min = 0
        signal_max = 2 # remember, exclusive upper bound
    else:
        signal_min = test_signal.min
        signal_max = test_signal.max

    if val_range is None:
        val_range = (signal_min, signal_max)

    if signed is None:
        if val_range[0] < 0:
            signed = True
        else:
            signed = False

    if correct_width > 1:
        if not isinstance(test_signal.val, intbv):
            raise ValueError('Port %s signal of width %d should be a '
                             'fixed width intbv value.' %
                             (name, correct_width))
    else:
        if not isinstance(test_signal.val, (intbv, bool)):
            raise ValueError('Port %s signal of width %d should be a '
                             'single bit intbv value or a boolean value.' %
                             (name, correct_width))

    if len(test_signal) == 0:
        raise ValueError('Port %s must have a defined length signal.' %
                         (name,))

    if len(test_signal) != correct_width:
        raise ValueError('Port %s should be %d bits wide' %
                         (name, correct_width))

    if signed and isinstance(test_signal.val, bool):
        raise ValueError('Port %s: A boolean signal should not be implicitly '
            'signed. Use a signed intbv signal instead.' % (name,))

    elif signed and test_signal.min >= 0:
        raise ValueError('Port %s should be a signed intbv signal.' %
                         (name,))

    elif (isinstance(test_signal.val, intbv) and not signed
          and test_signal.min < 0): # pragma: no branch
        raise ValueError('Port %s should be an unsigned intbv signal.' %
                         (name,))

    if range_test == 'inside':
        if signal_min < val_range[0] or signal_max > val_range[1]:
            raise ValueError('Port %s.min should be >= %d and port %s.max '
                             'should be <= %d.' %
                             (name, val_range[0], name, val_range[1]))

    elif range_test == 'outside':
        if signal_min > val_range[0] or signal_max < val_range[1]:
            raise ValueError('Port %s.min should be <= %d and port %s.max '
                             'should be >= %d.' %
                             (name, val_range[0], name, val_range[1]))

    elif range_test == 'exact':
        if signal_min != val_range[0] or signal_max != val_range[1]:
            raise ValueError('Port %s.min should be == %d and port %s.max '
                             'should be == %d.' %
                             (name, val_range[0], name, val_range[1]))

    else:
        raise ValueError('`range_test` should be one of \'inside\', '
                         '\'outside\' or \'exact\'')

def check_bool_signal(test_signal, name):

    if not isinstance(test_signal, myhdl._Signal._Signal):
        raise ValueError('Port %s should be a bool Signal' % (name,))

    if not isinstance(test_signal.val, (intbv, bool)):
        raise ValueError('Port %s signal should be a boolean value or a '
                         'single bit intbv value.' % (name,))

    if isinstance(test_signal.val, intbv) and len(test_signal) != 1:
        raise ValueError ('Port %s signal: intbv signals should only be a '
                          'single bit.' % (name,))

def check_reset_signal(test_signal, name, active, isasync):

    if not isinstance(test_signal, myhdl.ResetSignal):
        raise ValueError('Port %s should be a ResetSignal' % (name,))

    if test_signal.isasync != isasync:
        raise ValueError('Port %s reset signal should have the expected'
                         ' isasync flag.' % (name,))

    if test_signal.active != active:
        raise ValueError('Port %s reset signal should have the expected'
                         ' active flag.' % (name,))

def signed_intbv_list_to_unsigned(signed_list):

    unsigned_list = [val[len(val):] for val in signed_list]

    return unsigned_list

def unsigned_intbv_list_to_signed(unsigned_list):

    signed_list = [val.signed() for val in unsigned_list]

    return signed_list

def signed_int_list_to_unsigned(signed_list, bit_length):

    signed_intbv_list= [
        intbv(val, min=-2**(bit_length-1), max=2**(bit_length-1))
        for val in signed_list]

    unsigned_intbv_list = (
        signed_intbv_list_to_unsigned(signed_intbv_list))

    return [int(each) for each in unsigned_intbv_list]

def unsigned_int_list_to_signed(unsigned_list, bit_length):

    unsigned_intbv_list = [
        intbv(val)[bit_length:] for val in unsigned_list]

    signed_intbv_list = (
        unsigned_intbv_list_to_signed(unsigned_intbv_list))

    return [int(each) for each in signed_intbv_list]


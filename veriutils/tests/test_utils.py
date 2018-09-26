
from .base_hdl_test import TestCase
from myhdl import Signal, ResetSignal, intbv, enum, bin
from veriutils import (
    check_intbv_signal, check_bool_signal, check_reset_signal,
    signed_intbv_list_to_unsigned, unsigned_intbv_list_to_signed,
    signed_int_list_to_unsigned, unsigned_int_list_to_signed)

import random

class TestCheckIntbvSignal(TestCase):
    '''There should be a check on intbv signals, making sure the signal fits
    with what should be expected.
    '''

    def test_is_signal(self):
        '''The test signal should be an instance of _Signal
        '''
        self.assertRaisesRegex(
            ValueError, 'Port %s should be an intbv Signal' % ('foo',),
            check_intbv_signal, 'not a signal', 'foo', 10, False)

    def test_single_bit_val_type(self):
        '''Single bit signals should be bools or intbvs.
        '''
        working_test_cases = (
            ('foo', Signal(intbv(0)[1:]), 1, False),
            ('bar', Signal(bool(0)), 1, False))

        for name, signal, width, signed in working_test_cases:
            # Should pass fine
            check_intbv_signal(signal, name, width, signed)

        failing_test_cases = (
            ('foo', Signal('bleh'), 1, False),
            ('bar', Signal(10), 1, False))

        for name, signal, width, signed in failing_test_cases:
            self.assertRaisesRegex(
                ValueError, 'Port %s signal of width %d should be a '
                'single bit intbv value or a boolean value.' % (name, width),
                check_intbv_signal, signal, name, width, signed)

    def test_at_least_one_of_width_or_val_range(self):
        '''The check should be passed at least a width or a val_range.

        If neither is passed, a ValueError should be raised.
        '''
        self.assertRaisesRegex(
            ValueError, 'There should be at least a correct_width or a '
            'val_range set in the arguments.',
            check_intbv_signal, Signal(intbv(0)[1:]), 'foo', signed=False)


    def test_intbv_range_inside(self):
        '''Setting the val_range and range_test='inside' should check the
        range of the signal is inclusively inside the val_range supplied.

        The val_range should be defined by list-like object with the first
        value giving the minimum expected inclusive minimum value of the intbv
        and the second value giving the maximum expected exclusive maximum
        value of the intbv.

        That is, if val_range = (n, p), the min attribute of the signal should
        be >= n and the max attribute should be <= p.
        '''
        test_cases = (
            ('foo', Signal(intbv(200, min=100, max=500)),
             (101, 499), (0, 501)),
            ('foo2', Signal(intbv(0)[5:]), (0, 2**5 - 1), (0, 2**5 + 1)),
            ('bar', Signal(intbv(0, min=-40, max=50)), (-40, 49), (-40, 51)),
            ('boo', Signal(intbv(0, min=-40, max=50)), (-39, 50), (-41, 50)),
            ('baz', Signal(intbv(10, min=-(2**10), max=2**10)),
             (-1023, 1024), (-1025, 1024)),
            ('bleh', Signal(bool(0)), (0, 1), (0, 3))
        )

        for name, signal, smaller_range, bigger_range in test_cases:

            # Should work
            if not isinstance(signal.val, bool):
                correct_val_range = (signal.min, signal.max)

                if signal.min < 0:
                    signed = True
                else:
                    signed = False

            else:
                correct_val_range = (0, 2)
                signed = False

            # Exact and bigger ranges should pass
            check_intbv_signal(signal, name, val_range=correct_val_range,
                               range_test='inside')
            check_intbv_signal(signal, name, val_range=bigger_range,
                               range_test='inside')

            # smaller range should fail
            self.assertRaisesRegex(
                ValueError, 'Port %s.min should be >= %d and port %s.max '
                'should be <= %d.' %
                (name, smaller_range[0], name, smaller_range[1]),
                check_intbv_signal, signal, name, val_range=smaller_range,
                range_test='inside')

    def test_intbv_range_outside(self):
        '''Setting the val_range and range_test='outside' should check the
        range of the signal is inclusively outside the val_range supplied.

        The val_range should be defined by list-like object with the first
        value giving the maximum expected inclusive minimum value of the intbv
        and the second value giving the minimum expected exclusive maximum
        value of the intbv.

        That is, if val_range = (n, p), the min attribute of the signal should
        be <= n and the max attribute should be >= p.
        '''
        test_cases = (
            ('foo', Signal(intbv(200, min=100, max=500)),
             (101, 499), (0, 501)),
            ('foo2', Signal(intbv(0)[5:]), (0, 2**5 - 1), (0, 2**5 + 1)),
            ('bar', Signal(intbv(0, min=-40, max=50)), (-40, 49), (-40, 51)),
            ('boo', Signal(intbv(0, min=-40, max=50)), (-39, 50), (-41, 50)),
            ('baz', Signal(intbv(10, min=-(2**10), max=2**10)),
             (-1023, 1024), (-1025, 1024)),
            ('bleh', Signal(bool(0)), (0, 1), (0, 3))
        )

        for name, signal, smaller_range, bigger_range in test_cases:

            # Should work
            if not isinstance(signal.val, bool):
                correct_val_range = (signal.min, signal.max)

                if signal.min < 0:
                    signed = True
                else:
                    signed = False

            else:
                correct_val_range = (0, 2)
                signed = False

            # Exact and smaller ranges should pass
            check_intbv_signal(signal, name, val_range=correct_val_range,
                               range_test='outside')
            check_intbv_signal(signal, name, val_range=smaller_range,
                               range_test='outside')

            # bigger range should fail
            self.assertRaisesRegex(
                ValueError, 'Port %s.min should be <= %d and port %s.max '
                'should be >= %d.' %
                (name, bigger_range[0], name, bigger_range[1]),
                check_intbv_signal, signal, name, val_range=bigger_range,
                range_test='outside')


    def test_intbv_range_exact(self):
        '''Setting the val_range and range_test='exact' should check the
        range of the signal is exactly the val_range supplied.

        The val_range should be defined by list-like object with the first
        value giving the expected minimum value of the intbv
        and the second value giving the expected maximum value of the intbv.

        That is, if val_range = (n, p), the min attribute of the signal should
        be == n and the max attribute should be == p.
        '''
        test_cases = (
            ('foo', Signal(intbv(200, min=100, max=500)),
             (101, 499), (0, 501)),
            ('foo2', Signal(intbv(0)[5:]), (0, 2**5 - 1), (0, 2**5 + 1)),
            ('bar', Signal(intbv(0, min=-40, max=50)), (-40, 49), (-40, 51)),
            ('boo', Signal(intbv(0, min=-40, max=50)), (-39, 50), (-41, 50)),
            ('baz', Signal(intbv(10, min=-(2**10), max=2**10)),
             (-1023, 1024), (-1025, 1024)),
            ('bleh', Signal(bool(0)), (0, 1), (0, 3))
        )

        for name, signal, smaller_range, bigger_range in test_cases:

            # Should work
            if not isinstance(signal.val, bool):
                correct_val_range = (signal.min, signal.max)

                if signal.min < 0:
                    signed = True
                else:
                    signed = False

            else:
                correct_val_range = (0, 2)
                signed = False

            # Exact range should pass
            check_intbv_signal(signal, name, val_range=correct_val_range,
                               range_test='exact')

            # smaller range should fail
            self.assertRaisesRegex(
                ValueError, 'Port %s.min should be == %d and port %s.max '
                'should be == %d.' %
                (name, smaller_range[0], name, smaller_range[1]),
                check_intbv_signal, signal, name, val_range=smaller_range,
                range_test='exact')

            # bigger range should fail
            self.assertRaisesRegex(
                ValueError, 'Port %s.min should be == %d and port %s.max '
                'should be == %d.' %
                (name, bigger_range[0], name, bigger_range[1]),
                check_intbv_signal, signal, name, val_range=bigger_range,
                range_test='exact')

    def test_invalid_range_test_raises(self):
        '''A range_test that is not valid should raise a ValueError.

        The valid range_test values are 'outside', 'inside' and 'exact'.
        '''
        val_range = (100, 500)
        signal = Signal(intbv(200, min=val_range[0], max=val_range[1]))
        self.assertRaisesRegex(
            ValueError, '`range_test` should be one of \'inside\', '
            '\'outside\' or \'exact\'',
            check_intbv_signal, signal, 'signal', val_range=val_range,
            range_test='invalid')

    def test_None_signed_inferred_from_signal(self):
        '''If signed is not set or set to None, it should be inferred.
        '''
        test_cases = (
            ('foo', Signal(intbv(1, min=0, max=10))),
            ('foo2', Signal(intbv(0, min=-10, max=10))),
            ('bar', Signal(intbv(0, min=-4, max=10))),
            ('baz', Signal(bool(0))))

        for name, signal in test_cases:
            # Should all pass
            check_intbv_signal(signal, name, len(signal))

    def test_signed_true_check(self):
        '''Unsigned signals should be detected if a signed is needed.
        '''
        test_cases = (
            ('foo', Signal(intbv(1)[1:]), 1),
            ('foo', Signal(intbv(0)[5:]), 5),
            ('bar', Signal(intbv(0)[3:]), 3),
            ('baz', Signal(intbv(10)[5:]), 5),
            ('bat', Signal(intbv(10, min=0, max=100)), 7))

        for name, signal, width in test_cases:
            # Should work
            check_intbv_signal(signal, name, width, False)

            # signed True should raise
            self.assertRaisesRegex(
                ValueError, 'Port %s should be a signed intbv signal.' %
                (name,), check_intbv_signal, signal, name, width, True)

    def test_signed_true_bool_fails(self):
        '''A bool should never be allowed to be implicitly signed.
        '''
        self.assertRaisesRegex(
            ValueError, 'Port %s: A boolean signal should not be implicitly '
            'signed. Use a signed intbv signal instead.' % ('foo',),
            check_intbv_signal, Signal(bool(0)), 'foo', 1, True)


    def test_signed_false_check(self):
        '''Signed signals should be detected if an unsigned is needed.
        '''
        test_cases = (
            ('bat', Signal(intbv(-1, min=-1, max=1)), 1),
            ('bat', Signal(intbv(0, min=-1, max=1)), 1),
            ('bat', Signal(intbv(9, min=-20, max=10)), 6),
            ('boo', Signal(intbv(-20, min=-100, max=0)), 8))

        for name, signal, width in test_cases:
            # Should work
            check_intbv_signal(signal, name, width, True)

            # signed False should raise
            self.assertRaisesRegex(
                ValueError, 'Port %s should be an unsigned intbv signal.' %
                (name,), check_intbv_signal, signal, name, width, False)

    def test_unlengthed_signal_fails(self):
        '''Values without a length should fail.
        '''
        failing_test_cases = (
            ('foo', Signal(intbv(0)), 3, False),
            ('baz', Signal(intbv(100)), 3, False))

        for name, signal, width, signed in failing_test_cases:
            self.assertRaisesRegex(
                ValueError, 'Port %s must have a defined length signal.' %
                (name,), check_intbv_signal, signal, name, width, signed)

    def test_non_single_bit_val_is_correct_type(self):
        '''intbv values should always be the correct length.
        '''
        working_test_cases = (
            ('foo', Signal(intbv(0)[5:]), 5, False),
            ('bar', Signal(intbv(0)[3:]), 3, False),
            ('baz', Signal(intbv(10)[10:]), 10, False),
            ('bat', Signal(intbv(9, min=-20, max=10)), 6, True))

        for name, signal, width, signed in working_test_cases:
            check_intbv_signal(signal, name, width, signed)

        failing_test_cases = (
            ('foo', Signal('dfsd'), 10, False),
            ('bar', Signal(10), 10, False))

        for name, signal, width, signed in failing_test_cases:
            self.assertRaisesRegex(
                ValueError, 'Port %s signal of width %d should be a '
                'fixed width intbv value.' % (name, width),
                check_intbv_signal, signal, name, width, signed)

    def test_port_width_wrong_raises(self):
        '''For incorrect Signal bitwidth, a ValueError should be raised.
        '''
        test_cases = (
            ('foo', Signal(intbv(0)[1:]), 1, 2, False),
            ('bar', Signal(intbv(0)[3:]), 3, 2, False),
            ('baz', Signal(intbv(0)[3:]), 3, 4, False),
            ('bat', Signal(intbv(9, min=-20, max=10)), 6, 2, True))

        for name, test_signal, correct_width, incorrect_width, signed in (
            test_cases):

            # Should work
            check_intbv_signal(test_signal, name, correct_width, signed)

            # Should raise
            self.assertRaisesRegex(
                ValueError,
                'Port %s should be %d bits wide' % (name, incorrect_width,),
                check_intbv_signal, test_signal, name, incorrect_width,
                signed)



class TestCheckBoolSignal(TestCase):
    '''There should be a check on bool signals, making sure the signal fits
    with what should be expected.
    '''
    def test_is_signal(self):
        '''The test signal should be an instance of _Signal
        '''
        self.assertRaisesRegex(
            ValueError, 'Port %s should be a bool Signal' % ('foo',),
            check_bool_signal, 'not a signal', 'foo')

    def test_single_bit_intbv_check(self):
        '''intbv signals should be checked they are only a single bit.
        '''
        failing_test_cases = (
            ('foo', Signal(intbv(10))),
            ('foo', Signal(intbv(0)[5:])),
            ('bar', Signal(intbv(0)[2:])),
            ('bar', Signal(intbv(0))))

        for name, signal in failing_test_cases:
            self.assertRaisesRegex(
                ValueError, 'Port %s signal: intbv signals should only be a '
                'single bit.' % (name,),
                check_bool_signal, signal, name)

    def test_val_type_check(self):
        '''Signals should be bools or single bit intbvs.
        '''
        working_test_cases = (
            ('foo', Signal(intbv(0)[1:])),
            ('bar', Signal(bool(0))))

        for name, signal in working_test_cases:
            # Should pass fine
            check_bool_signal(signal, name)

        test_enum = enum('a', 'b')

        failing_test_cases = (
            ('foo', Signal('bleh')),
            ('foo', Signal(test_enum.a)),
            ('bar', Signal((10))),
            ('bar', Signal(0)))

        for name, signal in failing_test_cases:
            self.assertRaisesRegex(
                ValueError, 'Port %s signal should be a boolean value or a '
                'single bit intbv value.' % (name,),
                check_bool_signal, signal, name)

class TestCheckResetSignal(TestCase):
    '''There should be a check on reset signals, making sure the signal fits
    with what should be expected.
    '''
    def test_is_signal(self):
        '''The test signal should be an instance of ResetSignal
        '''
        self.assertRaisesRegex(
            ValueError, 'Port %s should be a ResetSignal' % ('foo',),
            check_reset_signal, Signal(bool(0)), 'foo', False, False)

    def test_isasync_correct(self):
        '''For incorrect isasync flags, a ValueError should be raised.

        The isasync flag of the ResetSignal should agree with that passed to
        the test function.
        '''

        name = 'foo'
        for isasync in (True, False):

            test_signal = ResetSignal(0, active=True, isasync=isasync)

            # Should pass fine
            check_reset_signal(test_signal, name, isasync=isasync, active=True)

            self.assertRaisesRegex(
                ValueError, 'Port %s reset signal should have the expected'
                ' isasync flag.' % (name,),
                check_reset_signal, test_signal, name, active=True,
                isasync=not isasync)

    def test_active_correct(self):
        '''For incorrect active flags, a ValueError should be raised.

        The active flag of the ResetSignal should agree with that passed to
        the test function.
        '''

        name = 'foo'
        for active in (True, False):

            test_signal = ResetSignal(0, active=active, isasync=False)

            # Should pass fine
            check_reset_signal(test_signal, name, isasync=False, active=active)

            self.assertRaisesRegex(
                ValueError, 'Port %s reset signal should have the expected'
                ' active flag.' % (name,),
                check_reset_signal, test_signal, name, active=not active,
                isasync=False)

class TestSignedIntbvListToUnsigned(TestCase):

    def test_list_of_ints(self):
        '''A list of signed intbv values should be converted to a list of
        unsigned intbv values with the equivalent bit values.
        '''
        sizes = [random.randrange(4, 20) for n in range(1000)]

        signed_list = [intbv(random.randrange(-2**(size-1), 2**(size-1)),
                            -2**(size-1), 2**(size-1)) for size in sizes]


        unsigned_list = [
            int(bin(~(-val) + 1, len(val)), 2) if val < 0 else int(val) for
            val in signed_list]

        test_output = signed_intbv_list_to_unsigned(signed_list)

        assert(all([val >= 0 for val in unsigned_list]))
        self.assertEqual(test_output, unsigned_list)
        self.assertEqual([len(val) for val in test_output], sizes)

class TestUnsignedIntbvListToSigned(TestCase):

    def test_list_of_ints(self):
        '''A list of unsigned intbv values should be converted to a list of
        signed intbv values with the equivalent bit values.
        '''
        sizes = [random.randrange(4, 20) for n in range(1000)]

        unsigned_list = [
            intbv(random.randrange(0, 2**(size)))[size:] for size in sizes]

        signed_list = [
            int(val) - 2**len(val) if val >= 2**(len(val) - 1) else int(val)
            for val in unsigned_list]

        test_output = unsigned_intbv_list_to_signed(unsigned_list)

        self.assertEqual(test_output, signed_list)
        self.assertEqual([len(val) for val in test_output], sizes)

class TestSignedIntListToUnsigned(TestCase):

    def test_list_of_ints(self):
        '''A list of signed int values should be converted to a list of
        unsigned int values with the equivalent bit values, when provided
        with a suitable bit length.
        '''
        size = random.randrange(4, 20)

        signed_list = [intbv(random.randrange(-2**(size-1), 2**(size-1)),
                            -2**(size-1), 2**(size-1)) for n in range(1000)]


        unsigned_list = [
            int(bin(~(-val) + 1, len(val)), 2) if val < 0 else int(val) for
            val in signed_list]

        int_signed_list = [int(each) for each in signed_list]
        int_unsigned_list = [int(each) for each in unsigned_list]

        test_output = signed_int_list_to_unsigned(signed_list, size)

        assert(all([val >= 0 for val in unsigned_list]))

        self.assertEqual(test_output, int_unsigned_list)

class TestUnsignedIntListToSigned(TestCase):

    def test_list_of_ints(self):
        '''A list of unsigned int values should be converted to a list of
        signed int values with the equivalent bit values, when provided
        with a suitable bit length.
        '''
        size = random.randrange(4, 20)

        unsigned_list = [
            intbv(random.randrange(0, 2**(size)))[size:] for n in range(1000)]

        signed_list = [
            int(val) - 2**len(val) if val >= 2**(len(val) - 1) else int(val)
            for val in unsigned_list]

        int_signed_list = [int(each) for each in signed_list]
        int_unsigned_list = [int(each) for each in unsigned_list]

        test_output = unsigned_int_list_to_signed(unsigned_list, size)

        self.assertEqual(test_output, int_signed_list)

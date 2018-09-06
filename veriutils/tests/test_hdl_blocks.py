
from veriutils.tests.base_hdl_test import HDLTestCase, TestCase
from veriutils import *
from myhdl import *
from myhdl import ToVerilogWarning, ToVHDLWarning
import myhdl

import copy
from random import randrange
import random
import tempfile
import shutil
from math import log

import warnings
import os


class TestSignalCopy(TestCase):
    '''There should be a function that returns a copy of its argument,
    focussed primarily on copying Signals, in which we really need to copy
    the value of the signal.

    It should be able to work out whether it is a Signal to be copied, or
    a class instance with Signal attributes.
    '''
    def test_signal_copy(self):
        '''It should be possible to copy MyHDL signals.

        The copied signals should have the same min and max values.
        '''
        a = Signal(intbv(10)[5:])
        b = copy_signal(a)
        self.assertEqual(a, b)
        self.assertIsNot(a, b)
        self.assertIsNot(a.val, b.val)

        self.assertEqual(a.min, b.min)
        self.assertEqual(a.max, b.max)

    def test_copy_retains_original_init(self):
        '''The copied signal should have the same init as the original.
        '''
        a = Signal(intbv(10)[5:])
        a.val[:] = 5
        b = copy_signal(a)

        self.assertEqual(a._init, b._init)

    def test_interface_retains_original_inits(self):
        '''The copied interface should have the same init as the original.
        '''
        class Interface(object):
            def __init__(self):
                self.foo = 'not a signal'
                self.a = Signal(intbv(5)[5:])
                self.b = Signal(intbv(2)[7:])

        interface_a = Interface()
        interface_a.a.val[:] = 3
        interface_a.b.val[:] = 6

        interface_b = copy_signal(interface_a)

        self.assertEqual(interface_a.a._init, interface_b.a._init)
        self.assertEqual(interface_a.b._init, interface_b.b._init)

    def test_interface_copy(self):
        '''It should be possible to copy interfaces.

        The copied signals should have the same min and max values.
        '''
        class Interface(object):
            def __init__(self):
                self.foo = 'not a signal'
                self.a = Signal(intbv(0)[5:])
                self.b = Signal(intbv(0)[7:])

        interface_a = Interface()
        interface_b = copy_signal(interface_a)

        self.assertEqual(interface_a.a, interface_b.a)
        self.assertEqual(interface_a.b, interface_b.b)

        self.assertEqual(interface_a.a.min, interface_b.a.min)
        self.assertEqual(interface_a.b.min, interface_b.b.min)

        self.assertEqual(interface_a.a.max, interface_b.a.max)
        self.assertEqual(interface_a.b.max, interface_b.b.max)

        self.assertIsNot(interface_a, interface_b)

        self.assertIsNot(interface_a.a, interface_b.a)
        self.assertIsNot(interface_a.b, interface_b.b)

        self.assertIsNot(interface_a.a.val, interface_b.a.val)
        self.assertIsNot(interface_a.b.val, interface_b.b.val)

    def test_reset_signal_copy(self):
        '''It should be possible to copy reset signals.

        The copied signal should have the same attributes as the original.
        '''
        test_cases = ((0, False, False),
                      (False, True, False),
                      (1, True, True),
                      (True, False, False))

        for init, active, isasync in test_cases:
            a = ResetSignal(0, active=False, isasync=False)
            b = copy_signal(a)
            self.assertTrue(isinstance(b, ResetSignal))
            self.assertEqual(a, b)
            self.assertIsNot(a, b)

            if not isinstance(a.val, bool):
                self.assertIsNot(a.val, b.val)

            self.assertEqual(a.active, b.active)
            self.assertEqual(a.isasync, b.isasync)


class TestClockSource(TestCase):
    '''There should be a clock source that takes a boolean signal and a
    period and returns a clock signal.

    If the period is even, then even states of the clock should be the same
    length as odd states of the clock.

    If the period is odd, then the even states of the clock should be one time
    interval shorter than the even states.

    The following example is a starting value of high, corresponding to even
    periods high:

    Period:        0  1  2  3  4  5
    Clock output: ---___---___---___

    Whether the odd periods correspond to high or low should be determined
    by the starting value.
    '''
    def check_clock_correct(self, period, even_length, start_val):
        clock = Signal(bool(start_val))
        time = [0]

        dut = clock_source(clock, period)

        @block
        def top():
            dut = clock_source(clock, period)

            @always(delay(1))
            def check_every_interval():
                if time[0] % period < even_length:
                    self.assertEqual(clock.val, start_val)
                else:
                    self.assertEqual(clock.val, not(start_val))

                time[0] += 1

            return dut, check_every_interval

        top_level_block = top()
        top_level_block.run_sim(duration=10*period, quiet=1)
        top_level_block.quit_sim()

    def test_not_signal(self):
        '''Passing something that is not a signal should raise a ValueError
        '''
        not_a_signal = 'A string'
        self.assertRaisesRegex(ValueError, 'The passed clock signal is not '
                               'a signal', clock_source, not_a_signal, 10)

    def test_even_period_high_start(self):
        '''Even period with high start should give high on every even interval
        '''
        period = 10
        self.check_clock_correct(period, period//2, True)

    def test_even_period_low_start(self):
        '''Even period with low start should give low on every even interval
        '''
        period = 10
        self.check_clock_correct(period, period//2, False)

    def test_odd_period_high_start(self):
        '''Odd period with high start should give high on every even interval
        '''
        period = 9
        self.check_clock_correct(period, period//2, False)

    def test_odd_period_low_start(self):
        '''Odd period with low start should give low on every even interval
        '''
        period = 9
        self.check_clock_correct(period, period//2, False)

    def test_even_period_convertible_to_VHDL(self):
        '''The even period clock should convert without error to VHDL
        '''
        clock = Signal(bool(0))

        period = 10
        test_block = clock_source(clock, period)
        tmp_dir = tempfile.mkdtemp()

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    'ignore',
                    message='Output port is read internally: clock',
                    category=ToVHDLWarning)

                test_block.convert(hdl='VHDL', path=tmp_dir)

        finally:
            shutil.rmtree(tmp_dir)

    def test_odd_period_convertible_to_VHDL(self):
        '''The odd period clock should convert without error to VHDL
        '''
        clock = Signal(bool(0))

        period = 9
        test_block = clock_source(clock, period)
        tmp_dir = tempfile.mkdtemp()

        try:
            test_block.convert(hdl='VHDL', path=tmp_dir)

        finally:
            shutil.rmtree(tmp_dir)

    def test_even_period_convertible_to_Verilog(self):
        '''The even period clock should convert without error to Verilog
        '''
        clock = Signal(bool(0))

        period = 10
        test_block = clock_source(clock, period)
        tmp_dir = tempfile.mkdtemp()

        try:

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    'ignore',
                    message='Output port is read internally: clock',
                    category=myhdl.ToVerilogWarning)

                test_block.convert(hdl='Verilog', path=tmp_dir)
        finally:
            shutil.rmtree(tmp_dir)

    def test_odd_period_convertible_to_Verilog(self):
        '''The odd period clock should convert without error to Verilog
        '''
        clock = Signal(bool(0))

        period = 9
        test_block = clock_source(clock, period)
        tmp_dir = tempfile.mkdtemp()

        tmp_dir = tempfile.mkdtemp()
        try:
            test_block.convert(hdl='Verilog', path=tmp_dir)

        finally:
            shutil.rmtree(tmp_dir)

class TestInitResetSource(HDLTestCase):
    '''There should be a initialisation reset source factory for generating
    instances that output high for the first three periods in order to reset
    everything, and then goes permanently low.
    '''

    def setUp(self):
        self.clock = Signal(bool(1))

        # Keep things simple (for the edge sensitivity test) and enforce an
        # even clock period
        self.clock_period = 10

        self.reset_signal = ResetSignal(0, active=True, isasync=False)

        self.default_args = {
            'reset': self.reset_signal,
            'clock': self.clock}

    def test_reset_signal_checked(self):
        '''The init_reset_source should only allow a ResetSignal.
        '''
        self.do_port_check_reset_test(init_reset_source, 'reset',
                                      self.reset_signal.active,
                                      self.reset_signal.isasync)

    def test_posedge_reset_sequence(self):
        '''The reset sequence should be three active cycles, then inactive.

        The idea is to allow the DUT etc to be reset to a known state prior
        to running the simulation.

        The three active cycles should include the starting condition, so
        from the perspective of the reset source, the output should be
        set active on the first two clock transitions.

        The default is to use a positive edge sensitivity.
        '''

        for clock_start in (0, 1):
            clock = Signal(bool(clock_start))

            dummy_reset = ResetSignal(intbv(0), active=1, isasync=False)
            n_runs = 99
            clock_idx = [0]

            @block
            def top():
                @always(delay(self.clock_period//2))
                def output_check():

                    if clock == True:
                        clock_idx[0] += 1

                        # positive edge
                        # The clock_start offset is because we need to ignore
                        # the starting value.
                        if clock_idx[0] < 3 + clock_start:
                            self.assertEqual(self.reset_signal.active,
                                             self.reset_signal)
                        else:
                            self.assertEqual(not self.reset_signal.active,
                                             self.reset_signal)

                        if clock_idx[0] >= n_runs:
                            raise StopSimulation


                    else:
                        # negative edge
                        # Nothing changes
                        if clock_idx[0] < 3 + clock_start:
                            self.assertEqual(self.reset_signal.active,
                                             self.reset_signal)

                        else:
                            self.assertEqual(not self.reset_signal.active,
                                             self.reset_signal)

                clockgen = clock_source(clock, self.clock_period)
                dut = init_reset_source(self.reset_signal, clock)

                return output_check, dut, clockgen

            top_level_block = top()
            top_level_block.run_sim(quiet=1)
            top_level_block.quit_sim()

    def test_negedge_reset_sequence(self):
        '''It should be possible to set a negative clock edge sensitivity.

        That is, the transition happens on negative edges.
        '''
        for clock_start in (0, 1):
            clock = Signal(bool(clock_start))

            dummy_reset = ResetSignal(intbv(0), active=1, isasync=False)
            n_runs = 99
            clock_idx = [0]

            @block
            def top():
                @always(delay(self.clock_period//2))
                def output_check():

                    if clock == False:
                        clock_idx[0] += 1

                        # negative edge
                        # The clock_start offset is because we need to ignore
                        # the starting value.
                        if clock_idx[0] < 3 + 1 - clock_start:
                            self.assertEqual(self.reset_signal.active,
                                             self.reset_signal)
                        else:
                            self.assertEqual(not self.reset_signal.active,
                                             self.reset_signal)

                        if clock_idx[0] >= n_runs:
                            raise StopSimulation


                    else:
                        # positive edge
                        # Nothing changes
                        if clock_idx[0] < 3 + 1 - clock_start:
                            self.assertEqual(self.reset_signal.active,
                                             self.reset_signal)

                        else:
                            self.assertEqual(not self.reset_signal.active,
                                             self.reset_signal)

                dut = init_reset_source(self.reset_signal, clock,
                                        edge_sensitivity='negedge')
                clockgen = clock_source(clock, self.clock_period)

                return output_check, dut, clockgen

            top_level_block = top()
            top_level_block.run_sim(quiet=1)
            top_level_block.quit_sim()


    def test_invalid_sensitivity(self):
        '''An invalid sensitivity should raise a ValueError
        '''
        edge_sensitivity = 'foobar'
        test_signal = self.reset_signal
        self.assertRaisesRegex(ValueError, 'Invalid edge sensitivity',
                               init_reset_source, test_signal, self.clock,
                               edge_sensitivity=edge_sensitivity)

    def test_init_reset_source_convertible_to_VHDL(self):
        '''The init reset source should be convertible to VHDL
        '''

        clock = Signal(bool(0))
        test_signal = Signal(intbv(0, min=-1000, max=1024))

        test_block = init_reset_source(self.reset_signal, clock)
        tmp_dir = tempfile.mkdtemp()

        try:
            test_block.convert(hdl='VHDL', path=tmp_dir)

        finally:
            shutil.rmtree(tmp_dir)

    def test_init_reset_source_convertible_to_Verilog(self):
        '''The init reset source should be convertible to Verilog
        '''

        clock = Signal(bool(0))
        test_signal = Signal(intbv(0, min=-1000, max=1024))

        test_block = init_reset_source(self.reset_signal, clock)
        tmp_dir = tempfile.mkdtemp()

        try:
            test_block.convert(hdl='Verilog', path=tmp_dir)

        finally:
            shutil.rmtree(tmp_dir)



class TestRandomSource(TestCase):
    '''There should be a random source factory for generating instances that
    write random data to a Signal.

    It should take an optional seed argument.
    '''
    def setUp(self):
        self.clock = Signal(bool(1))

        # Keep things simple (for the edge sensitivity test) and enforce an
        # even clock period
        self.clock_period = 10

    def tearDown(self):
        random.seed(None)

    def test_posedge_sensitivity(self):
        '''It should be possible to set a positive clock edge sensitivity.
        '''

        # Check we have what we think we have
        assert self.clock.val == 1 # clock starts at 1
        assert self.clock_period % 2 == 0 # even period

        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = -1000
        max_val = 1024

        seed = randrange(0, 0x5EEDF00D)

        random.seed(seed)

        test_output = [randrange(min_val, max_val) for each in range(100)]
        test_output.reverse()
        test_output.append(0)

        @instance
        def output_check():

            current_output = 0
            # Nothing has happened yet...
            yield(delay(self.clock_period//2))

            while True:
                try:
                    if self.clock.val:
                        # The value should have changed
                        current_output = test_output.pop()
                        self.assertEqual(current_output,
                                         int(test_signal))
                    else:
                        # No change
                        self.assertEqual(current_output,
                                         int(test_signal))

                except IndexError:
                    raise StopSimulation

                # We assume an even clock period
                yield delay(self.clock_period//2)

        edge_sensitivity = 'posedge'
        test_signal = Signal(intbv(0, min=min_val, max=max_val))
        # Careful! We need to create and use the random_source without doing
        # any other random number generation. It should therefore be the last
        # thing created before use.
        dut = random_source(test_signal, self.clock, reset_signal, seed,
                            edge_sensitivity)
        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_negedge_sensitivity(self):
        '''It should be possible to set a negative clock edge sensitivity.
        '''

        # Check we have what we think we have
        assert self.clock.val == 1 # clock starts at 1
        assert self.clock_period % 2 == 0 # even period

        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = -1000
        max_val = 1024

        seed = randrange(0, 0x5EEDF00D)

        random.seed(seed)

        test_output = [randrange(min_val, max_val) for each in range(100)]
        test_output.reverse()

        @instance
        def output_check():

            current_output = 0
            # Nothing has happened yet...
            yield(delay(self.clock_period//2))

            while True:
                try:
                    if self.clock.val:
                        # No change
                        self.assertEqual(current_output,
                                         int(test_signal))
                    else:
                        # Value changed
                        current_output = test_output.pop()
                        self.assertEqual(current_output,
                                         int(test_signal))

                except IndexError:
                    raise StopSimulation

                # We assume an even clock period
                yield delay(self.clock_period//2)


        edge_sensitivity = 'negedge'
        test_signal = Signal(intbv(0, min=min_val, max=max_val))
        # Careful! We need to create and use the random_source without doing
        # any other random number generation. It should therefore be the last
        # thing created before use.
        dut = random_source(test_signal, self.clock, reset_signal,
                            seed, edge_sensitivity)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_output_repeatable(self):
        '''The output should be repeatable despite other generators.
        '''
        test_signal = Signal(intbv(0, min=-1000, max=1024))
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = test_signal.val.min
        max_val = test_signal.val.max

        seed = randrange(0, 0x5EEDF00D)

        random.seed(seed)
        test_output = [randrange(min_val, max_val) for each in range(100)]
        test_output.reverse()
        test_output += [0] # The first value is not defined yet.

        @always_seq(self.clock.posedge, reset_signal)
        def confusifier():
            # Call random a few times to mess with the state
            random.random()
            random.random()
            random.random()

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                self.assertEqual(test_output.pop(), test_signal)
            except IndexError:
                raise StopSimulation

        dut = random_source(test_signal, self.clock, reset_signal, seed)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check, confusifier)
        sim.run(quiet=1)

    def test_invalid_sensitivity(self):
        '''An invalid sensitivity should raise a ValueError.
        '''
        edge_sensitivity = 'foobar'
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        test_signal = Signal(intbv(0, min=-100, max=100))
        self.assertRaisesRegex(ValueError, 'Invalid edge sensitivity',
                               random_source, test_signal, self.clock,
                               reset_signal,
                               edge_sensitivity=edge_sensitivity)

    def test_output_reset_whilst_reset_active(self):
        '''The random source outputs are reset synchronously on active reset.

        That is, the clock cycle _after_ the reset is made active, the
        output values of the Signals should be set to their defaults.
        '''
        enum_names = ('a', 'b', 'c', 'd', 'e')
        enum_vals = enum(*enum_names)

        class Interface(object):

            signals = None

            def __init__(self):
                self.a = Signal(intbv(0, min=-100, max=59))
                self.b = Signal(bool(0))
                self.c = Signal(enum_vals.a)

                self.signals = (self.a, self.b, self.c)

        test_signals = (
            (Signal(intbv(0, min=-1000, max=1024)), 'signal'),
            (Signal(bool(0)), 'signal'),
            (Signal(enum_vals.b), 'signal'),
            (Interface(), 'interface'),)

        @block
        def top(test_signal, test_signal_type):

            if test_signal_type == 'signal':

                @always(clock.posedge)
                def output_check():

                    if last_reset[0] == reset_signal.active:
                        self.assertEqual(test_signal, test_signal._init)

                    else:
                        pass

                    last_reset[0] = copy.copy(reset_signal.val)

            else:
                @always(clock.posedge)
                def output_check():

                    if last_reset[0] == reset_signal.active:
                        for each_signal in test_signal.signals:
                            self.assertEqual(
                                each_signal, each_signal._init)

                    else:
                        pass

                    last_reset[0] = copy.copy(reset_signal.val)


            random.seed()
            dummy_reset_signal = ResetSignal(
                intbv(0), active=1, isasync=False)

            reset_signal = ResetSignal(intbv(0), active=1, isasync=False)

            last_reset = [copy.copy(reset_signal.val)]

            random_reset = random_source(reset_signal, clock,
                                         dummy_reset_signal)
            clockgen = clock_source(clock, self.clock_period)

            dut = random_source(test_signal, clock, reset_signal)

            return clockgen, random_reset, dut, output_check

        for each_test_signal, each_test_signal_type in test_signals:

            clock = Signal(bool(0))

            top_level_block = top(each_test_signal, each_test_signal_type)
            top_level_block.run_sim(
                duration=self.clock_period * 1000, quiet=1)
            top_level_block.quit_sim()


    def test_no_seed(self):
        '''It should be possible to work without a seed.
        '''

        test_signal = Signal(intbv(0, min=-1000, max=1024))
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = test_signal.val.min
        max_val = test_signal.val.max

        test_output = [1] * 10

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                test_output.pop()
            except IndexError:
                raise StopSimulation

        dut = random_source(test_signal, self.clock, reset_signal)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_intbv_signal(self):
        '''It should be possible to generate random intbv signals.

        The min and max values of the signal should be determined by the
        signal that is passed to the source.
        '''

        test_signal = Signal(intbv(0, min=-1000, max=1024))
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = test_signal.val.min
        max_val = test_signal.val.max

        seed = randrange(0, 0x5EEDF00D)

        random.seed(seed)
        test_output = [randrange(min_val, max_val) for each in range(100)]
        test_output.reverse()
        test_output += [0] # The first value is not defined yet.

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                self.assertEqual(test_output.pop(), test_signal)
            except IndexError:
                raise StopSimulation

        dut = random_source(test_signal, self.clock, reset_signal, seed)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_bool_signal(self):
        '''It should be possible to generate random boolean signals.
        '''
        test_signal = Signal(bool(0))
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = 0
        max_val = 2

        seed = randrange(0, 0x5EEDF00D)

        random.seed(seed)
        test_output = [randrange(min_val, max_val) for each in range(100)]
        test_output.reverse()
        test_output += [0] # The first value is not defined yet.

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                self.assertEqual(test_output.pop(), test_signal)
            except IndexError:
                raise StopSimulation

        dut = random_source(test_signal, self.clock, reset_signal, seed)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_bool_as_long_signal(self):
        '''It should be possible to have a bool signal with a long value.

        When a bool signal is update, it is valid to do so with 0 or 1 as well
        as True and False. Signals updated like this should be handled
        properly.
        '''
        test_signal = Signal(bool(0))

        test_signal.next = 1
        test_signal._update()

        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = 0
        max_val = 2

        seed = randrange(0, 0x5EEDF00D)

        random.seed(seed)
        test_output = [randrange(min_val, max_val) for each in range(100)]
        test_output.reverse()
        test_output += [test_signal.val] # The first value is not defined yet.

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                self.assertEqual(test_output.pop(), test_signal)
            except IndexError:
                raise StopSimulation

        dut = random_source(test_signal, self.clock, reset_signal, seed)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_enum_signal(self):
        '''It should be possible to generate random enum signals.
        '''
        enum_names = ('a', 'b', 'c', 'd', 'e')
        enum_vals = enum(*enum_names)

        test_signal = Signal(enum_vals.a)
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)

        seed = randrange(0, 0x5EEDF00D)

        random.seed(seed)
        test_output = [getattr(enum_vals, random.choice(enum_names))
                       for each in range(100)]

        test_output.reverse()
        test_output += [enum_vals.a] # The first value is not defined yet.

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                self.assertEqual(test_output.pop(), test_signal)
            except IndexError:
                raise StopSimulation

        dut = random_source(test_signal, self.clock, reset_signal, seed)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_signal_list(self):
        '''It should be possible to generate random values for a signal list.

        Non signals in the list are simply ignored.
        '''

        N = 20
        test_list = [
            Signal(intbv(0, min=-2**n, max=(2**n)-1)) for n in range(1, N+1)]

        test_list.append('Not a signal')
        test_list[10] = ['also not a signal']

        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)

        # Set the initial seed
        seed = randrange(0, 0x5EEDF00D)
        random.seed(seed)

        # Replicate the expected random state logic
        random.seed(randrange(0, 0x5EEDF00D))
        random_state = random.getstate()

        outputs = []
        stripped_test_list = []
        for each_signal in test_list:

            if not isinstance(each_signal, myhdl._Signal._Signal):
                continue

            stripped_test_list.append(each_signal)

            each_signal_output = [
                randrange(each_signal.min, each_signal.max) for
                each in range(100)]

            each_signal_output.reverse()
            each_signal_output += [0] # The first value is not defined yet.

            outputs.append(each_signal_output)

            # seed a new value
            random.setstate(random_state)
            random.seed(randrange(0, 0x5EEDF00D))
            random_state = random.getstate()

        # None of the data vectors should be the same as any other
        data_hashes = [hash(tuple(each)) for each in outputs]
        # asserts all the hashes are unique
        assert len(set(data_hashes)) == len(outputs)

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                for n in range(len(outputs)):
                    self.assertEqual(outputs[n].pop(), stripped_test_list[n])

            except IndexError:
                raise StopSimulation

        dut = random_source(test_list, self.clock, reset_signal, seed)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_interface_signal(self):
        '''It should be possible to generate random interface signals.
        '''

        enum_names = ('a', 'b', 'c', 'd', 'e')
        enum_vals = enum(*enum_names)

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                # The attributes are sorted, so we need to run through
                # them in the correct order. 'a', 'b', 'c', 'd' is fine.
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(intbv(0, min=min_val, max=max_val))
                self.c = Signal(bool(0))
                self.d = Signal(enum_vals.a)

                # The following should be ignored
                self.next = 'An attribute'
                self.another_attribute = 10

        test_signal = Interface()
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)

        # Set the initial seed
        seed = randrange(0, 0x5EEDF00D)
        random.seed(seed)

        # Replicate the expected random state logic
        random.seed(randrange(0, 0x5EEDF00D))
        random_state = random.getstate()

        # Generate the expected data
        intbv1_output = [randrange(min_val, max_val) for each in range(100)]
        intbv1_output.reverse()
        intbv1_output += [0] # The first value is not defined yet.

        random.setstate(random_state)

        random.seed(randrange(0, 0x5EEDF00D))

        random_state = random.getstate()

        intbv2_output = [randrange(min_val, max_val) for each in range(100)]
        intbv2_output.reverse()
        intbv2_output += [0] # The first value is not defined yet.

        # The two arrays should _not_ be the same
        assert intbv2_output != intbv1_output
        # But be the same length
        assert len(intbv2_output) == len(intbv1_output)

        random.setstate(random_state)
        random.seed(randrange(0, 0x5EEDF00D))

        random_state = random.getstate()

        bool_output = [randrange(0, 2) for each in range(100)]
        bool_output.reverse()
        bool_output += [0] # The first value is not defined yet.

        # change the seed for the next array (it is still deterministic)
        random.setstate(random_state)
        random.seed(randrange(0, 0x5EEDF00D))

        random_state = random.getstate()

        enum_output = [getattr(enum_vals, random.choice(enum_names))
                       for each in range(100)]
        enum_output.reverse()
        enum_output += [enum_vals.a] # The first value is not defined yet.

        @always_seq(self.clock.posedge, reset_signal)
        def output_check():
            try:
                self.assertEqual(intbv1_output.pop(), test_signal.a)
                self.assertEqual(intbv2_output.pop(), test_signal.b)
                self.assertEqual(bool_output.pop(), test_signal.c)
                self.assertEqual(enum_output.pop(), test_signal.d)

            except IndexError:
                raise StopSimulation

        dut = random_source(test_signal, self.clock, reset_signal, seed)

        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_unsupported_signal(self):
        '''Unsupported signals should fail
        '''
        test_signal = Signal('a string')
        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        seed = randrange(0, 0x5EEDF00D)

        self.assertRaisesRegex(ValueError, 'Invalid signal type',
                               random_source, test_signal, self.clock,
                               reset_signal, seed)


class TestRecorderSink(TestCase):
    '''There should be a block that records a signal. It should be
    constructed with a signal and a clock, and it should record every value
    on every sensitive clock edge, plus the start value.
    '''
    def setUp(self):
        self.clock = Signal(bool(1))
        self.reset = ResetSignal(intbv(0), active=1, isasync=False)
        self.clock_period = 10

    def tearDown(self):
        random.seed(None)

    def test_correct_intbv_recording(self):
        '''It should record intbv Signals as a list of intbv values.
        '''

        min_val = -999
        max_val = 999

        test_signal = Signal(intbv(0, min=min_val, max=max_val))
        test_output = []
        recorded_output = []

        @block
        def top():
            @always_seq(self.clock.posedge, reset=self.reset)
            def test_recorder():
                test_output.append(int(test_signal.val))

            source = random_source(test_signal, self.clock, self.reset)
            sink = recorder_sink(
                test_signal, self.clock, recorded_output)
            clockgen = clock_source(self.clock, self.clock_period)

            return clockgen, source, sink, test_recorder

        top_level_block = top()
        top_level_block.run_sim(duration=30*self.clock_period, quiet=1)
        top_level_block.quit_sim()

        self.assertEqual(test_output, recorded_output)

    def test_correct_interface_recording(self):
        '''It should record interfaces as a list of dicts of signal values.
        '''
        min_val = -999
        max_val = 999
        enum_names = ('a', 'b', 'c', 'd', 'e')
        enum_vals = enum(*enum_names)

        class TestInterface(object):

            def __init__(self):
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(bool(0))
                self.c = Signal(enum_vals.a)

                # The following should be ignored
                self.next = 'An attribute'
                self.another_attribute = 10

        test_signal = TestInterface()
        recorded_output = []
        test_output = []

        @block
        def top():
            @always_seq(self.clock.posedge, reset=self.reset)
            def test_recorder():
                test_output.append(
                    {'a': int(test_signal.a.val),
                     'b': bool(test_signal.b.val),
                     'c': test_signal.c.val})

            source = random_source(test_signal, self.clock, self.reset)
            sink = recorder_sink(test_signal, self.clock, recorded_output)
            clockgen = clock_source(self.clock, self.clock_period)

            return clockgen, source, sink, test_recorder

        top_level_block = top()
        top_level_block.run_sim(duration=30*self.clock_period, quiet=1)
        top_level_block.quit_sim()

        self.assertEqual(test_output, recorded_output)

    def test_correct_signal_list_recording(self):
        '''It should record signal lists as a list of lists of signal values.
        '''

        N = 10
        test_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for n in range(1, N+1)]

        test_signal_list[5] = 'not a signal'
        valid_signals = [each for each in test_signal_list if
                         isinstance(each, myhdl._Signal._Signal)]

        test_output = []
        recorded_output = []

        @block
        def top():

            @always_seq(self.clock.posedge, reset=self.reset)
            def test_recorder():
                each_output = [None] * len(valid_signals)

                for n in range(len(valid_signals)):
                    each_output[n] = copy.copy(valid_signals[n].val)

                test_output.append(each_output)

            source = random_source(test_signal_list, self.clock, self.reset)
            sink = recorder_sink(test_signal_list, self.clock, recorded_output)
            clockgen = clock_source(self.clock, self.clock_period)

            return source, sink, clockgen, test_recorder

        top_level_block = top()
        top_level_block.run_sim(duration=30*self.clock_period, quiet=1)
        top_level_block.quit_sim()

        self.assertEqual(test_output, recorded_output)


    def test_correct_bool_recording(self):
        '''It should record bool Signals as a list of bool values.
        '''
        min_val = 0
        max_val = 2

        test_signal = Signal(bool(0))
        test_output = []
        recorded_output = []

        @block
        def top():
            @always_seq(self.clock.posedge, reset=self.reset)
            def test_recorder():
                test_output.append(bool(test_signal.val))

            source = random_source(test_signal, self.clock, self.reset)
            sink = recorder_sink(test_signal, self.clock, recorded_output)
            clockgen = clock_source(self.clock, self.clock_period)

            return source, sink, clockgen, test_recorder

        top_level_block = top()
        top_level_block.run_sim(duration=30*self.clock_period, quiet=1)
        top_level_block.quit_sim()

        self.assertEqual(test_output, recorded_output)

    def test_correct_enum_recording(self):
        '''It should record enum Signals as a list of enum values.
        '''
        enum_names = ('a', 'b', 'c', 'd', 'e')
        enum_vals = enum(*enum_names)

        test_signal = Signal(enum_vals.a)
        test_output = []
        recorded_output = []

        @block
        def top():
            @always_seq(self.clock.posedge, reset=self.reset)
            def test_recorder():
                test_output.append(test_signal.val)

            source = random_source(test_signal, self.clock, self.reset)
            sink = recorder_sink(test_signal, self.clock, recorded_output)
            clockgen = clock_source(self.clock, self.clock_period)

            return source, sink, clockgen, test_recorder

        top_level_block = top()
        top_level_block.run_sim(duration=30*self.clock_period, quiet=1)
        top_level_block.quit_sim()

        self.assertEqual(test_output, recorded_output)

    def test_edge_sensitivity(self):
        '''It should be possible to set a clock edge sensitivity.
        '''

        # Check we have what we think we have
        assert self.clock.val == 1 # clock starts at 1
        assert self.clock_period % 2 == 0 # even period

        min_val = -999
        max_val = 999

        test_signal = Signal(intbv(0, min=min_val, max=max_val))
        neg_edge_output = []
        pos_edge_output = []

        @block
        def top():
            # We require a negative edge source
            source = random_source(test_signal, self.clock, self.reset,
                                   edge_sensitivity='negedge')

            neg_edge_sink = recorder_sink(
                test_signal, self.clock, neg_edge_output,
                edge_sensitivity='negedge')
            pos_edge_sink = recorder_sink(
                test_signal, self.clock, pos_edge_output,
                edge_sensitivity='posedge')
            clockgen = clock_source(self.clock, self.clock_period)

            return clockgen, source, pos_edge_sink, neg_edge_sink

        top_level_block = top()
        top_level_block.run_sim(duration=30*self.clock_period, quiet=1)
        top_level_block.quit_sim()

        assert len(neg_edge_output) == len(pos_edge_output)
        # Now we need to offset the results of the positive edge
        # with respect to the negative edge. This is dictated by the starting
        # conditions. This can be confirmed with a timing diagram.
        self.assertEqual(neg_edge_output[1:], pos_edge_output[:-1])

    def test_invalid_edge_arg_raises(self):
        '''An invalid edge sensitivity should raise a ValueError.
        '''
        min_val = -999
        max_val = 999

        test_signal = Signal(intbv(0, min=min_val, max=max_val))

        source = random_source(test_signal, self.clock, self.reset)

        self.assertRaisesRegex(ValueError, 'Invalid edge sensitivity',
                               recorder_sink, test_signal, self.clock, [],
                               edge_sensitivity='INVALID')

class TestLutSignalDriver(TestCase):
    '''In order that a signal can be replayed, specifically in the case
    of the convertible device under test, there should be a block that
    reads from a lookup table and writes the result to the passed in signal.
    '''

    def setUp(self):
        self.clock = Signal(bool(1))

        # Keep things simple (for the edge sensitivity test) and enforce an
        # even clock period
        self.clock_period = 10

    def test_basic_signal_driver(self):
        '''It should be possible to drive a signal from a simple list.
        '''

        test_signal = Signal(intbv(0, min=-1000, max=1024))
        min_val = test_signal.val.min
        max_val = test_signal.val.max

        test_output = [randrange(min_val, max_val) for each in range(100)]
        lut = copy.copy(test_output)

        # ignore last couple of values to make sure there are few enough
        # values to work (otherwise, the lut overflows before StopSimulation
        # is raised)
        test_output = test_output[:-2]
        test_output.reverse()

        @always(self.clock.posedge)
        def output_check():
            try:
                self.assertEqual(test_output.pop(), test_signal)
            except IndexError:
                raise StopSimulation

        dut = lut_signal_driver(test_signal, lut, self.clock)
        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_signal_repeats(self):
        '''The look-up table should wrap around when it runs out of values.
        '''
        test_signal = Signal(intbv(0, min=-1000, max=1024))
        min_val = test_signal.val.min
        max_val = test_signal.val.max

        test_output = [randrange(min_val, max_val) for each in range(100)]
        lut = copy.copy(test_output)
        test_output.reverse()
        # Repeat it a few times
        test_output = test_output + test_output + test_output

        @always(self.clock.posedge)
        def output_check():
            try:
                self.assertEqual(test_output.pop(), test_signal)
            except IndexError:
                raise StopSimulation

        dut = lut_signal_driver(test_signal, lut, self.clock)
        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_zero_length_luts_should_raise(self):
        '''With a zero length lut, a ValueError should be raised.

        Because the list is necessarily longer than 0, a ValueError
        should be raised if it is not.
        '''
        test_signal = Signal(intbv(0, min=-1000, max=1024))

        lut = ()
        self.assertRaisesRegex(
            ValueError, 'Invalid zero length lut',
            lut_signal_driver, test_signal, lut, self.clock)

    def test_invalid_edge_arg_raises(self):
        '''An invalid edge sensitivity should raise a ValueError.
        '''
        min_val = -999
        max_val = 999

        lut = (1, 2, 3)

        test_signal = Signal(intbv(0, min=min_val, max=max_val))

        # should work.
        source = lut_signal_driver(test_signal, lut, self.clock)

        self.assertRaisesRegex(ValueError, 'Invalid edge sensitivity',
                               lut_signal_driver, test_signal, lut,
                               self.clock, edge_sensitivity='INVALID')

    def test_lut_iterable(self):
        '''The lut object should be iterable in order that it is convertible.
        '''

        min_val = -999
        max_val = 999

        invalid_lut = 10

        test_signal = Signal(intbv(0, min=min_val, max=max_val))

        self.assertRaisesRegex(TypeError, 'object is not iterable',
                               lut_signal_driver, test_signal, invalid_lut,
                               self.clock)

    def test_posedge_sensitivity(self):
        '''It should be possible to set a positive clock edge sensitivity.
        '''

        # Check we have what we think we have
        assert self.clock.val == 1 # clock starts at 1
        assert self.clock_period % 2 == 0 # even period

        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = -1000
        max_val = 1024

        test_output = [randrange(min_val, max_val) for each in range(100)]
        lut = copy.copy(test_output)

        # ignore last couple of values to make sure there are few enough
        # values to work (otherwise, the lut overflows before StopSimulation
        # is raised)
        test_output = test_output[:-2]
        test_output.reverse()

        @instance
        def output_check():

            next_transition = intbv(bool(0))
            # Pop off the first value
            current_output = test_output.pop()

            # Then wait for the next clock edge
            yield(delay(self.clock_period//2))

            while True:
                try:
                    if next_transition: # a positive edge
                        self.assertEqual(current_output,
                                         int(test_signal))

                        # The value should now change for the next cycle
                        current_output = test_output.pop()

                    else: # A negative edge
                        self.assertEqual(current_output,
                                         int(test_signal))
                        # No change

                except IndexError:
                    raise StopSimulation

                next_transition[:] = not next_transition

                # We assume an even clock period
                yield delay(self.clock_period//2)

        edge_sensitivity = 'posedge'
        test_signal = Signal(intbv(0, min=min_val, max=max_val))

        dut = lut_signal_driver(test_signal, lut, self.clock)
        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_negedge_sensitivity(self):
        '''It should be possible to set a negative clock edge sensitivity.
        '''
        # Check we have what we think we have
        assert self.clock.val == 1 # clock starts at 1
        assert self.clock_period % 2 == 0 # even period

        reset_signal = ResetSignal(intbv(0), active=1, isasync=False)
        min_val = -1000
        max_val = 1024

        test_output = [randrange(min_val, max_val) for each in range(100)]
        lut = copy.copy(test_output)

        # ignore last couple of values to make sure there are few enough
        # values to work (otherwise, the lut overflows before StopSimulation
        # is raised)
        test_output = test_output[:-2]
        test_output.reverse()

        @instance
        def output_check():

            next_transition = intbv(bool(0))
            # Pop off the first value
            current_output = test_output.pop()

            # Then wait for the next clock edge
            yield(delay(self.clock_period//2))

            while True:
                try:
                    if next_transition: # a positive edge
                        self.assertEqual(current_output,
                                         int(test_signal))
                        # No change
                    else: # A negative edge
                        self.assertEqual(current_output,
                                         int(test_signal))

                        # The value should now change for the next cycle
                        current_output = test_output.pop()

                except IndexError:
                    raise StopSimulation

                next_transition[:] = not next_transition

                # We assume an even clock period
                yield delay(self.clock_period//2)

        edge_sensitivity = 'negedge'
        test_signal = Signal(intbv(0, min=min_val, max=max_val))

        dut = lut_signal_driver(test_signal, lut, self.clock,
                                edge_sensitivity=edge_sensitivity)
        clockgen = clock_source(self.clock, self.clock_period)

        sim = Simulation(clockgen, dut, output_check)
        sim.run(quiet=1)

    def test_lut_signal_driver_convertible_to_VHDL(self):
        '''The lut signal driver should be convertible to VHDL
        '''
        tmp_dir = tempfile.mkdtemp()

        try:
            test_signal = Signal(intbv(0, min=-1000, max=1024))

            min_val = test_signal.val.min
            max_val = test_signal.val.max
            clock = self.clock

            lut = [randrange(min_val, max_val) for each in range(100)]

            # Make sure our lut length is not a power of 2
            assert (log(len(lut), 2) % 2 != 0)

            test_block = lut_signal_driver(test_signal, lut, clock)
            test_block.convert(hdl='VHDL', path=tmp_dir)

        finally:
            shutil.rmtree(tmp_dir)

    def test_lut_signal_driver_convertible_to_Verilog(self):
        '''The lut signal driver should be convertible to Verilog
        '''
        tmp_dir = tempfile.mkdtemp()

        try:
            test_signal = Signal(intbv(0, min=-1000, max=1024))

            min_val = test_signal.val.min
            max_val = test_signal.val.max
            clock = self.clock

            lut = [randrange(min_val, max_val) for each in range(100)]

            # Make sure our lut length is not a power of 2
            assert (log(len(lut), 2) % 2 != 0)

            test_block = lut_signal_driver(test_signal, lut, clock)
            test_block.convert(hdl='Verilog', path=tmp_dir)

        finally:
            shutil.rmtree(tmp_dir)

    def test_lut_signal_driver_VHDL_with_name_annotation(self):
        '''If signal_name is a string, then output VHDL should contain an
        annotation comment that looks like:
            ``-- <name_annotation> internal_converted_name signal_name``
        in which ``internal_converted_name`` is whatever name MyHDL assigns
        the signal in the converted file and ``signal_name`` is whatever is
        passed to this function.
        '''
        tmp_dir = tempfile.mkdtemp()

        try:
            test_signal = Signal(intbv(0, min=-1000, max=1024))

            min_val = test_signal.val.min
            max_val = test_signal.val.max
            clock = self.clock

            lut = [randrange(min_val, max_val) for each in range(100)]

            # Make sure our lut length is not a power of 2
            assert (log(len(lut), 2) % 2 != 0)

            test_block = lut_signal_driver(
                test_signal, lut, clock, signal_name='my_signal_name')
            test_block.convert(hdl='VHDL', path=tmp_dir)

            with open(os.path.join(tmp_dir, 'lut_signal_driver.vhd')) as f:
                vhdl_code = f.read()

            self.assertTrue(
                '\n-- <name_annotation> signal my_signal_name\n' in vhdl_code)

        finally:
            shutil.rmtree(tmp_dir)

    def test_lut_signal_driver_verilog_with_name_annotation(self):
        '''If signal_name is a string, then output verilog should contain an
        annotation comment that looks like:
            ``// <name_annotation> internal_converted_name signal_name``
        in which ``internal_converted_name`` is whatever name MyHDL assigns
        the signal in the converted file and ``signal_name`` is whatever is
        passed to this function.
        '''
        tmp_dir = tempfile.mkdtemp()

        try:
            test_signal = Signal(intbv(0, min=-1000, max=1024))

            min_val = test_signal.val.min
            max_val = test_signal.val.max
            clock = self.clock

            lut = [randrange(min_val, max_val) for each in range(100)]

            # Make sure our lut length is not a power of 2
            assert (log(len(lut), 2) % 2 != 0)

            test_block = lut_signal_driver(
                test_signal, lut, clock, signal_name='my_signal_name')
            test_block.convert(hdl='Verilog', path=tmp_dir)

            with open(os.path.join(tmp_dir, 'lut_signal_driver.v')) as f:
                verilog_code = f.read()

            self.assertTrue(
                '\n// <name_annotation> signal my_signal_name\n' in
                verilog_code)

        finally:
            shutil.rmtree(tmp_dir)


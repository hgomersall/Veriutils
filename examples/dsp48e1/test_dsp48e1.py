
import unittest
from tests.base_hdl_test import HDLTestCase, get_signed_intbv_rand_signal
from myhdl import (intbv, enum, Signal, ResetSignal, instance,
                   delay, always, always_seq, Simulation, StopSimulation)

# FIXME the vivado_executable check should be part of the API
from tests.test_cosimulation import vivado_executable

from random import randrange
import random

from collections import deque

from .dsp48e1 import (
    DSP48E1, OPMODE_MULTIPLY, OPMODE_MULTIPLY_ADD, OPMODE_MULTIPLY_ACCUMULATE)

from veriutils import myhdl_cosimulation, vivado_cosimulation, copy_signal

PERIOD = 10

class DSP48E1TestCase(HDLTestCase):
    
    def setUp(self):
        
        self.len_A = 25
        self.len_B = 18
        self.len_C = 48
        self.len_P = 48

        self.clock = Signal(bool(1))
        self.clock_enable = Signal(bool(1))        
        self.reset = ResetSignal(bool(0), active=1, async=False)

        self.A, self.a_min, self.a_max = (
            get_signed_intbv_rand_signal(self.len_A))
        self.B, self.b_min, self.b_max = (
            get_signed_intbv_rand_signal(self.len_B))

        initial_C, _c_min, _c_max = (
            get_signed_intbv_rand_signal(self.len_C))

        # Reduce the range of C, but not enough to reduce its bitwidth
        self.c_min = int(_c_min * 0.6)
        self.c_max = int(_c_max * 0.6)
        self.C = Signal(intbv(0, min=self.c_min, max=self.c_max))
        self.C.val[:] = int(initial_C.val * 0.6)

        self.P, self.p_min, self.p_max = (
            get_signed_intbv_rand_signal(self.len_P))

        # Tweak the initialisations
        self.P.val[:] = 0

        self.operations = {
            'multiply': OPMODE_MULTIPLY,
            'multiply_add': OPMODE_MULTIPLY_ADD,
            'multiply_accumulate': OPMODE_MULTIPLY_ACCUMULATE}

        self.opmode = Signal(intbv(0, min=0, max=len(self.operations)))

        self.default_args = {
            'A': self.A, 'B': self.B, 'C': self.C, 'P': self.P,
            'opmode': self.opmode, 'reset': self.reset, 'clock': self.clock, 
            'clock_enable': self.clock_enable}

        self.default_arg_types = {
            'A': 'random', 'B': 'random', 'C': 'random', 'P': 'output', 
            'opmode': 'custom', 'reset': 'init_reset', 'clock': 'clock', 
            'clock_enable': 'custom'}

        # Should work, no probs
        test = DSP48E1(**self.default_args)

        self.pipeline_registers = 3

class TestDSP48E1Interface(DSP48E1TestCase):
    '''The DSP48E1 should have a well defined interface, with careful
    checking of the parameters.
    '''

    def test_A_port_checked(self):
        '''The A port should be an 25 bit signed intbv.

        Anything else should raise a ValueError.
        '''
        self.do_port_check_intbv_test(DSP48E1, 'A', 25, signed=True)

    def test_B_port_checked(self):
        '''The B port should be an 18 bit signed intbv.

        Anything else should raise a ValueError.
        '''
        self.do_port_check_intbv_test(DSP48E1, 'B', 18, signed=True)

    def test_C_port_checked(self):
        '''The C port should be an 48 bit signed intbv.

        Anything else should raise a ValueError.
        '''
        self.do_port_check_intbv_test(DSP48E1, 'C', 48, signed=True)

    def test_P_port_checked(self):
        '''The P port should be an 48 bit signed intbv.

        Anything else should raise a ValueError.
        '''
        self.do_port_check_intbv_test(DSP48E1, 'P', 48, signed=True)

    def test_opmode_port_checked(self):
        '''The opmode port should be an unsigned intbv.

        The min and max values of the opmode port should be determined by 
        the number of implemented opmodes.
        '''
        opmode_range = (self.opmode.min, self.opmode.max)
        self.do_port_check_intbv_test(DSP48E1, 'opmode', 
                                      val_range=opmode_range)

    def test_clock_port_checked(self):
        '''The clock port should be a boolean signal.

        Anything else should raise a ValueError.
        '''
        self.do_port_check_bool_test(DSP48E1, 'clock')

    def test_clock_enable_port_checked(self):
        '''The clock enable port should be a boolean signal.

        Anything else should raise a ValueError.
        '''
        self.do_port_check_bool_test(DSP48E1, 'clock_enable')

    def test_reset_port_checked(self):
        '''The reset port should be a boolean signal.

        Anything else should raise a ValueError.
        '''
        self.do_port_check_reset_test(DSP48E1, 'reset', active=1, async=False)

class TestDSP48E1Simulation(DSP48E1TestCase):
    '''The DSP48E1 slice should implement various bits of functionality that
    should be verifiable through simulation.
    '''

    def cosimulate(self, sim_cycles, dut_factory, ref_factory, args, 
                   arg_types, **kwargs):

        return myhdl_cosimulation(sim_cycles, dut_factory, ref_factory, 
                                  args, arg_types, **kwargs)

    def test_basic_multiply(self):
        '''The basic multiply with default Z should be the product of A and B.
        '''

        self.opmode.val[:] = self.operations['multiply']

        def ref(**kwargs):

            P = kwargs['P']
            A = kwargs['A']
            B = kwargs['B']
            clock = kwargs['clock']
            reset = kwargs['reset']

            @always_seq(clock.posedge, reset=reset)
            def test_basic_multiply():
                P.next = A * B

            return test_basic_multiply

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        cycles = 20
        dut_outputs, ref_outputs = self.cosimulate(
            cycles, DSP48E1, ref, args, arg_types)

        # There are pipeline_registers cycles latency on the output. 
        # The reference above has only 1 cycle latency, so we need to offset 
        # the results by pipeline_registers - 1 cycles.
        self.assertEqual(dut_outputs['P'][self.pipeline_registers - 1:], 
                         ref_outputs['P'][:-(self.pipeline_registers - 1)])

    def test_multiply_add(self):
        '''There should be a multiply-add mode, giving C + A * B
        '''

        self.opmode.val[:] = self.operations['multiply_add']

        def ref(**kwargs):

            P = kwargs['P']
            A = kwargs['A']
            B = kwargs['B']
            C = kwargs['C']            
            clock = kwargs['clock']
            reset = kwargs['reset']

            @always_seq(clock.posedge, reset=reset)
            def test_basic_multiply():
                P.next = A * B + C

            return test_basic_multiply

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        cycles = 20
        dut_outputs, ref_outputs = self.cosimulate(
            cycles, DSP48E1, ref, args, arg_types)

        # There are pipeline_registers cycles latency on the output. 
        # The reference above has only 1 cycle latency, so we need to offset 
        # the results by pipeline_registers - 1 cycles.
        self.assertEqual(dut_outputs['P'][self.pipeline_registers - 1:], 
                         ref_outputs['P'][:-(self.pipeline_registers - 1)])


    def test_multiply_accumulate(self):
        '''There should be a multiply-accumulate mode, giving P + A * B.

        P is defined to be the output, which is not pipelined. That is,
        the output should always be incremented by A*B as long as the 
        multiply-accumulate is ongoing.
        '''
        self.opmode.val[:] = self.operations['multiply_accumulate']        

        def ref(**kwargs):

            P = kwargs['P']
            A = kwargs['A']
            B = kwargs['B']
            clock = kwargs['clock']
            reset = kwargs['reset']

            @always_seq(clock.posedge, reset=reset)
            def test_basic_multiply():
                P.next = A * B + P

            return test_basic_multiply

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        # Don't run too many cycles or you'll get an overflow!
        cycles = 20
        dut_outputs, ref_outputs = self.cosimulate(
            cycles, DSP48E1, ref, args, arg_types)

        # There are pipeline_registers cycles latency on the output. 
        # The reference above has only 1 cycle latency, so we need to offset 
        # the results by pipeline_registers - 1 cycles.
        self.assertEqual(dut_outputs['P'][self.pipeline_registers - 1:], 
                         ref_outputs['P'][:-(self.pipeline_registers - 1)])

    def test_changing_modes(self):
        '''It should be possible to change modes dynamically.

        When the mode is changed, the mode should propagate through the
        pipeline with the data. That is, the mode should be attached to
        the input it accompanies.
        '''
        
        # Create the (unique) reverse lookup
        opmode_reverse_lookup = {
            self.operations[key]: key for key in self.operations}

        def custom_reset_source(driven_reset, clock):
            dummy_reset = ResetSignal(bool(0), active=1, async=False)

            @instance
            def custom_reset():
                driven_reset.next = 1
                yield(clock.posedge)
                driven_reset.next = 1
                yield(clock.posedge)
                while True:
                    next_reset = randrange(0, 100)
                    # Be false 80% of the time.
                    if next_reset > 95:
                        driven_reset.next = 1
                    else:
                        driven_reset.next = 0
                        
                    yield(clock.posedge)

            return custom_reset

        def ref(**kwargs):

            P = kwargs['P']
            A = kwargs['A']
            B = kwargs['B']
            C = kwargs['C']            
            opmode = kwargs['opmode']
            clock = kwargs['clock']
            reset = kwargs['reset']

            # Each pipeline should be pipeline_registers - 1 long since
            # there is one implicit register.
            A_pipeline = deque(
                [copy_signal(A) for _ in range(self.pipeline_registers - 1)])
            B_pipeline = deque(
                [copy_signal(B) for _ in range(self.pipeline_registers - 1)])
            C_pipeline = deque(
                [copy_signal(C) for _ in range(self.pipeline_registers - 1)])
            opmode_pipeline = deque(
                [copy_signal(opmode) for _ in 
                 range(self.pipeline_registers - 1)])

            @always(clock.posedge)
            def test_arbitrary_pipeline():
                
                if reset == reset.active:
                    for _A, _B, _C, _opmode in zip(
                        A_pipeline, B_pipeline, C_pipeline, opmode_pipeline):

                        _A.next = _A._init
                        _B.next = _B._init
                        _C.next = _C._init
                        _opmode.next = _opmode._init
                        P.next = P._init
                else:
                    A_pipeline.append(copy_signal(A))
                    B_pipeline.append(copy_signal(B))
                    C_pipeline.append(copy_signal(C))
                    opmode_pipeline.append(copy_signal(opmode))

                    A_out = A_pipeline.popleft()
                    B_out = B_pipeline.popleft()
                    C_out = C_pipeline.popleft()
                    opmode_out = opmode_pipeline.popleft()
                    
                    if (opmode_reverse_lookup[int(opmode_out.val)] == 
                        'multiply'):
                        P.next = A_out * B_out

                    elif (opmode_reverse_lookup[int(opmode_out.val)] == 
                          'multiply_add'):
                        P.next = A_out * B_out + C_out

                    if (opmode_reverse_lookup[int(opmode_out.val)] == 
                        'multiply_accumulate'):
                        P.next = A_out * B_out + P

            return test_arbitrary_pipeline

        args = self.default_args.copy()
        arg_types = self.default_arg_types.copy()

        arg_types.update({'opmode': 'random', 'reset': 'custom_reset'})

        custom_sources = [custom_reset_source(args['reset'], args['clock'])]

        cycles = 100
        dut_outputs, ref_outputs = self.cosimulate(
            cycles, DSP48E1, ref, args, arg_types, 
            custom_sources=custom_sources)
        
        self.assertEqual(dut_outputs['reset'], ref_outputs['reset'])
        self.assertEqual(dut_outputs['P'], ref_outputs['P'])

@unittest.skipIf(vivado_executable is None, 'Vivado executable not in path')
class TestDSP48E1VivadoSimulation(TestDSP48E1Simulation):
    '''The tests of TestDSP48E1Simulation should run under the Vivado 
    simulator.
    '''

    def cosimulate(self, sim_cycles, dut_factory, ref_factory, args, 
                   arg_types, **kwargs):

        return vivado_cosimulation(sim_cycles, dut_factory, ref_factory, 
                                   args, arg_types, **kwargs)

from veriutils import SynchronousTest

from .test_cosimulation import CosimulationTestMixin

from .base_hdl_test import TestCase
from myhdl import *

import shutil
import tempfile
import os

def _conversion_test(
    target_language, cycles, dut_factory, ref_factory, args,
    arg_types, custom_sources=None, **kwargs):
    '''Constructs a SimulationTest object and converts the convertible_top
    method to the target language.

    To do this it needs to first run a simulation instance which is the basis
    of the data generated, and then converts the result to
    '''

    sim_object = SynchronousTest(dut_factory, ref_factory, args, arg_types,
                                 custom_sources=custom_sources)

    # We need to create the test data
    myhdl_outputs = sim_object.cosimulate(cycles)

    tmp_dir = tempfile.mkdtemp()

    try:
        project_name = 'tmp_project'
        project_path = os.path.join(tmp_dir, project_name)

        convertible_top = sim_object.dut_convertible_top(tmp_dir)

        convertible_top.convert(hdl=target_language, path=tmp_dir)

    finally:
        shutil.rmtree(tmp_dir)


    return myhdl_outputs

class ConvertibleCodeTestsMixin(CosimulationTestMixin):
    '''There should be a well defined subset of cases that are convertible
    with no warnings.
    '''

    check_mocks = False

    def test_interface_case(self):
        '''It should be possible to work with interfaces.

        It is not allowed to have enums in the interface.
        '''

        # This replaces the test_interface_case, removin
        args = self.default_args.copy()

        min_val = -1000
        max_val = 1000

        class Interface(object):
            def __init__(self):
                # The attributes are sorted, so we need to run through
                # them in the correct order. 'a', 'b', 'c', 'd' is fine.
                self.a = Signal(intbv(0, min=min_val, max=max_val))
                self.b = Signal(intbv(0, min=min_val, max=max_val))
                self.c = Signal(intbv(0, min=0, max=max_val))
                self.d = Signal(bool(0))

        @block
        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                test_output.a.next = test_input.a
                test_output.b.next = test_input.b
                test_output.c.next = test_input.c
                test_output.d.next = test_input.d

            return identity

        args['test_input'] = Interface()
        args['test_output'] = Interface()

        sim_cycles = 31

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory,
            args, self.default_arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal], ref_results[signal])

    def test_signal_list_arg(self):
        '''It should be possible to work with lists of signals.

        Only lists of signals of the same size are supported.
        '''

        args = self.default_args.copy()

        # We need to overwrite the parent implemented version in order
        # to create a test that will convert properly.
        N = 20
        n = 8
        input_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for _ in range(1, N+1)]

        output_signal_list = [
            Signal(intbv(0, min=-2**n, max=2**n-1)) for _ in range(1, N+1)]

        @block
        def identity_factory(test_input, test_output, reset, clock):
            @always_seq(clock.posedge, reset=reset)
            def identity():
                for i in range(N):
                    test_output[i].next = test_input[i]

            return identity

        args['test_input'] = input_signal_list
        args['test_output'] = output_signal_list

        sim_cycles = 31

        dut_results, ref_results = self.construct_and_simulate(
            sim_cycles, identity_factory, identity_factory,
            args, self.default_arg_types)

        for signal in dut_results:
            self.assertEqual(dut_results[signal][1:], ref_results[signal][1:])

class ConvertibleCodeTests(ConvertibleCodeTestsMixin):

    def hdl_conversion_wrapper(self, sim_cycles, dut_factory, ref_factory,
                               args, arg_types, **kwargs):

        raise NotImplementedError

    def construct_and_simulate(
        self, sim_cycles, dut_factory, ref_factory, args, arg_types,
        **kwargs):
        '''This doesn't actually simulate, but runs the conversion code.
        '''
        return self.hdl_conversion_wrapper(
            sim_cycles, dut_factory, ref_factory, args, arg_types,
            **kwargs)

class ConvertibleCodeVHDLTests(ConvertibleCodeTests, TestCase):

    def hdl_conversion_wrapper(self, sim_cycles, dut_factory, ref_factory,
                               args, arg_types, **kwargs):

        return _conversion_test(
            'VHDL', sim_cycles, dut_factory, ref_factory, args, arg_types,
            **kwargs)


class ConvertibleCodeVerilogTests(ConvertibleCodeTests, TestCase):

    def hdl_conversion_wrapper(self, sim_cycles, dut_factory, ref_factory,
                               args, arg_types, **kwargs):

        return _conversion_test(
            'Verilog', sim_cycles, dut_factory, ref_factory, args, arg_types,
            **kwargs)

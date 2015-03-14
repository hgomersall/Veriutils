
'''A module implementing the Xilinx DSP48E1 DSP slice.
'''

from myhdl import always_seq, always_comb, Signal, intbv, enum, ConcatSignal
from veriutils import (
    check_intbv_signal, check_bool_signal, check_reset_signal)
from math import log, floor

# Opmode enumeration
N_OPMODES = 3
OPMODE_MULTIPLY = 0
OPMODE_MULTIPLY_ADD = 1
OPMODE_MULTIPLY_ACCUMULATE = 2

# Set the values for the internal multiplexers
X_ZEROS, X_M = 0, 1
Y_ZEROS, Y_M = 0, 1
Z_ZEROS, Z_P, Z_C = 0, 2, 3


def DSP48E1(A, B, C, P, opmode, clock_enable, reset, clock):

    # Check the inputs
    check_intbv_signal(A, 'A', 25, signed=True)
    check_intbv_signal(B, 'B', 18, signed=True)
    check_intbv_signal(C, 'C', 48, signed=True)
    check_intbv_signal(P, 'P', 48, signed=True)
    check_intbv_signal(opmode, 'opmode', val_range=(0, N_OPMODES))    
    check_bool_signal(clock_enable, 'clock_enable')    
    check_bool_signal(clock, 'clock')
    check_reset_signal(reset, 'reset', active=1, async=False)

    ALUMODE = None

    out_len = 48
    max_out = 2**(out_len - 1) - 1 # one bit for the sign
    min_out = -max_out

    A_register = Signal(intbv(val=0, min=A.min, max=A.max))
    B_register = Signal(intbv(val=0, min=B.min, max=B.max))

    M_register = Signal(intbv(val=0, min=min_out, max=max_out))
    C_register1 = Signal(intbv(val=0, min=min_out, max=max_out))
    C_register2 = Signal(intbv(val=0, min=min_out, max=max_out))
    
    P_register = Signal(intbv(val=0, min=min_out, max=max_out))

    # Set up the opmode registers.
    # Currently two input side registers.
    opmode_register1 = Signal(intbv(val=0, min=0, max=N_OPMODES))
    opmode_register2 = Signal(intbv(val=0, min=0, max=N_OPMODES))

    opmode_X = Signal(intbv(0)[2:])
    opmode_Y = Signal(intbv(0)[2:])
    opmode_Z = Signal(intbv(0)[3:])

    X_output = intbv(val=X_ZEROS, min=min_out, max=max_out)
    Y_output = intbv(val=Y_ZEROS, min=min_out, max=max_out)
    Z_output = intbv(val=Z_ZEROS, min=min_out, max=max_out)

    @always_seq(clock.posedge, reset=reset)
    def opmode_pipeline():
        opmode_register1.next = opmode
        opmode_register2.next = opmode_register1

    @always_comb
    def set_opmode_X():
        if opmode_register2 == OPMODE_MULTIPLY:
            opmode_X.next = X_M
        elif opmode_register2 == OPMODE_MULTIPLY_ADD:
            opmode_X.next = X_M
        elif opmode_register2 == OPMODE_MULTIPLY_ACCUMULATE:
            opmode_X.next = X_M
        else:
            if __debug__:
                raise ValueError('Unsupported Y opmode: %d', opmode_Y)
            pass

    @always_comb
    def set_opmode_Y():
        if opmode_register2 == OPMODE_MULTIPLY:
            opmode_Y.next = Y_M
        elif opmode_register2 == OPMODE_MULTIPLY_ADD:
            opmode_Y.next = Y_M
        elif opmode_register2 == OPMODE_MULTIPLY_ACCUMULATE:
            opmode_Y.next = Y_M
        else:
            if __debug__:
                raise ValueError('Unsupported Y opmode: %d', opmode_Y)
            pass

    @always_comb
    def set_opmode_Z():
        if opmode_register2 == OPMODE_MULTIPLY:
            opmode_Z.next = Z_ZEROS
        elif opmode_register2 == OPMODE_MULTIPLY_ADD:
            opmode_Z.next = Z_C
        elif opmode_register2 == OPMODE_MULTIPLY_ACCUMULATE:
            opmode_Z.next = Z_P
        else:
            if __debug__:
                raise ValueError('Unsupported Y opmode: %d', opmode_Y)
            pass

    @always_seq(clock.posedge, reset=reset)
    def _dsp48e1_block():

        # The partial products are combined in this implementation.
        # No problems with this as all we are doing is multiply/add or 
        # multiply/accumulate.
        if opmode_X == X_M:
            X_output[:] = M_register
        else:
            if __debug__:
                raise ValueError('Unsupported X opmode: %d', opmode_X)
            pass

        if opmode_Y == Y_M:
            Y_output[:] = 0 # The full product is handled by X
        else:
            if __debug__:
                raise ValueError('Unsupported Y opmode: %d', opmode_Y)
            pass

        if opmode_Z == Z_ZEROS:
            Z_output[:] = 0
        elif opmode_Z == Z_C:
            Z_output[:] = C_register2
        elif opmode_Z == Z_P:
            Z_output[:] = P_register
        else:
            if __debug__:
                raise ValueError('Unsupported Z opmode: %d', opmode_Z)
            pass

        M_register.next = A_register * B_register

        A_register.next = A
        B_register.next = B

        C_register1.next = C
        C_register2.next = C_register1

        P_register.next = X_output + Y_output + Z_output

        P.next = P_register

    return (_dsp48e1_block, opmode_pipeline, 
            set_opmode_X, set_opmode_Y, set_opmode_Z)


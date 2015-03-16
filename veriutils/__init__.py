from distutils import spawn as _spawn
VIVADO_EXECUTABLE = _spawn.find_executable('vivado')

from .cosimulation import *
from .hdl_blocks import *
from .utils import *


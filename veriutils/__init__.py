from distutils import spawn as _spawn
VIVADO_EXECUTABLE = _spawn.find_executable('vivado')
#VIVADO_EXECUTABLE = None

from .cosimulation import *
from .hdl_blocks import *
from .utils import *
from .axi import *


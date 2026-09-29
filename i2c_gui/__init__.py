#############################################################################
# zlib License
#
# (C) 2023 Cristóvão Beirão da Cruz e Silva <cbeiraod@cern.ch>
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.
#############################################################################

from __future__ import annotations

__version__ = '0.0.2'
__platform__ = None  # For storing the result of automativ platform detection
__swap_endian__ = True  # Whether to swap register address bytes to correct for mixed up endianness
__no_connect__ = False  # Set to true if the connection to I2C is to be emulated
__no_connect_type__ = "check" # Set the type of no connect to implement. For most uses "check" is enough, but for readback tests the "echo" option is preferred

from .etroc1_gui import ETROC1_GUI
from .etroc2_gui import ETROC2_GUI
from .ad5593r_gui import AD5593R_GUI
from .multi_gui import Multi_GUI
from .script_helper import ScriptHelper
from .connection_controller import Connection_Controller

from .functions import validate_8bit_register
from .functions import validate_variable_bit_register
from .functions import validate_i2c_address
from .functions import validate_pixel_index
from .functions import hex_0fill
from .functions import addLoggingLevel

# Add custom log levels to logging
addLoggingLevel('TRACE', 8)
addLoggingLevel('DETAILED_TRACE', 5)
#addLoggingLevel('HIGH_TEST', 100)

def set_platform(value):
    global __platform__
    __platform__ = value

def get_swap_endian():
    return __swap_endian__

def toggle_swap_endian():
    global __swap_endian__
    __swap_endian__ = not __swap_endian__

def set_swap_endian():
    global __swap_endian__
    __swap_endian__ = True

def unset_swap_endian():
    global __swap_endian__
    __swap_endian__ = False

__all__ = [
    "ETROC1_GUI",
    "ETROC2_GUI",
    "AD5593R_GUI",
    "Multi_GUI",
    "ScriptHelper",
    "Connection_Controller",
    "validate_8bit_register",
    "validate_variable_bit_register",
    "validate_i2c_address",
    "validate_pixel_index",
    "hex_0fill",
    "set_platform",
    "get_swap_endian",
    "toggle_swap_endian",
    "set_swap_endian",
    "unset_swap_endian",
]

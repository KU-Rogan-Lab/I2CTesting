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

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..connection_controller import Connection_Controller

from .base_chip import Base_Chip
from ..gui_helper import GUI_Helper
from .address_space_controller import Address_Space_Controller
from ..i2c_messages import I2CMessages
from math import ceil

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging

ad5593r_version = "0.0.1"

register_model = {
    "AD5593R": {  # Address Space (i.e. separate I2C memory spaces)
        "Memory Size": 256,
        "Register Bits": 8,
        "Register Length": 16,
        "Endianness": "big",
        "Read Type": 'Repeated Start',
        "Register Blocks": {
            "Config_WR": {
                "Base Address": 0x00,
                "Registers": {
                    "NOP": {
                        "offset": 0x00,
                        "default": 0x0000,
                    },
                    "ADC_SEQ": {
                        "offset": 0x02,
                        "default": 0x0000,
                    },
                    "GEN_CTRL_REG": {
                        "offset": 0x03,
                        "default": 0x0000,
                    },
                    "ADC_CONFIG": {
                        "offset": 0x04,
                        "default": 0x0000,
                    },
                    "DAC_CONFIG": {
                        "offset": 0x05,
                        "default": 0x0000,
                    },
                    "PULLDWN_CONFIG": {
                        "offset": 0x06,
                        "default": 0x00FF,
                    },
                    "LDAC_MODE": {
                        "offset": 0x07,
                        "default": 0x0000,
                    },
                    "GPIO_CONFIG": {
                        "offset": 0x08,
                        "default": 0x0000,
                    },
                    "GPIO_OUTPUT": {
                        "offset": 0x09,
                        "default": 0x0000,
                    },
                    "GPIO_INPUT": {
                        "offset": 0x0a,
                        "default": 0x0000,
                    },
                    "PD_REF_CTRL": {
                        "offset": 0x0b,
                        "default": 0x0000,
                    },
                    "GPIO_OPENDRAIN_CONFIG": {
                        "offset": 0x0c,
                        "default": 0x0000,
                    },
                    "IO_TS_CONFIG": {
                        "offset": 0x0d,
                        "default": 0x0000,
                    },
                    "SW_RESET": {
                        "offset": 0x0f,
                        "default": 0x0000,
                    },
                },
            },
            "Config_RD": {
                "Base Address": 0x70,
                "Write Base Address": 0x00,
                "Registers": {
                    "NOP": {
                        "offset": 0x00,
                        "default": 0x0000,
                    },
                    "ADC_SEQ": {
                        "offset": 0x02,
                        "default": 0x0000,
                    },
                    "GEN_CTRL_REG": {
                        "offset": 0x03,
                        "default": 0x0000,
                    },
                    "ADC_CONFIG": {
                        "offset": 0x04,
                        "default": 0x0000,
                    },
                    "DAC_CONFIG": {
                        "offset": 0x05,
                        "default": 0x0000,
                    },
                    "PULLDWN_CONFIG": {
                        "offset": 0x06,
                        "default": 0x00FF,
                    },
                    "LDAC_MODE": {
                        "offset": 0x07,
                        "default": 0x0000,
                    },
                    "GPIO_CONFIG": {
                        "offset": 0x08,
                        "default": 0x0000,
                    },
                    "GPIO_OUTPUT": {
                        "offset": 0x09,
                        "default": 0x0000,
                    },
                    "GPIO_INPUT": {
                        "offset": 0x0a,
                        "default": 0x0000,
                    },
                    "PD_REF_CTRL": {
                        "offset": 0x0b,
                        "default": 0x0000,
                    },
                    "GPIO_OPENDRAIN_CONFIG": {
                        "offset": 0x0c,
                        "default": 0x0000,
                    },
                    "IO_TS_CONFIG": {
                        "offset": 0x0d,
                        "default": 0x0000,
                    },
                    "SW_RESET": {
                        "offset": 0x0f,
                        "default": 0x0000,
                    },
                },
            },
            "ADC_RD": {
                "Base Address": 0x40,
                "Registers": {
                    "Readings": {
                        "offset": 0x00,
                        "default": 0x0000,
                    },
                },
            },
            "DAC_WR": {
                "Base Address": 0x10,
                "Registers": {
                    "DAC0": {
                        "offset": 0x00,
                        "default": 0x0000,
                    },
                    "DAC1": {
                        "offset": 0x01,
                        "default": 0x0000,
                    },
                    "DAC2": {
                        "offset": 0x02,
                        "default": 0x0000,
                    },
                    "DAC3": {
                        "offset": 0x03,
                        "default": 0x0000,
                    },
                    "DAC4": {
                        "offset": 0x04,
                        "default": 0x0000,
                    },
                    "DAC5": {
                        "offset": 0x05,
                        "default": 0x0000,
                    },
                    "DAC6": {
                        "offset": 0x06,
                        "default": 0x0000,
                    },
                    "DAC7": {
                        "offset": 0x07,
                        "default": 0x0000,
                    },
                },
            },
            "DAC_RD": {
                "Base Address": 0x50,
                "Write Base Address": 0x10,
                "Registers": {
                    "DAC0": {
                        "offset": 0x00,
                        "default": 0x0000,
                    },
                    "DAC1": {
                        "offset": 0x01,
                        "default": 0x0000,
                    },
                    "DAC2": {
                        "offset": 0x02,
                        "default": 0x0000,
                    },
                    "DAC3": {
                        "offset": 0x03,
                        "default": 0x0000,
                    },
                    "DAC4": {
                        "offset": 0x04,
                        "default": 0x0000,
                    },
                    "DAC5": {
                        "offset": 0x05,
                        "default": 0x0000,
                    },
                    "DAC6": {
                        "offset": 0x06,
                        "default": 0x0000,
                    },
                    "DAC7": {
                        "offset": 0x07,
                        "default": 0x0000,
                    },
                },
            },
            "GPIO_RD": {
                "Base Address": 0x60,
                "Registers": {
                    "GPIO": {
                        "offset": 0x00,
                        "default": 0x0000,
                    },
                },
            },
        },
    },
}

register_decoding = {
}

class AD5593R_Chip(Base_Chip):

    _indexer_info = {
        "vars": [],
        "min": [],
        "max": [],
    }

    def __init__(self, parent: GUI_Helper, i2c_controller: Connection_Controller):
        super().__init__(
            parent=parent,
            chip_name="AD5593R",
            version=ad5593r_version,
            i2c_controller=i2c_controller,
            register_model=register_model,
            register_decoding=register_decoding,
            indexer_info = self._indexer_info
        )

        self._i2c_address = None

        self.clear_tab("Empty")
        self.register_tab(
            "Config",
            {
                "canvas": True,
                "builder": self.config_interface_builder,
            }
        )
        self.register_tab(
            "DAC",
            {
                "canvas": True,
                "builder": self.dac_interface_builder,
            }
        )

        # Set indexer vars callback, so we can update the displayed block array
        self._callback_indexer_var = {}
        for var in self._indexer_vars:
            indexer_var = self._indexer_vars[var]['variable']
            self._callback_indexer_var[var] = indexer_var.trace_add('write', self._update_indexed_vars)

    def _update_indexed_vars(self, var=None, index=None, mode=None):
        pass

    def update_whether_modified(self):
        state = self._address_space["AD5593R"].is_modified

        self._parent._local_status_update(state)

    def config_i2c_address(self, address):
        self._i2c_address = address

        from .address_space_controller import Address_Space_Controller
        if "AD5593R" in self._address_space:
            address_space: Address_Space_Controller = self._address_space["AD5593R"]
            address_space.update_i2c_address(address)
        self.update_whether_modified()

    def config_interface_builder(self, frame: ttk.Frame):
        frame.columnconfigure(100, weight=1)
        columns = 4

        self._AD5593R_config_frame = self.build_block_interface(
            element=frame,
            title="Configuration Registers",
            internal_title="ConfigurationRegisters",
            button_title="Config",
            address_space="AD5593R",
            block="Config_RD",
            col=100,
            row=100,
            register_columns=columns,
        )

    def dac_interface_builder(self, frame: ttk.Frame):
        frame.columnconfigure(100, weight=1)
        columns = 4

        self._AD5593R_DAC_frame = self.build_block_interface(
            element=frame,
            title="DAC",
            internal_title="DAC",
            button_title="DAC",
            address_space="AD5593R",
            block="DAC_RD",
            col=100,
            row=100,
            register_columns=columns,
        )

    def read_adc_results(self, adc_sequence: int, num_measurements: int):
        if num_measurements == 0:
            return []

        adc_sequence_handle = self.get_display_var("AD5593R", "Config_RD", "ADC_SEQ")

        # Select channels to be converted by ADC (Step 2 from the "ADC Operation" in the manual)
        adc_sequence_handle.set(adc_sequence)
        self.write_register("AD5593R", "Config_RD", "ADC_SEQ")

        # Select the ADC for reading (Step 3 from the "ADC Operation" in the manual)
        self._i2c_controller.direct_i2c([I2CMessages.START, I2CMessages.WRITE2, self._i2c_address << 1, 0b01000000, I2CMessages.STOP])

        # Actually read the ADC conversion data (Step 4 from the "ADC Operation" in the manual)
        data = []
        num_repeats = ceil(num_measurements/8)  #  each measurement is 2 bytes and we want to read a max of 16 bytes at a time
        for i in range(num_repeats):
            num_bytes = 16
            if i == num_repeats - 1:
                num_bytes = num_measurements*2 - i*16

            commands = [I2CMessages.START, I2CMessages.WRITE1, (self._i2c_address << 1) + 1]

            commands += [getattr(I2CMessages, f'READ{num_bytes - 1}')]

            commands += [I2CMessages.NACK, I2CMessages.READ1, I2CMessages.STOP]

            data += self._i2c_controller.direct_i2c(commands)

        # Stop ADC conversion (explained at the end of the "ADC Operation" in the manual)
        adc_sequence_handle.set(0x0000)
        self.write_register("AD5593R", "Config_RD", "ADC_SEQ")

        retVal = [None for _ in range(num_measurements)]
        for i in range(num_measurements):
            retVal[i] = ((data[i * 2] & 0xff) << 8) | (data[i * 2 + 1] & 0xff)

        return retVal
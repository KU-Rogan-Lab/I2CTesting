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

from .i2c_connection_helper import I2C_Connection_Helper
from .i2c_messages import I2CMessages
from .base_gui import Base_GUI

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging
import time

from usb_iss import UsbIss, defs

class USB_ISS_Helper(I2C_Connection_Helper):
    def __init__(self, parent: Base_GUI, max_seq_byte: int = 8, swap_endian: bool = True):
        super().__init__(parent, max_seq_byte, swap_endian)

        self._iss = UsbIss()
        #self._iss = UsbIss(verbose=True)

        self._port_var = tk.StringVar()
        self._port_var.set("/dev/ttyACM0")

        self._clk_var = tk.IntVar(self._frame)
        self._clk_var.set(100)

    @property
    def port(self):
        return self._port_var.get()

    @port.setter
    def port(self, value):
        self._port_var.set(value)

    @property
    def clk(self):
        return self._clk_var.get()

    @clk.setter
    def clk(self, value):
        self._clk_var.set(value)

    def _check_i2c_device(self, address: int):
        return self._iss.i2c.test(address)

    def _write_i2c_device_memory(self, address: int, memory_address: int, data: list[int], register_bits: int = 16, write_type: str = 'Normal'):
        if write_type == 'Normal':
            if register_bits == 16:
                self._iss.i2c.write_ad2(address, memory_address, data)
            elif register_bits == 8:
                self._iss.i2c.write_ad1(address, memory_address, data)
            else:
                self.send_message("Unknown bit size trying to be sent", "Error")
        #elif write_type == "Repeated Start":
        #    pass
        else:
            raise RuntimeError("Unknown write type chosen for the USB ISS")

    def _read_i2c_device_memory(self, address: int, memory_address: int, byte_count: int, register_bits: int = 16, read_type: str = 'Normal') -> list[int]:
        if read_type == 'Normal':
            if register_bits == 16:
                return self._iss.i2c.read_ad2(address, memory_address, byte_count)
            if register_bits == 8:
                return self._iss.i2c.read_ad1(address, memory_address, byte_count)
            else:
                self.send_message("Unknown bit size trying to be sent", "Error")
                return []
        elif read_type == "Repeated Start":
            direct_msg = [defs.I2CDirect.START]

            device_address_byte = address << 1
            if register_bits == 8:
                direct_msg += [
                    defs.I2CDirect.WRITE2,
                    device_address_byte,
                    memory_address & 0xff,
                ]
            elif register_bits == 16:
                direct_msg += [
                    defs.I2CDirect.WRITE3,
                    device_address_byte,
                    (memory_address >> 8) & 0xff,
                    memory_address & 0xff,
                ]
            else:
                self.send_message("Unknown bit size trying to be sent", "Error")
                return []

            direct_msg += [
                defs.I2CDirect.RESTART,
                defs.I2CDirect.WRITE1,
                device_address_byte | 0x01,
            ]

            #byte_count += 1  # Why do I need to do this... maybe something is misconfigured
            if byte_count <= 16:
                if byte_count > 1:
                    direct_msg += [
                        getattr(defs.I2CDirect, f"READ{byte_count-1}"),
                    ]
            else:
                raise RuntimeError("USB ISS does not support a block read of more than 16 bytes")

            direct_msg += [
                defs.I2CDirect.NACK,
                defs.I2CDirect.READ1,
                defs.I2CDirect.STOP,
            ]

            retVal = self._iss.i2c.direct(direct_msg)

            if len(retVal) != byte_count:
                raise RuntimeError(f"Did not receive the expected number of bytes")
            else:
                return retVal
        else:
            raise RuntimeError("Unknown read type chosen for the USB ISS")

    def _direct_i2c(self, commands: list[int]) -> list[int]:
        direct_msg = []

        #print("Got commands:")
        #print(commands)

        idx = 0
        while True:
            if idx >= len(commands):
                break

            command = commands[idx]
            if command not in I2CMessages:
                raise RuntimeError("Unknown I2C command")

            direct_msg += [command.value]
            if command == I2CMessages.WRITE1:
                direct_msg += [commands[idx+1]]
                idx += 2
            elif command == I2CMessages.WRITE2:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                idx += 3
            elif command == I2CMessages.WRITE3:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                idx += 4
            elif command == I2CMessages.WRITE4:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                idx += 5
            elif command == I2CMessages.WRITE5:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                idx += 6
            elif command == I2CMessages.WRITE6:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                idx += 7
            elif command == I2CMessages.WRITE7:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                idx += 8
            elif command == I2CMessages.WRITE8:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                idx += 9
            elif command == I2CMessages.WRITE9:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                idx += 10
            elif command == I2CMessages.WRITE10:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                direct_msg += [commands[idx+10]]
                idx += 11
            elif command == I2CMessages.WRITE11:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                direct_msg += [commands[idx+10]]
                direct_msg += [commands[idx+11]]
                idx += 12
            elif command == I2CMessages.WRITE12:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                direct_msg += [commands[idx+10]]
                direct_msg += [commands[idx+11]]
                direct_msg += [commands[idx+12]]
                idx += 13
            elif command == I2CMessages.WRITE13:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                direct_msg += [commands[idx+10]]
                direct_msg += [commands[idx+11]]
                direct_msg += [commands[idx+12]]
                direct_msg += [commands[idx+13]]
                idx += 14
            elif command == I2CMessages.WRITE14:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                direct_msg += [commands[idx+10]]
                direct_msg += [commands[idx+11]]
                direct_msg += [commands[idx+12]]
                direct_msg += [commands[idx+13]]
                direct_msg += [commands[idx+14]]
                idx += 15
            elif command == I2CMessages.WRITE15:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                direct_msg += [commands[idx+10]]
                direct_msg += [commands[idx+11]]
                direct_msg += [commands[idx+12]]
                direct_msg += [commands[idx+13]]
                direct_msg += [commands[idx+14]]
                direct_msg += [commands[idx+15]]
                idx += 16
            elif command == I2CMessages.WRITE16:
                direct_msg += [commands[idx+1]]
                direct_msg += [commands[idx+2]]
                direct_msg += [commands[idx+3]]
                direct_msg += [commands[idx+4]]
                direct_msg += [commands[idx+5]]
                direct_msg += [commands[idx+6]]
                direct_msg += [commands[idx+7]]
                direct_msg += [commands[idx+8]]
                direct_msg += [commands[idx+9]]
                direct_msg += [commands[idx+10]]
                direct_msg += [commands[idx+11]]
                direct_msg += [commands[idx+12]]
                direct_msg += [commands[idx+13]]
                direct_msg += [commands[idx+14]]
                direct_msg += [commands[idx+15]]
                direct_msg += [commands[idx+16]]
                idx += 17
            else:
                idx += 1

        #print("Translated commands:")
        #print(direct_msg)

        return self._iss.i2c.direct(direct_msg)

    def display_in_frame(self, frame: ttk.Frame):
        if hasattr(self, '_frame') and self._frame is not None:
            tmp = self._frame.children.copy()
            for widget in tmp:
                tmp[widget].destroy()

        self._frame = frame
        self._port_label = ttk.Label(self._frame, text="Port:")
        self._port_label.grid(column=0, row=0, sticky=(tk.W, tk.E))

        self._port_entry = ttk.Entry(self._frame, textvariable=self._port_var, width=10)
        self._port_entry.grid(column=1, row=0, sticky=(tk.W, tk.E), padx=(0,30))

        self._frame.columnconfigure(2, weight=1)

        self._clk_values = [ # These are the frequencies supported by the USB-ISS module (in kHz), two of them are supported in both hardware and software
            20,   # Supported in software bit bashed
            50,   # Supported in software bit bashed
            100,  # Supported in software bit bashed and hardware
            400,  # Supported in software bit bashed and hardware
            1000  # Supported in hardware
        ]

        self._clk_label = ttk.Label(self._frame, text="Clock Frequency:")
        self._clk_label.grid(column=3, row=0, sticky=(tk.W, tk.E))

        self._clk_option = ttk.OptionMenu(self._frame, self._clk_var, self._clk_values[2], *self._clk_values)
        self._clk_option.grid(column=4, row=0, sticky=(tk.W, tk.E))

        self._clk_units_label = ttk.Label(self._frame, text="kHz")
        self._clk_units_label.grid(column=5, row=0, sticky=(tk.W, tk.E), padx=(0,30))

        self._frame.columnconfigure(6, weight=1)

    def validate_connection_params(self):
        if self.port == "":
            self.send_message("Please enter a valid port")
            return False

        return True

    def connect(self, no_connect: bool = False):
        # Give preference to hardware I2C for clk which support both hardware and bit bashed
        use_hardware = True
        if self._clk_var.get() < 100:
            use_hardware = False

        self._no_connect = no_connect
        if not no_connect:  # For emulated connection
            try:
                self._iss.open(self.port)
                self._iss.setup_i2c(clock_khz=self.clk, use_i2c_hardware=use_hardware)
            except:
                self.send_message("Unable to connect to I2C bus on port {} using I2C at {} kHz".format(self.port, self.clk))
                return False

        if hasattr(self, "_port_entry"):
            self._port_entry.config(state="disabled")
        if hasattr(self, "_clk_option"):
            self._clk_option.config(state="disabled")
        self.send_message("Connected to I2C bus with a bitrate of {} kHz through port {}".format(self.clk, self.port))
        #print(self._iss.read_fw_version())
        return True

    def disconnect(self):
        self._iss.close()

        if hasattr(self, "_port_entry"):
            self._port_entry.config(state="normal")
        if hasattr(self, "_clk_option"):
            self._clk_option.config(state="normal")
        self.send_message("Disconnected from I2C bus with a bitrate of {} kHz through port {}".format(self.clk, self.port))
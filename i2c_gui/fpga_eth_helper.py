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
from .base_gui import Base_GUI

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging
import time

import socket
import struct
from .functions import validate_hostname

class FPGA_ETH_Helper(I2C_Connection_Helper):
    def __init__(self, parent: Base_GUI, max_seq_byte: int = 8, swap_endian: bool = False):
        super().__init__(parent, max_seq_byte, swap_endian)

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._hostname_var = tk.StringVar(value='192.168.2.3') # FPGA IP address

        self._port_var = tk.IntVar(value=1024) # port number

    @property
    def hostname(self):
        return self._hostname_var.get()

    @hostname.setter
    def hostname(self, value: str):
        self._hostname_var.set(value)

    @property
    def port(self):
        return self._port_var.get()

    @port.setter
    def port(self, value: int):
        self._port_var.set(value)

    def _check_i2c_device(self, address: int):
        mode = 0
        wr = 1
        val = mode << 24 | address << 17 | wr << 16  # write device addr and read one byte, ignore read address

        self._write_fpga_config_register(4, 0xffff & val)
        self._write_fpga_config_register(5, 0xffff & (val>>16))
        time.sleep(0.01)
        self._pulse_fpga_register(0x0001)  # Send a pulse to IIC module
        time.sleep(0.01)

        ack_error = self._read_fpga_status_register(0) & 0x0100  # the 9th bit of status register is ACK_ERROR
        return (ack_error == 0)  # if no error, return true

    def _write_i2c_device_memory(self, address: int, memory_address: int, data: list[int], register_bits: int = 16, write_type: str = 'Normal'):
        for index in range(len(data)):
            self._write_i2c_device_register(
                i2c_address = address,
                memory_address = memory_address + index,
                data = data[index],
                addressing_mode = register_bits,
                write_type = write_type,
            )
        return

    def _write_i2c_device_register(self, i2c_address: int, memory_address: int, data: int, addressing_mode: int = 16, write_type: str = 'Normal'):
        if write_type != 'Normal':
            raise RuntimeError("The FPGA ETH interface does not support write types which are not of the normal type")
        wr = 0  # Operation is a write
        if addressing_mode == 8 :
            mode = 1  # Send an I2C message where 2 bytes are acted on
            val = mode << 24 | (0x7f & i2c_address) << 17 | wr << 16 | (0xff & memory_address) << 8 | (0xff & data)
            self._write_fpga_config_register(4, 0xffff & val)
            self._write_fpga_config_register(5, 0xffff & (val>>16))
            time.sleep(0.01)
            self._pulse_fpga_register(0x0001)
            time.sleep(0.01)
        elif addressing_mode == 16:
            memory_address_lsb = 0x00ff & memory_address
            memory_address_msb = 0xff00 & memory_address
            mode = 2  # Send an I2C message where 3 bytes are acted on
            val = mode << 24 | (0x7f & i2c_address) << 17 | wr << 16 | (0xff & memory_address_lsb) << 8 | (0xff & data)
            self._write_fpga_config_register(4, 0xffff & val)
            self._write_fpga_config_register(5, 0xffff & (val>>16))
            self._write_fpga_config_register(6, 0xffff & (0xff &(memory_address_msb >> 8)))
            time.sleep(0.01)
            self._pulse_fpga_register(0x0001)
            time.sleep(0.01)
        else:
            self.send_message("Unknown adressing mode for writing an i2c device register", "Error")
        return

    def _read_i2c_device_memory(self, address: int, memory_address: int, byte_count: int, register_bits: int = 16, read_type: str = 'Normal') -> list[int]:
        retVal = []
        for index in range(byte_count):
            retVal += [self._read_i2c_device_register(
                i2c_address = address,
                memory_address = memory_address + index,
                addressing_mode = register_bits,
                read_type = read_type,
            )]
        return retVal

    def _read_i2c_device_register(self, i2c_address: int, memory_address: int, addressing_mode: int = 16, read_type: str = 'Normal') -> int:
        if read_type != 'Normal':
            raise RuntimeError("The FPGA ETH interface does not support read types which are not of the normal type")
        if addressing_mode == 8 :
            mode = 0  # Send an I2C message where 1 byte is acted on
            wr = 0  # Operation is a write
            val = mode << 24 | (0x7f & i2c_address) << 17 | wr << 16 | (0xff & memory_address) << 8 | 0x00
            #write 8 bit address first
            self._write_fpga_config_register(4, 0xffff & val)
            self._write_fpga_config_register(5, 0xffff & (val>>16))
            time.sleep(0.01)
            self._pulse_fpga_register(0x0001)
            time.sleep(0.01)

            #read 8 bit data
            wr = 1  # Operation is a read
            val = mode << 24 | (0x7f & i2c_address) << 17 | wr << 16 | (0xff & memory_address) << 8 | 0x00
            self._write_fpga_config_register(4, 0xffff & val)
            self._write_fpga_config_register(5, 0xffff & (val>>16))
            time.sleep(0.01)
            self._pulse_fpga_register(0x0001)
            time.sleep(0.01)
        elif addressing_mode == 16:
            memory_address_lsb = 0x00ff & memory_address
            memory_address_msb = 0xff00 & memory_address
            #write 16 bit address first
            mode = 1  # Send an I2C message where 2 bytes are acted on
            wr = 0  # Operation is a write
            val = mode << 24 | (0x7f & i2c_address) << 17 | wr << 16 | (0xff & memory_address_lsb) << 8 | (0xff & (memory_address_msb >> 8))
            self._write_fpga_config_register(4, 0xffff & val)
            self._write_fpga_config_register(5, 0xffff & (val>>16))
            time.sleep(0.01)
            self._pulse_fpga_register(0x0001)
            time.sleep(0.01)

            #read 8 bit data
            mode = 0  # Send an I2C message where 1 byte is acted on
            wr = 1  # Operation is a read
            val = mode << 24 | (0x7f & i2c_address) << 17 | 1 << 16 | (0xff & memory_address_lsb) << 8 | 0x00
            self._write_fpga_config_register(4, 0xffff & val)
            self._write_fpga_config_register(5, 0xffff & (val>>16))
            time.sleep(0.01)
            self._pulse_fpga_register(0x0001)
            time.sleep(0.01)
        else:
            self.send_message("Unknown adressing mode for reading an i2c device register", "Error")
        return self._read_fpga_status_register(0) & 0x00ff

    def _read_fpga_config_register(self, register_address: int):
        package_data = 0x80200000 + (register_address << 16)
        self._socket.sendall(struct.pack('I', package_data)[::-1])
        return struct.unpack('I', self._socket.recv(4)[::-1])[0]

    def _write_fpga_config_register(self, register_address: int, data: int):
        package_data = 0x00200000 + (register_address << 16) + data
        self._socket.sendall(struct.pack('I',package_data)[::-1])

    def _read_fpga_status_register(self, register_address: int):
        package_data = 0x80000000 + (register_address << 16)
        self._socket.sendall(struct.pack('I',package_data)[::-1])
        return struct.unpack('I', self._socket.recv(4)[::-1])[0]

    def _pulse_fpga_register(self, register_address: int):
        package_data = 0x000b0000 + register_address
        self._socket.sendall(struct.pack('I',package_data)[::-1])

    def _read_fpga_data_fifo(self, count: int):
        package_data = 0x00190000 + (count -1)
        self._socket.sendall(struct.pack('I', package_data)[::-1])
        fifo_data = []
        for i in range(count):
            fifo_data += [struct.unpack('I', self._socket.recv(4)[::-1])[0]]
        return fifo_data

    def display_in_frame(self, frame: ttk.Frame):
        if hasattr(self, '_frame') and self._frame is not None:
            tmp = self._frame.children.copy()
            for widget in tmp:
                tmp[widget].destroy()

        self._frame = frame

        self._hostname_label = ttk.Label(self._frame, text="Hostname:")
        self._hostname_label.grid(column=0, row=0, sticky=(tk.W, tk.E))

        self._hostname_entry = ttk.Entry(self._frame, textvariable=self._hostname_var, width=10)
        self._hostname_entry.grid(column=1, row=0, sticky=(tk.W, tk.E), padx=(0,30))

        self._frame.columnconfigure(2, weight=1)

        self._port_label = ttk.Label(self._frame, text="Port:")
        self._port_label.grid(column=3, row=0, sticky=(tk.W, tk.E))

        self._port_entry = ttk.Entry(self._frame, textvariable=self._port_var, width=7)
        self._port_entry.grid(column=4, row=0, sticky=(tk.W, tk.E), padx=(0,30))

        self._frame.columnconfigure(5, weight=1)

    def validate_connection_params(self):
        if not validate_hostname(self.hostname):
            self.send_message("Please enter a valid hostname", "Error")
            return False

        if self.port == "":
            self.send_message("Please enter a valid port", "Error")
            return False

        try:
            socket.gethostbyname(self.hostname)
        except socket.gaierror:
            self.send_message("Unable to find the host: {}".format(self.hostname))
            return False

        return True

    def connect(self, no_connect: bool = False):
        self._no_connect = no_connect
        if not no_connect:  # For emulated connection
            try:
                self._socket.connect((self.hostname, self.port))
            except socket.error:
                self.send_message("Unable to connect to {} on port {}".format(self.hostname, self.port))
                return False

        if hasattr(self, "_hostname_entry"):
            self._hostname_entry.config(state="disabled")
        if hasattr(self, "_port_entry"):
            self._port_entry.config(state="disabled")
        self.send_message("Connected to {} on port {}".format(self.hostname, self.port))
        return True

    def disconnect(self):
        if not self._no_connect:
            self._socket.close()
            del self._socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if hasattr(self, "_hostname_entry"):
            self._hostname_entry.config(state="normal")
        if hasattr(self, "_port_entry"):
            self._port_entry.config(state="normal")
        self.send_message("Disconnected from {} on port {}".format(self.hostname, self.port))
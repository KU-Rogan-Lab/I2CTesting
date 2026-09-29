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

from .gui_helper import GUI_Helper
from .base_gui import Base_GUI
from .functions import hex_0fill
from .functions import validate_bit_length
from .functions import validate_variable_bit_register

from math import ceil

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging
import time
import re

from .usb_iss_helper import USB_ISS_Helper
from .fpga_eth_helper import FPGA_ETH_Helper

class Connection_Controller(GUI_Helper):
    _orange_col = '#f0c010'
    _green_col = '#08ef10'
    _black_col = '#000000'

    _connection_types = [
        "USB-ISS",
        "FPGA-Eth",
    ]

    _parent: Base_GUI
    def __init__(
        self,
        parent: Base_GUI,
        usb_iss_max_seq_byte = 8,
        override_logger = None,
        successive_i2c_delay_us : int = 10000,
    ):
        if override_logger is None:
            super().__init__(parent, None, parent._logger)
        else:
            super().__init__(parent, None, override_logger)
        self._is_connected = False

        self._time_last_i2c_command = time.time_ns()

        self._usb_iss_max_seq_byte = usb_iss_max_seq_byte

        #  The i2c connection is instantiated as a helper class, the helper class will manage
        # the connection itself, allowing to replace the class with others in case other I2C
        # interfaces need to be supported
        self._i2c_connection = USB_ISS_Helper(self, usb_iss_max_seq_byte)

        self._i2c_connection_type_var = tk.StringVar(value=self._connection_types[0])
        self._i2c_connection_type_var.trace_add("write", self._update_connection_type) # This should probably be moved lower

        self._registered_connection_callbacks = []

        self._successive_i2c_delay_us = successive_i2c_delay_us

        from . import __no_connect__
        if __no_connect__:
            self._previous_write_value = None

        self._do_logging_i2c = False
        self._i2c_logging_window_status_var = tk.StringVar()
        self._i2c_logging_window_status_var.set("Logging Disabled")

        self._i2c_window_address_var = tk.StringVar()
        self._i2c_window_register_var = tk.StringVar()
        self._i2c_window_register_value_var = tk.StringVar()
        self._i2c_window_block_size_var = tk.StringVar()

        self._i2c_window_register_length_var = tk.StringVar(value="8")
        self._i2c_window_register_length_var.trace_add("write", self._changed_register_length)

        self._i2c_window_register_address_length_var = tk.StringVar(value="16")
        self._i2c_window_register_address_length_var.trace_add("write", self._changed_register_address_length)

        self._enable_readback_var = tk.BooleanVar(value=True)
        self._enable_readback_var.trace_add("write", self._toggle_enable_readback)

    @property
    def is_connected(self):
        return self._is_connected

    @property
    def connection_type(self):
        return self._i2c_connection_type_var.get()

    @connection_type.setter
    def connection_type(self, val: str):
        if not self.is_connected:
            self._i2c_connection_type_var.set(val)

    @property
    def handle(self):
        return self._i2c_connection

    def _set_connected(self, value):
        if value != self._is_connected:
            self._is_connected = value
            for function in self._registered_connection_callbacks:
                function(value)

    def _toggle_enable_readback(self, var=None, index=None, mode=None):
        value = self._enable_readback_var.get()
        self._parent.set_enable_readback(value)

    def _changed_register_length(self, var=None, index=None, mode=None):
        string = self._i2c_window_register_length_var.get()

        if validate_bit_length(string):
            if hasattr(self, "_i2c_window_register_value_entry"):
                if not hasattr(self, f'_register_{string}_validate_cmd'):
                    setattr(self, f'_register_{string}_validate_cmd', (self._frame.register(lambda string_v : validate_variable_bit_register(string_v, int(string, 10))), '%P'))

                func = getattr(self, f'_register_{string}_validate_cmd')
                self._i2c_window_register_value_entry.config(validate='key', validatecommand=func, invalidcommand=self._invalid_register_value_cmd)

    def _changed_register_address_length(self, var=None, index=None, mode=None):
        string = self._i2c_window_register_address_length_var.get()

        if validate_bit_length(string):
            if hasattr(self, "_i2c_window_register_value_entry"):
                if not hasattr(self, f'_register_{string}_validate_cmd'):
                    setattr(self, f'_register_{string}_validate_cmd', (self._frame.register(lambda string_v : validate_variable_bit_register(string_v, int(string, 10))), '%P'))

                func = getattr(self, f'_register_{string}_validate_cmd')
                self._i2c_window_register_entry.config(validate='key', validatecommand=func, invalidcommand=self._invalid_register_address_cmd)

    def _update_connection_type(self, var=None, index=None, mode=None):
        connection_type = self._i2c_connection_type_var.get()
        update_display = False
        if connection_type == "USB-ISS":
            self._i2c_connection = USB_ISS_Helper(self, self._usb_iss_max_seq_byte)
            update_display = True
        elif connection_type == "FPGA-Eth":
            self._i2c_connection = FPGA_ETH_Helper(self)
            self.send_message("The FPGA-Eth connection is not fully implement yet - this will not work", "Warning")
            update_display = True
        else:
            self.send_message("Unknown I2C Connection Type: {}".format(connection_type), "Error")
            self._i2c_connection_type_var.set(self._connection_types[0])
            self._update_connection_type()

        if update_display and hasattr(self, "_i2c_connection_frame") and self._i2c_connection_frame is not None:
            self._i2c_connection_frame.destroy()

            self._i2c_connection_frame = ttk.Frame(self._frame)
            self._i2c_connection_frame.grid(column=1, row=0, sticky=(tk.W, tk.E))

            self._i2c_connection.display_in_frame(self._i2c_connection_frame)

    def check_i2c_device(self, address: str):
        this_time = time.time_ns()
        if this_time - self._time_last_i2c_command < self._successive_i2c_delay_us * 1000:
            time.sleep(self._successive_i2c_delay_us/10E6)
            this_time = time.time_ns()
        self._time_last_i2c_command = this_time

        from . import __no_connect__
        if __no_connect__:
            return True

        return self._i2c_connection.check_i2c_device(int(address, 0))

    def register_connection_callback(self, function):
        if function not in self._registered_connection_callbacks:
            self._registered_connection_callbacks += [function]

    def deregister_connection_callback(self, function):
        if function in self._registered_connection_callbacks:
            self._registered_connection_callbacks.remove(function)

    def prepare_display(self, element: tk.Tk, col: int, row: int):
        self._frame = ttk.LabelFrame(element, text="I2C Connection Configuration")
        self._frame.grid(column=col, row=row, sticky=(tk.N, tk.W, tk.E, tk.S))

        self._connection_type_option = ttk.OptionMenu(self._frame, self._i2c_connection_type_var, self._connection_types[0], *self._connection_types)
        self._connection_type_option.grid(column=0, row=0, sticky=(tk.W, tk.E), padx=(5, 20))

        self._i2c_connection_frame = ttk.Frame(self._frame)
        self._i2c_connection_frame.grid(column=1, row=0, sticky=(tk.W, tk.E))
        self._frame.columnconfigure(1, weight=1)

        self._i2c_connection.display_in_frame(self._i2c_connection_frame)

        self._connect_button = ttk.Button(self._frame, text="Connect", command=self.connect)
        self._connect_button.grid(column=2, row=0, sticky=(tk.W, tk.E), padx=(0,5))

        self._enable_readback_checkbutton = ttk.Checkbutton(self._frame, variable=self._enable_readback_var, state='disabled', text='Enable Readback')
        self._enable_readback_checkbutton.grid(column=3, row=0, sticky=(tk.W, tk.E), padx=(0,5))

    def connect(self):
        if self.is_connected:
            self.disconnect()

        if not self._i2c_connection.validate_connection_params():
            return

        from . import __no_connect__
        if self._i2c_connection.connect(__no_connect__):
            if hasattr(self, "_connect_button"):
                self._connect_button.config(text="Disconnect", command=self.disconnect)
            if hasattr(self, "_connection_type_option"):
                self._connection_type_option.config(state="disabled")
            if hasattr(self, "_enable_readback_checkbutton"):
                self._enable_readback_checkbutton.config(state="normal")
            self._set_connected(True)
            if hasattr(self, "_i2c_window"):
                self._test_device_button.config(state='normal')
                self._read_register_button.config(state='normal')
                self._write_register_button.config(state='normal')
                self._read_block_button.config(state='normal')
                self._write_block_button.config(state='normal')
            if hasattr(self, "_i2c_scan_window"):
                self._toggle_logging_button.config(state='normal')

    def disconnect(self):
        if not self.is_connected:
            return

        self._i2c_connection.disconnect()

        if hasattr(self, "_connect_button"):
            self._connect_button.config(text="Connect", command=self.connect)
        if hasattr(self, "_connection_type_option"):
            self._connection_type_option.config(state="normal")
            if hasattr(self, "_enable_readback_checkbutton"):
                self._enable_readback_checkbutton.config(state="disabled")
        self._set_connected(False)
        if hasattr(self, "_i2c_window"):
            self._test_device_button.config(state='disabled')
            self._read_register_button.config(state='disabled')
            self._write_register_button.config(state='disabled')
            self._read_block_button.config(state='disabled')
            self._write_block_button.config(state='disabled')
        if hasattr(self, "_i2c_scan_window"):
            self._toggle_logging_button.config(state='disabled')

    def read_device_memory(self, device_address: int, memory_address: int, byte_count: int = 1, register_bits: int = 16, register_length: int = 8, read_type: str = 'Normal'):
        if not self.is_connected:
            raise RuntimeError("You must first connect to a device before trying to read registers from it")

        from .functions import validate_i2c_address
        if not validate_i2c_address(hex(device_address)):
            raise RuntimeError("Invalid I2C address received: {}".format(hex(device_address)))

        this_time = time.time_ns()
        if this_time - self._time_last_i2c_command < self._successive_i2c_delay_us * 1000:
            time.sleep(self._successive_i2c_delay_us/10E6)
            this_time = time.time_ns()
        self._time_last_i2c_command = this_time

        from . import __no_connect__
        from . import __no_connect_type__
        if __no_connect__:
            retVal = []
            if __no_connect_type__ == "check" or self._previous_write_value is None:
                retVal = [i for i in range(byte_count)]
                if byte_count == 1:
                    retVal[0] = 0x42
            elif __no_connect_type__ == "echo":
                retVal = [self._previous_write_value for i in range(byte_count)]
            else:
                self._logger.error("Massive error, no connect was set, but an incorrect no connect type was chosen, so the I2C emulation behaviour is unknown")
            return retVal

        return self._i2c_connection.read_device_memory(device_address, memory_address, byte_count, register_bits, register_length, read_type)

    def write_device_memory(self, device_address: int, memory_address: int, data: list[int], register_bits: int = 16, register_length: int = 8, write_type: str = 'Normal'):
        if not self.is_connected:
            raise RuntimeError("You must first connect to a device before trying to write registers to it")

        from .functions import validate_i2c_address
        if not validate_i2c_address(hex(device_address)):
            raise RuntimeError("Invalid I2C address received: {}".format(hex(device_address)))

        this_time = time.time_ns()
        if this_time - self._time_last_i2c_command < self._successive_i2c_delay_us * 1000:
            time.sleep(self._successive_i2c_delay_us/10E6)
            this_time = time.time_ns()
        self._time_last_i2c_command = this_time

        from . import __no_connect__
        from . import __no_connect_type__
        if __no_connect__:
            if __no_connect_type__ == "echo":
                self._previous_write_value = data[len(data)-1]
            return

        self._i2c_connection.write_device_memory(device_address, memory_address, data, register_bits, register_length, write_type)

    def display_i2c_window(self):
        if hasattr(self, "_i2c_window"):
            self._logger.info("I2C window already open")
            self._i2c_window.focus()
            return

        if not hasattr(self, '_do_logging_i2c'):
            self.is_logging_i2c = False

        state = 'normal'
        if not self.is_connected:
            state = 'disabled'

        self._style = ttk.Style(self._frame)

        self._i2c_window = tk.Toplevel(self._parent._root)
        self._i2c_window.title(self._parent._title + " - I2C Monitor")
        self._i2c_window.protocol('WM_DELETE_WINDOW', self.close_i2c_window)
        self._i2c_window.columnconfigure(100, weight=1)
        self._i2c_window.rowconfigure(100, weight=1)

        self._i2c_window_top_frame = ttk.Frame(self._i2c_window, padding="0 0 0 0")  # For the main content
        self._i2c_window_top_frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_window_top_frame.columnconfigure(200, weight=1)
        self._i2c_window_top_frame.rowconfigure(100, weight=1)

        self._i2c_window_bottom_frame = ttk.Frame(self._i2c_window, padding="0 0 0 0")  # For the status info
        self._i2c_window_bottom_frame.grid(column=100, row=200, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_window_bottom_frame.columnconfigure(0, weight=1)

        # Place a control frame on the left side of the top frame
        self._i2c_window_control_frame = ttk.Frame(self._i2c_window_top_frame, padding="5 5 5 5")
        self._i2c_window_control_frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_window_control_frame.rowconfigure(200, weight=1)
        self._i2c_window_control_frame.rowconfigure(400, weight=1)

        # Place a frame at the top of the control frame for generic controls
        self._i2c_window_generic_control_frame = ttk.Frame(self._i2c_window_control_frame, padding="0 0 0 0")
        self._i2c_window_generic_control_frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_window_generic_control_frame.columnconfigure(100, weight=1)
        self._i2c_window_generic_control_frame.columnconfigure(300, weight=1)

        # Place an I2C control frame
        self._i2c_window_connection_control_frame = ttk.LabelFrame(self._i2c_window_control_frame, text="I2C Comm", padding="0 0 0 0")
        self._i2c_window_connection_control_frame.grid(column=100, row=300, sticky=(tk.N, tk.W, tk.E, tk.S))

        # Place main display text on right side of the top frame
        self._text_display = tk.Text(self._i2c_window_top_frame, state='disabled', width=80, wrap=tk.WORD)#'none')
        self._text_display.grid(column=200, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

        # Place scrollbar against the main display text
        self._scrollbar = ttk.Scrollbar(self._i2c_window_top_frame, command=self._text_display.yview)
        self._scrollbar.grid(column=201, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._text_display.config(yscrollcommand=self._scrollbar.set)

        # Place the logging toggle button at the top of the control frame
        self._toggle_logging_button = ttk.Button(self._i2c_window_generic_control_frame, text="Enable Logging", command=self.toggle_i2c_logging)
        self._toggle_logging_button.grid(column=200, row=100, sticky=(tk.W, tk.E), padx=(0,5))

        # Place the clear log button below the logging toggle button
        self._clear_logging_button = ttk.Button(self._i2c_window_generic_control_frame, text="Clear Log", command=self.clear_i2c_log)
        self._clear_logging_button.grid(column=200, row=110, sticky=(tk.W, tk.E), padx=(0,5))

        # Place logging status at right of status bar
        self._i2c_logging_status_label = ttk.Label(self._i2c_window_bottom_frame, textvariable=self._i2c_logging_window_status_var)
        self._i2c_logging_status_label.grid(column=500, row=100, sticky=(tk.E), padx=(0,15), pady=(0,5))
        self.is_logging_i2c = self.is_logging_i2c


        from .functions import validate_8bit_register
        from .functions import validate_i2c_address
        from .functions import validate_num
        self._register_8_validate_cmd = (self._frame.register(validate_8bit_register), '%P')
        self._register_16_validate_cmd = (self._frame.register(lambda string : validate_variable_bit_register(string, 16)), '%P')
        self._address_validate_cmd = (self._frame.register(validate_i2c_address), '%P')
        self._block_size_cmd = (self._frame.register(validate_num), '%P')
        self._bit_length_validate_cmd = (self._frame.register(validate_bit_length), '%P')

        ###################################################
        # Main controls to send/receive I2C info
        ###################################################
        self._i2c_window_input_frame = ttk.Frame(self._i2c_window_connection_control_frame, padding="0 0 0 0")
        self._i2c_window_input_frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

        self._i2c_window_address_label = ttk.Label(self._i2c_window_input_frame, text="Device Address:")
        self._i2c_window_address_label.grid(column=100, row=100, padx=(0,5), sticky=(tk.E))
        self._i2c_window_address_entry = ttk.Entry(self._i2c_window_input_frame, textvariable=self._i2c_window_address_var, width=6)
        self._i2c_window_address_entry.grid(column=200, row=100)

        # Validate the I2C address
        self._invalid_i2c_address_cmd  = (self._frame.register(lambda string : self.send_message("Invalid I2C address trying to be set in I2C monitor: {}".format(string), "Warning")), '%P')
        self._i2c_window_address_entry.config(validate='key', validatecommand=self._address_validate_cmd, invalidcommand=self._invalid_i2c_address_cmd)

        self._i2c_window_register_label = ttk.Label(self._i2c_window_input_frame, text="Register Address:")
        self._i2c_window_register_label.grid(column=100, row=200, padx=(0,5), sticky=(tk.E))
        self._i2c_window_register_entry = ttk.Entry(self._i2c_window_input_frame, textvariable=self._i2c_window_register_var, width=6)
        self._i2c_window_register_entry.grid(column=200, row=200)

        # Validate the register address
        self._invalid_register_address_cmd  = (self._frame.register(lambda string : self.send_message("Invalid register address trying to be set in I2C monitor: {}".format(string), "Warning")), '%P')
        self._i2c_window_register_entry.config(validate='key', validatecommand=self._register_16_validate_cmd, invalidcommand=self._invalid_register_address_cmd)

        self._i2c_window_register_value_label = ttk.Label(self._i2c_window_input_frame, text="Register Value:")
        self._i2c_window_register_value_label.grid(column=100, row=300, padx=(0,5), sticky=(tk.E))
        self._i2c_window_register_value_entry = ttk.Entry(self._i2c_window_input_frame, textvariable=self._i2c_window_register_value_var, width=6)
        self._i2c_window_register_value_entry.grid(column=200, row=300)

        # Validate register value
        self._invalid_register_value_cmd  = (self._frame.register(lambda string : self.send_message("Invalid register value trying to be set in I2C monitor: {}".format(string), "Warning")), '%P')
        self._i2c_window_register_value_entry.config(validate='key', validatecommand=self._register_8_validate_cmd, invalidcommand=self._invalid_register_value_cmd)

        self._i2c_window_block_size_label = ttk.Label(self._i2c_window_input_frame, text="Block Size:")
        self._i2c_window_block_size_label.grid(column=100, row=400, padx=(0,5), sticky=(tk.E))
        self._i2c_window_block_size_entry = ttk.Entry(self._i2c_window_input_frame, textvariable=self._i2c_window_block_size_var, width=6)
        self._i2c_window_block_size_entry.grid(column=200, row=400)

        # Validate block size
        self._invalid_block_size_cmd  = (self._frame.register(lambda string : self.send_message("Invalid block size trying to be set in I2C monitor: {}".format(string), "Warning")), '%P')
        self._i2c_window_block_size_entry.config(validate='key', validatecommand=self._block_size_cmd, invalidcommand=self._invalid_block_size_cmd)

        self._i2c_window_register_length_label = ttk.Label(self._i2c_window_input_frame, text="Register Length:")
        self._i2c_window_register_length_label.grid(column=100, row=500, padx=(0,5), sticky=(tk.E))
        self._i2c_window_register_length_entry = ttk.Entry(self._i2c_window_input_frame, textvariable=self._i2c_window_register_length_var, width=6)
        self._i2c_window_register_length_entry.grid(column=200, row=500)

        # Validate the register length
        self._invalid_register_length_cmd = (self._frame.register(self._invalid_register_length), '%P')
        self._i2c_window_register_length_entry.config(validate='focusout', validatecommand=self._bit_length_validate_cmd, invalidcommand=self._invalid_register_length_cmd)

        self._i2c_window_register_address_length_label = ttk.Label(self._i2c_window_input_frame, text="Register Address Length:")
        self._i2c_window_register_address_length_label.grid(column=100, row=600, padx=(0,5), sticky=(tk.E))
        self._i2c_window_register_address_length_entry = ttk.Entry(self._i2c_window_input_frame, textvariable=self._i2c_window_register_address_length_var, width=6)
        self._i2c_window_register_address_length_entry.grid(column=200, row=600)

        # Validate the register address length
        self._invalid_register_address_length_cmd = (self._frame.register(self._invalid_register_address_length), '%P')
        self._i2c_window_register_address_length_entry.config(validate='focusout', validatecommand=self._bit_length_validate_cmd, invalidcommand=self._invalid_register_address_length_cmd)

        self._i2c_window_button_frame = ttk.Frame(self._i2c_window_connection_control_frame, padding="0 0 0 0")
        self._i2c_window_button_frame.grid(column=100, row=200, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_window_button_frame.columnconfigure(0, weight=1)

        self._test_device_button = ttk.Button(self._i2c_window_button_frame, text="Test Device", command=self.test_i2c_device, state=state)
        self._test_device_button.grid(column=100, row=100, sticky=(tk.W, tk.E))

        self._read_register_button = ttk.Button(self._i2c_window_button_frame, text="Read Register", command=self.read_i2c_device_register, state=state)
        self._read_register_button.grid(column=100, row=200, sticky=(tk.W, tk.E))

        self._write_register_button = ttk.Button(self._i2c_window_button_frame, text="Write Register", command=self.write_i2c_device_register, state=state)
        self._write_register_button.grid(column=100, row=300, sticky=(tk.W, tk.E))

        self._read_block_button = ttk.Button(self._i2c_window_button_frame, text="Read Block", command=self.read_i2c_device_block, state=state)
        self._read_block_button.grid(column=100, row=400, sticky=(tk.W, tk.E))

        self._write_block_button = ttk.Button(self._i2c_window_button_frame, text="Write Block", command=self.write_i2c_device_block, state=state)
        self._write_block_button.grid(column=100, row=500, sticky=(tk.W, tk.E))

        self._i2c_window.update()
        self._i2c_window.minsize(self._i2c_window.winfo_width(), self._i2c_window.winfo_height())

    def _invalid_register_length(self, string: str):
        self.send_message("Invalid register length trying to be set in I2C monitor: {}".format(string), "Warning")

        length = 8
        if string != "":
            digit_regex = r"\d+"

            if re.fullmatch(digit_regex, string) is not None:
                length = ceil(int(string, 10)/8)*8

        self._i2c_window_register_length_var.set(length)

    def _invalid_register_address_length(self, string: str):
        self.send_message("Invalid register address length trying to be set in I2C monitor: {}".format(string), "Warning")

        length = 8
        if string != "":
            digit_regex = r"\d+"

            if re.fullmatch(digit_regex, string) is not None:
                length = ceil(int(string, 10)/8)*8

        self._i2c_window_register_address_length_var.set(length)

    def close_i2c_window(self):
        if not hasattr(self, "_i2c_window"):
            self._logger.info("I2C window does not exist")
            return

        self.is_logging_i2c = False

        self._i2c_window.destroy()
        del self._i2c_window

    def toggle_i2c_logging(self):
        self.is_logging_i2c = not self.is_logging_i2c

        button_text = "Enable Logging"
        if self.is_logging_i2c:
            button_text = "Disable Logging"

        self._toggle_logging_button.config(text=button_text)

    def clear_i2c_log(self):
        self._text_display.configure(state='normal')
        self._text_display.delete("1.0", tk.END)
        #self._text_display.insert('end', self.get_log())
        self._text_display.configure(state='disabled')

    def test_i2c_device(self):
        self._normalize_i2c_address()

        self._i2c_connection.check_i2c_device(int(self._i2c_window_address_var.get(), 0))

    def read_i2c_device_register(self):
        self._normalize_i2c_address()
        self._normalize_register_address()
        self._normalize_register_length()
        self._normalize_register_address_length()

        register_length = int(self._i2c_window_register_length_var.get(), 0)
        byte_count = ceil(register_length/8)
        register_address_length = int(self._i2c_window_register_address_length_var.get(), 0)

        self._i2c_connection.read_device_memory(
            int(self._i2c_window_address_var.get(), 0),
            int(self._i2c_window_register_var.get(), 0),
            byte_count = byte_count,
            register_bits = register_address_length,
            register_length = register_length,
        )

    def write_i2c_device_register(self):
        self._normalize_i2c_address()
        self._normalize_register_address()
        self._normalize_register_value()
        self._normalize_register_length()
        self._normalize_register_address_length()

        register_length = int(self._i2c_window_register_length_var.get(), 0)
        byte_count = ceil(register_length/8)
        register_address_length = int(self._i2c_window_register_address_length_var.get(), 0)

        if byte_count == 1:
            data = [int(self._i2c_window_register_value_var.get(), 0)]
        else:
            # Assuming fixed little endian
            data = [None for i in range(byte_count)]
            tmp = int(self._i2c_window_register_value_var.get(), 0)
            for i in range(byte_count):
                data[i] = tmp & 0xff
                tmp = tmp >> 8

        self._i2c_connection.write_device_memory(
            int(self._i2c_window_address_var.get(), 0),
            int(self._i2c_window_register_var.get(), 0),
            data,
            register_bits = register_address_length,
            register_length = register_length,
        )

    def read_i2c_device_block(self):
        self._normalize_i2c_address()
        self._normalize_register_address()
        self._normalize_block_size()
        self._normalize_register_length()
        self._normalize_register_address_length()

        register_length = int(self._i2c_window_register_length_var.get(), 0)
        byte_count = ceil(register_length/8)
        register_address_length = int(self._i2c_window_register_address_length_var.get(), 0)

        self._i2c_connection.read_device_memory(
            int(self._i2c_window_address_var.get(), 0),
            int(self._i2c_window_register_var.get(), 0),
            int(self._i2c_window_block_size_var.get(), 0) * byte_count,
            register_bits = register_address_length,
            register_length = register_length,
        )

    def write_i2c_device_block(self):
        self._normalize_i2c_address()
        self._normalize_register_address()
        self._normalize_register_value()
        self._normalize_block_size()
        self._normalize_register_length()
        self._normalize_register_address_length()

        register_length = int(self._i2c_window_register_length_var.get(), 0)
        byte_count = ceil(register_length/8)
        register_address_length = int(self._i2c_window_register_address_length_var.get(), 0)

        block_size = int(self._i2c_window_block_size_var.get(), 0)

        if byte_count == 1:
            data = [int(self._i2c_window_register_value_var.get(), 0) for i in range(block_size)]
        else:
            # Assuming fixed little endian
            tmp_data = [None for i in range(byte_count)]
            tmp = int(self._i2c_window_register_value_var.get(), 0)
            for i in range(byte_count):
                tmp_data[i] = tmp & 0xff
                tmp = tmp >> 8

            data = []
            for i in range(block_size):
                data += tmp_data


        self._i2c_connection.write_device_memory(
            int(self._i2c_window_address_var.get(), 0),
            int(self._i2c_window_register_var.get(), 0),
            data,
            register_bits = register_address_length,
            register_length = register_length,
        )

    def direct_i2c(self, commands: list[int]):
        this_time = time.time_ns()
        if this_time - self._time_last_i2c_command < self._successive_i2c_delay_us * 1000:
            time.sleep(self._successive_i2c_delay_us/10E6)
            this_time = time.time_ns()
        self._time_last_i2c_command = this_time

        return self._i2c_connection._direct_i2c(commands)

    @property
    def is_logging_i2c(self):
        return self._do_logging_i2c

    @is_logging_i2c.setter
    def is_logging_i2c(self, value):
        if value not in [True, False]:
            raise TypeError("Logging can only be true or false")

        self._do_logging_i2c = value

        if self._do_logging_i2c:
            self._i2c_logging_window_status_var.set("Logging Enabled")
            self._i2c_logging_status_label.config(background = self._green_col, foreground = self._black_col)
            #if self._connection_status_label.cget('background') == '':
            if self._style.theme_use() == 'aqua':
                self._i2c_logging_status_label.config(foreground = self._green_col)
        else:
            self._i2c_logging_window_status_var.set("Logging Disabled")
            self._i2c_logging_status_label.config(background = self._orange_col, foreground = self._black_col)
            #if self._connection_status_label.cget('background') == '':
            if self._style.theme_use() == 'aqua':
                self._i2c_logging_status_label.config(foreground = self._orange_col)

    def _normalize_i2c_address(self):
        self._i2c_window_address_var.set(hex_0fill(self._i2c_window_address_var.get(), 7))

    def _normalize_register_address(self):
        length = int(self._i2c_window_register_address_length_var.get(), 0)
        self._i2c_window_register_var.set(hex_0fill(self._i2c_window_register_var.get(), length))

    def _normalize_register_value(self):
        length = int(self._i2c_window_register_length_var.get(), 0)
        self._i2c_window_register_value_var.set(hex_0fill(self._i2c_window_register_value_var.get(), length))

    def _normalize_block_size(self):
        value = self._i2c_window_block_size_var.get()
        if value == '':
            value = "0"
        else:
            value = str(int(value, 0))
        self._i2c_window_block_size_var.set(value)

    def _normalize_register_length(self):
        self._i2c_window_register_length_var.set(str(int(self._i2c_window_register_length_var.get(), 0)))

    def _normalize_register_address_length(self):
        self._i2c_window_register_address_length_var.set(str(int(self._i2c_window_register_address_length_var.get(), 0)))

    def send_i2c_logging_message(self, message: str):
        if not self.is_logging_i2c:
            return

        self._text_display.configure(state='normal')
        self._text_display.insert('end', message + "\n")
        self._text_display.configure(state='disabled')

    def display_i2c_scan_window(self):
        if hasattr(self, "_i2c_scan_window"):
            self._logger.info("Scan I2C window already open")
            self._i2c_scan_window.focus()
            return

        state = 'normal'
        if not self.is_connected:
            state = 'disabled'

        self._i2c_scan_window = tk.Toplevel(self._parent._root)
        self._i2c_scan_window.title(self._parent._title + " - Scan I2C Devices")
        self._i2c_scan_window.protocol('WM_DELETE_WINDOW', self.close_i2c_scan_window)
        self._i2c_scan_window.columnconfigure(100, weight=1)
        self._i2c_scan_window.rowconfigure(100, weight=1)

        self._i2c_scan_window_top_frame = ttk.Frame(self._i2c_scan_window, padding="0 0 0 0")  # For the main content
        self._i2c_scan_window_top_frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_scan_window_top_frame.columnconfigure(100, weight=1)
        self._i2c_scan_window_top_frame.rowconfigure(100, weight=1)

        self._i2c_scan_window_bottom_frame = ttk.Frame(self._i2c_scan_window, padding="0 0 0 0")  # For the status info
        self._i2c_scan_window_bottom_frame.grid(column=100, row=200, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_scan_window_bottom_frame.columnconfigure(0, weight=1)
        self._i2c_scan_window_bottom_frame.columnconfigure(100, weight=1)

        # Place a control frame on the right side of the top frame
        self._i2c_scan_window_control_frame = ttk.Frame(self._i2c_scan_window_top_frame, padding="5 5 5 5")
        self._i2c_scan_window_control_frame.grid(column=500, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._i2c_scan_window_control_frame.rowconfigure(0, weight=1)

        # Place main display text on left side of the top frame
        self._scan_display = tk.Text(self._i2c_scan_window_top_frame, state='disabled', width=80, wrap=tk.WORD)#'none')
        self._scan_display.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

        # Place scrollbar against the main display text
        self._scan_scrollbar = ttk.Scrollbar(self._i2c_scan_window_top_frame, command=self._scan_display.yview)
        self._scan_scrollbar.grid(column=101, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))
        self._scan_display.config(yscrollcommand=self._scan_scrollbar.set)

        # Place the scan devices button at the bottom of the control frame
        self._toggle_logging_button = ttk.Button(self._i2c_scan_window_control_frame, text="Scan Devices", command=self.scan_i2c_devices, state=state)
        self._toggle_logging_button.grid(column=100, row=100, sticky=(tk.W, tk.E), padx=(0,5))

        # Place a clear button below
        self._clear_scan_button = ttk.Button(self._i2c_scan_window_control_frame, text="Clear", command=self.clear_i2c_scan)
        self._clear_scan_button.grid(column=100, row=110, sticky=(tk.W, tk.E), padx=(0,5))

        # Place an empty label below to reserve the vertical space
        self._empty_scan_label = ttk.Label(self._i2c_scan_window_bottom_frame, text=" ")
        self._empty_scan_label.grid(column=0, row=100)

        self._i2c_scan_window.update()
        self._i2c_scan_window.minsize(self._i2c_scan_window.winfo_width(), self._i2c_scan_window.winfo_height())

    def close_i2c_scan_window(self):
        if not hasattr(self, "_i2c_scan_window"):
            self._logger.info("Scan I2C window does not exist")
            return

        self._i2c_scan_window.destroy()
        del self._i2c_scan_window

    def scan_i2c_devices(self):
        self.scan_progress(0)

        found = []
        last_update = time.time_ns()
        for device_address in range(128):
            address_hex = hex_0fill(device_address, 8)
            if self.check_i2c_device(address_hex):
                found.append(address_hex)

            curr_time = time.time_ns()
            if curr_time - last_update > 0.3 * 10**9:
                last_update = curr_time
                progress = device_address/128.0 * 100.0
                self.scan_progress(progress)
                self._parent._root.update()

            # For testing without hardware
            #time.sleep(10**-2)

        if len(found) == 0:
            self._scan_display.configure(state='normal')
            self._scan_display.insert('end', "Did not find any devices\n\n")
            self._scan_display.configure(state='disabled')
        else:
            self._scan_display.configure(state='normal')
            self._scan_display.insert('end', "Found devices at the following I2C addresses:\n")
            for entry in found:
                self._scan_display.insert('end', f" - {entry}\n")
            self._scan_display.insert('end', "\n")
            self._scan_display.configure(state='disabled')

        self.clear_scan_progress()

    def clear_i2c_scan(self):
        self._scan_display.configure(state='normal')
        self._scan_display.delete("1.0", tk.END)
        self._scan_display.configure(state='disabled')

    def scan_progress(self, percentage):
        if not hasattr(self, "_scan_progress") or self._scan_progress is None:
            self._scan_progress = ttk.Progressbar(self._i2c_scan_window_bottom_frame, mode='determinate', length='300')
            self._scan_progress.grid(column=50, row=100, sticky=(tk.W, tk.E))

        self._scan_progress['value'] = int(percentage)

    def clear_scan_progress(self):
        if hasattr(self, "_scan_progress") and self._scan_progress is not None:
            self._scan_progress.destroy()
            self._scan_progress = None

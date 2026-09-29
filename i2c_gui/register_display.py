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
from .functions import hex_0fill

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging

from math import ceil

class Register_Display(GUI_Helper):
    _parent: GUI_Helper
    _display_var: tk.StringVar
    _shadow_var: tk.Variable

    def __init__(self, parent: GUI_Helper, register_name: str, display_var: tk.StringVar, read_only: bool = False, register_length: int = 8):
        super().__init__(parent, None, parent._logger)

        self._name = register_name
        self._enabled = False
        self._display_var = display_var
        self._callback_update_shadow_var = self._display_var.trace_add('write', self._update_shadow_var)
        self._shadow_var = None
        self._read_only = read_only
        self._register_length = register_length

    @property
    def shadow_var(self):
        return self._shadow_var

    @shadow_var.setter
    def shadow_var(self, val: tk.Variable):
        if val is None or isinstance(val, tk.Variable):
            # Remove previous shadow var, if any
            if self._shadow_var is not None:
                self._shadow_var.trace_remove('write', self._callback_update_display_var)
                self._shadow_var = None

            # Update displayed value
            if val is not None:
                self._display_var.set(val.get())

            # Set new shadow var
            self._shadow_var = val
            if self._shadow_var is not None:
                self._callback_update_display_var = self._shadow_var.trace_add('write', self._update_display_var)
            else:
                del self._callback_update_display_var
        else:
            raise RuntimeError("Wrong type for shadow variable: '{}'".format(type(val)))

    def enable(self):
        self._enabled = True
        if hasattr(self, "_value_entry") and not self._read_only:
            self._value_entry.config(state="normal")
        if hasattr(self, "_read_button"):
            self._read_button.config(state="normal")
        if hasattr(self, "_write_button"):
            self._write_button.config(state="normal")

    def disable(self):
        self._enabled = False
        if hasattr(self, "_value_entry"):
            self._value_entry.config(state="disabled")
        if hasattr(self, "_read_button"):
            self._read_button.config(state="disabled")
        if hasattr(self, "_write_button"):
            self._write_button.config(state="disabled")

    def set_position(self, col: int, row: int):
        self._frame.grid(column=col, row=row, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

    def get_required_size(self):
        return (self._frame.winfo_reqwidth(), self._frame.winfo_reqheight())

    def get_size(self):
        return (self._frame.winfo_width(), self._frame.winfo_height())

    def prepare_display(self, element: tk.Tk, col: int, row: int, read_function=None, write_function=None):
        # TODO: Add a check in case this function is called a second time? Also to protect all the callbacks and other stuff?
        self._frame = ttk.LabelFrame(element, text=self._name)
        self.set_position(col, row)

        state = 'disabled'
        if self._enabled:
            state = 'normal'

        self._value_label = ttk.Label(self._frame, text="Value:")
        self._value_label.grid(column=100, row=100, sticky=tk.E)

        value_state = state
        if not self._read_only:
            value_state = 'disabled'
        width = ceil(self._register_length/4) + 3
        self._value_entry = ttk.Entry(self._frame, textvariable=self._display_var, state=value_state, width=width)
        self._value_entry.grid(column=200, row=100, sticky=tk.W)

        if not self._read_only:
            from .functions import validate_variable_bit_register
            self._register_validate_cmd = (self._frame.register(lambda string : validate_variable_bit_register(string, self._register_length)), '%P')
            self._register_invalid_cmd  = (self._frame.register(self.invalid_register_value), '%P')
            self._value_entry.config(validate='key', validatecommand=self._register_validate_cmd, invalidcommand=self._register_invalid_cmd)


        self._value_binary_label = ttk.Label(self._frame, text="Binary:")
        self._value_binary_label.grid(column=100, row=200, sticky=tk.E)

        self._value_binary_frame = ttk.Frame(self._frame)
        self._value_binary_frame.grid(column=200, row=200, sticky=(tk.W, tk.S, tk.N), padx=0, pady=0)
        self._frame.rowconfigure(200, weight=1)
        self._value_binary_frame.rowconfigure(100, weight=1)

        self._value_binary_prefix = ttk.Label(self._value_binary_frame, font='TkFixedFont', text="0b")
        self._value_binary_prefix.grid(column=100, row=100)

        for bit_idx in range(self._register_length):
            bit_num = self._register_length - 1 - bit_idx
            bit_label = ttk.Label(self._value_binary_frame, font='TkFixedFont', text="0")
            bit_label.grid(column = (2+bit_idx)*100, row=100)
            bit_label.bind("<Button-1>", lambda e, bit=bit_num:self._toggle_bit(bit))
            setattr(self, f'_value_binary_bit{bit_num}', bit_label)
        self._callback_update_binary_repr = self._display_var.trace_add('write', self._update_binary_repr)


        if read_function is not None:
            self._read_button = ttk.Button(self._frame, text="R", state=state, command=read_function, width=1.5)
            self._read_button.grid(column=400, row=100, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(10,0))

        if write_function is not None and not self._read_only:
            self._write_button = ttk.Button(self._frame, text="W", state=state, command=lambda func=write_function: self._write(func), width=1.5)
            self._write_button.grid(column=400, row=200, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(10,0))


        self._frame.columnconfigure(0, weight=1)
        self._frame.columnconfigure(500, weight=1)

        self._update_binary_repr()

    def _write(self, func):
        if self._read_only:
            return
        if self.validate_register():
            func()
        else:
            self.send_message("Unable to write register {}, check that the value makes sense: '{}'".format(self._name, self._display_var.get()))

    def _toggle_bit(self, bit_idx):
        if self._enabled:
            value = int(self._display_var.get(), 0)
            self._display_var.set(hex_0fill(value ^ (1 << bit_idx), self._register_length))

    def _update_display_var(self, var=None, index=None, mode=None):
        self._logger.detailed_trace("Attempting to update display var from shadow var for {}".format(self._name))
        if hasattr(self, "_updating_from_display_var"):  # Avoid an infinite loop where the two variables trigger each other
            return

        if self._shadow_var is not None:
            self._logger.trace("Updating display var from shadow var for {}".format(self._name))

            self._updating_from_shadow_var = True

            self._display_var.set(self._shadow_var.get())

            del self._updating_from_shadow_var

    def _update_shadow_var(self, var=None, index=None, mode=None):
        self._logger.detailed_trace("Attempting to update shadow var from display var for {}".format(self._name))
        if hasattr(self, "_updating_from_shadow_var"):  # Avoid an infinite loop where the two variables trigger each other
            return

        if self._shadow_var is not None:
            self._logger.trace("Updating shadow var from display var for {}".format(self._name))

            self._updating_from_display_var = True

            self._shadow_var.set(self._display_var.get())

            del self._updating_from_display_var

    def _update_binary_repr(self, var=None, index=None, mode=None):
        binary_string = ""
        for i in range(self._register_length):
            binary_string += "0"
        if self._display_var.get() != '' and self._display_var.get() != '0x':  # If value is set, decode the binary string
            binary_string = format(int(self._display_var.get(), 0), 'b')
            if len(binary_string) < self._register_length:
                prepend = '0'*(self._register_length-len(binary_string))
                binary_string = prepend + binary_string
        for bit in range(self._register_length):
            value = binary_string[self._register_length-1-bit]
            getattr(self, "_value_binary_bit{}".format(bit)).config(text=value)

        self._parent.update_whether_modified()

    def invalid_register_value(self, string: str):
        self.send_message("Invalid value trying to be set for register {}: {}".format(self._name, string))

    def validate_register(self):
        if self._display_var.get() == "" or self._display_var.get() == "0x":
            return False
        self._display_var.set(hex_0fill(int(self._display_var.get(), 0), self._register_length))
        return True
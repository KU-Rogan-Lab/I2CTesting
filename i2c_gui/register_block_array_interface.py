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

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from chips.base_chip import Base_Chip

from .base_interface import Base_Interface

class Register_Block_Array_Interface(Base_Interface):
    _parent: Base_Chip
    def __init__(self, parent: Base_Chip, address_space: str, block_name: str, block_title: str, button_title: str, register_model, read_only: bool = False, register_length: int = 8):
        super().__init__(parent, False, False)

        self._address_space = address_space
        self._block_name = block_name
        self._block_title = block_title
        self._button_title = button_title
        self._register_model = register_model
        self._read_only = read_only
        self._register_length = register_length

    def update_whether_modified(self):
        self._parent.update_whether_modified()

    def enable(self):
        super().enable()
        if hasattr(self, "_read_button"):
            self._read_button.config(state="normal")
        if hasattr(self, "_write_button"):
            self._write_button.config(state="normal")
        if hasattr(self, "_register_handle"):
            for register in self._register_handle:
                self._register_handle[register].enable()

    def disable(self):
        super().disable()
        if hasattr(self, "_read_button"):
            self._read_button.config(state="disabled")
        if hasattr(self, "_write_button"):
            self._write_button.config(state="disabled")
        if hasattr(self, "_register_handle"):
            for register in self._register_handle:
                self._register_handle[register].disable()

    def read_register(self, register_name):
        self._parent.read_register(self._address_space, self._block_name, register_name)

    def write_register(self, register_name):
        if self._read_only:
            return
        if not self._parent.write_register(self._address_space, self._block_name, register_name, write_check=self._parent.enable_readback):
            self.send_message("Failed writing the register {} in block {} of address space {}.".format(register_name, self._block_name, self._address_space), "Error")

    def prepare_display(self, element: tk.Tk, col: int, row: int, register_columns: int):
        registers = list(self._register_model.keys())

        self._frame = ttk.LabelFrame(element, text=self._block_title)
        self._frame.grid(column=col, row=row, sticky=(tk.N, tk.W, tk.E, tk.S))#, padx=5, pady=5)
        self._frame.columnconfigure(100, weight=1)

        state = 'disabled'
        if self._enabled:
            state = 'normal'

        self._control_frame = ttk.Frame(self._frame)
        self._control_frame.grid(column=100, row=200, sticky=(tk.N, tk.E))

        self._read_button = ttk.Button(
            self._control_frame,
            text="Read " + self._button_title,
            command=lambda parent=self._parent, address_space=self._address_space, block=self._block_name:parent.read_all_block(address_space, block),
            state=state
        )
        self._read_button.grid(column=100, row=100, sticky=(tk.W, tk.E))

        if not self._read_only:
            self._write_button = ttk.Button(
                self._control_frame,
                text="Write " + self._button_title,
                command=lambda parent=self._parent, address_space=self._address_space, block=self._block_name:parent.write_all_block(address_space, block, write_check=parent.enable_readback),
                state=state
            )
            self._write_button.grid(column=200, row=100, sticky=(tk.W, tk.E))

        self._register_frame = ttk.Frame(self._frame)
        self._register_frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

        first_register = None

        from .register_display import Register_Display
        self._register_handle = {}
        index = 0
        for col in range(register_columns):
            self._register_frame.columnconfigure((col + 1)*100, weight=1)

        for register in registers:
            if 'display' in self._register_model[register] and not self._register_model[register]['display']:
                continue
            if index == 0:
                first_register = register
            column = int(index % register_columns)
            row    = int(index / register_columns)
            tk_column = (column + 1) * 100
            tk_row = (row + 1) * 100
            display_var = self._parent.get_display_var(self._address_space, self._block_name, register)
            read_only = False
            if 'read_only' in self._register_model[register]:
                read_only = self._register_model[register]['read_only']
            handle = Register_Display(
                self,
                register_name=register,
                display_var=display_var,
                read_only=read_only,
                register_length=self._register_length,
            )
            handle.prepare_display(
                self._register_frame,
                tk_column,
                tk_row,
                read_function=lambda register=register: self.read_register(register),
                write_function=lambda register=register: self.write_register(register),
            )
            self._register_handle[register] = handle
            index += 1

        self.update_array_display_vars()

        if first_register is not None:
            self._frame.update_idletasks()
            self._register_orig_size = self._register_handle[first_register].get_required_size()
            self._current_displayed_columns = register_columns
            element.bind("<Configure>", self._check_for_resize, add='+')

    def update_array_display_vars(self):
        registers = list(self._register_model.keys())

        for register in registers:
            handle = self._register_handle[register]
            internal_var: tk.StringVar = self._parent.get_indexed_var(self._address_space, self._block_name, register)

            handle.shadow_var = internal_var

    def _check_for_resize(self, event):
        from math import floor
        size_in_registers = self._register_frame.winfo_width()/(self._register_orig_size[0]+10)  # Add 10 because that is the total padding that the register adds, 5 to each side
        if floor(size_in_registers) != self._current_displayed_columns:
            orig_registers = list(self._register_model.keys())

            registers = []
            for register in orig_registers:
                if 'display' not in self._register_model[register] or self._register_model[register]['display']:
                    registers += [register]

            for col in range(max(self._current_displayed_columns, floor(size_in_registers))):
                if col < floor(size_in_registers):
                    self._register_frame.columnconfigure((col + 1)*100, weight=1)  # Make sure the new columns have the correct weight
                else:
                    self._register_frame.columnconfigure((col + 1)*100, weight=0)  # Reset unused columns to unused weight

            self._current_displayed_columns = floor(size_in_registers)
            index = 0
            for register in registers:
                column = int(index % self._current_displayed_columns)
                row    = int(index / self._current_displayed_columns)
                tk_column = (column + 1) * 100
                tk_row = (row + 1) * 100
                self._register_handle[register].set_position(col=tk_column, row=tk_row)
                index += 1
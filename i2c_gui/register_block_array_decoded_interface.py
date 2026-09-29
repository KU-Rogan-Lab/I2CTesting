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

class Register_Block_Array_Decoded_Interface(Base_Interface):
    _parent: Base_Chip
    def __init__(self,
                 parent: Base_Chip,
                 address_space: str,
                 block_name: str,
                 block_title: str,
                 button_title: str,
                 decoding_info,
                 read_only: bool = False,
                 use_groups: bool = False,
                 ):
        super().__init__(parent, False, False)

        self._address_space = address_space
        self._block_name = block_name
        self._block_title = block_title
        self._button_title = button_title
        self._decoding_info = decoding_info
        self._read_only = read_only
        self._use_groups = use_groups

    def update_whether_modified(self):
        self._parent.update_whether_modified()

    def enable(self):
        super().enable()
        if hasattr(self, "_read_button"):
            self._read_button.config(state="normal")
        if hasattr(self, "_write_button"):
            self._write_button.config(state="normal")
        if hasattr(self, "_value_handle"):
            for value in self._value_handle:
                self._value_handle[value].enable()

    def disable(self):
        super().disable()
        if hasattr(self, "_read_button"):
            self._read_button.config(state="disabled")
        if hasattr(self, "_write_button"):
            self._write_button.config(state="disabled")
        if hasattr(self, "_value_handle"):
            for value in self._value_handle:
                self._value_handle[value].disable()

    def prepare_display(self, element: tk.Tk, col: int, row: int, value_columns: int):
        values = list(self._decoding_info.keys())

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

        self._value_frame = ttk.Frame(self._frame)
        self._value_frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

        first_value = None

        from .decoded_value_display import Decoded_Value_Display
        self._value_handle = {}
        index = 0
        for col in range(value_columns):
            self._value_frame.columnconfigure((col + 1)*100, weight=1)

        if not self._use_groups:
            for value in values:
                if 'display' in self._decoding_info[value] and not self._decoding_info[value]['display']:
                    continue
                if index == 0:
                    first_value = value
                column = int(index % value_columns)
                row    = int(index / value_columns)
                tk_column = (column + 1) * 100
                tk_row = (row + 1) * 100
                display_var = self._parent.get_decoded_display_var(self._address_space, self._block_name, value)
                handle = Decoded_Value_Display(
                    self,
                    value_name=value,
                    display_var=display_var,
                    metadata=self._decoding_info[value]
                )
                handle.prepare_display(
                    self._value_frame,
                    tk_column,
                    tk_row
                )
                self._value_handle[value] = handle
                index += 1

        self.update_array_display_vars()

        # Not currently working
        if first_value is not None:
            self._frame.update_idletasks()
            # TODO: fix the below since all cells should have the same size
            self._value_orig_size = self._value_handle[first_value].get_required_size()
            self._current_displayed_columns = value_columns
            element.bind("<Configure>", self._check_for_resize, add='+')

    def update_array_display_vars(self):
        values = list(self._decoding_info.keys())

        for value in values:
            handle = self._value_handle[value]
            internal_var: tk.StringVar = self._parent.get_decoded_indexed_var(self._address_space, self._block_name, value)

            handle.shadow_var = internal_var

    def _check_for_resize(self, event):
        from math import floor
        size_in_values = self._value_frame.winfo_width()/(self._value_orig_size[0]+10)  # Add 10 because that is the total padding that the register adds, 5 to each side
        #print(size_in_values)
        if floor(size_in_values) != self._current_displayed_columns:
            values = list(self._decoding_info.keys())

            for col in range(max(self._current_displayed_columns, floor(size_in_values))):
                if col < floor(size_in_values):
                    self._value_frame.columnconfigure((col + 1)*100, weight=1)  # Make sure the new columns have the correct weight
                else:
                    self._value_frame.columnconfigure((col + 1)*100, weight=0)  # Reset unused columns to unused weight

            self._current_displayed_columns = floor(size_in_values)
            index = 0
            for value in values:
                column = int(index % self._current_displayed_columns)
                row    = int(index / self._current_displayed_columns)
                tk_column = (column + 1) * 100
                tk_row = (row + 1) * 100
                self._value_handle[value].set_position(col=tk_column, row=tk_row)
                index += 1

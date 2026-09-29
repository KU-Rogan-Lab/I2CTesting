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

class Block_Array_Controller_Interface(Base_Interface):
    _parent: Base_Chip
    def __init__(self, parent: Base_Chip, title: str, control_variables):
        super().__init__(parent, False, False)

        self._title = title
        self._control_variables = control_variables
        self._tk_control_variables = {}

    def update_whether_modified(self):
        self._parent.update_whether_modified()

    def enable(self):
        super().enable()
        for variable in self._tk_control_variables:
            if "entry" in self._tk_control_variables[variable]:
                self._tk_control_variables[variable]["entry"].config(state="normal")

    def disable(self):
        super().disable()
        for variable in self._tk_control_variables:
            if "entry" in self._tk_control_variables[variable]:
                self._tk_control_variables[variable]["entry"].config(state="disabled")

    def prepare_display(self, element: tk.Tk, col: int, row: int, control_columns: int = 4):
        self._frame = ttk.LabelFrame(element, text=self._title)
        self._frame.grid(column=col, row=row, sticky=(tk.N, tk.W, tk.E, tk.S))#, padx=5, pady=5)
        self._frame.columnconfigure(99, weight=1)
        self._frame.columnconfigure((control_columns + 1)*100 + 10, weight=1)

        state = 'disabled'
        if self._enabled:
            state = 'normal'

        index = 0
        for variable in self._control_variables:
            column = int(index%control_columns)
            row    = int(index/control_columns)
            tk_column = (column + 1)*100
            tk_row    = (row    + 1)*100

            self._tk_control_variables[variable] = {}

            self._tk_control_variables[variable]["label"] = ttk.Label(self._frame, text=variable.title())
            self._tk_control_variables[variable]["label"].grid(column=tk_column, row=tk_row, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(8, 0))

            if self._control_variables[variable]["min"] == 0 and self._control_variables[variable]["max"] == 1:
                self._tk_control_variables[variable]["entry"] = ttk.Checkbutton(self._frame, variable=self._control_variables[variable]["variable"], state=state)
            else:
                self._tk_control_variables[variable]["entry"] = ttk.Entry(self._frame, textvariable=self._control_variables[variable]["variable"], state=state)

                self._variable_validate_cmd = (self._frame.register(lambda val, variable=variable: self._validate_control_variable(variable, val)), '%P')
                self._variable_invalid_cmd  = (self._frame.register(lambda val, variable=variable: self._invalid_control_variable(variable, val)), '%P')
                self._tk_control_variables[variable]["entry"].config(validate='key', validatecommand=self._variable_validate_cmd, invalidcommand=self._variable_invalid_cmd)

            self._tk_control_variables[variable]["entry"].grid(column=tk_column+1, row=tk_row, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(0, 8))

            index += 1

    def _validate_control_variable(self, variable: str, string: str):

        digit_regex = r"\d+"

        if string == "":
            return True

        import re
        if re.fullmatch(digit_regex, string) is not None:
            minimum = self._control_variables[variable]["min"]
            maximum = self._control_variables[variable]["max"]

            value = int(string, 10)
            if value >= minimum and value < maximum:
                return True
        return False

    def _invalid_control_variable(self, variable: str, string: str):
        self.send_message("Invalid value trying to be set for control variable '{}': {}".format(variable, string))
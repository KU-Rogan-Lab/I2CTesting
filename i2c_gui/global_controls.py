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
from .logging import Logging_Helper
from .connection_controller import Connection_Controller

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging

class Global_Controls(GUI_Helper):
    _parent: Base_GUI
    def __init__(self, parent: Base_GUI, stack_controls: bool):
        super().__init__(parent, None, parent._logger)

        self._logging_helper = parent._logging_helper
        self._i2c_controller = parent._i2c_controller
        self._stack_controls = stack_controls

    def prepare_display(self, element: tk.Tk, col, row):
        self._frame = ttk.Frame(element)
        self._frame.grid(column=col, row=row, sticky=(tk.N, tk.W, tk.E, tk.S))

        self._control_frame = ttk.Frame(self._frame)
        self._control_frame.grid(column=100, row=100, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10,20))
        self._control_frame.rowconfigure(0, weight=1)
        self._control_frame.rowconfigure(3000, weight=1)

        read_col = 100
        read_row = 100
        read_pad = (0,10)
        write_col = 200
        write_row = 100
        write_pad = (0,10)
        logging_frame = self._frame
        logging_col = 2000
        logging_row = 100
        logging_pad = (10,10)
        extra_pad = (0,0)

        if self._stack_controls:
            write_pad = (10,10)
            read_pad = write_pad
            logging_pad = write_pad
            write_col = read_col
            logging_col = read_col
            write_row = read_row + 100
            logging_row = read_row + 200
            logging_frame = self._control_frame
            extra_pad = (0,20)

        self._read_button = ttk.Button(
            self._control_frame,
            text="Read All",
            command=self._parent.read_all,
            state='disabled',
        )
        self._read_button.grid(column=read_col, row=read_row, sticky=(tk.W, tk.E), padx=read_pad)

        self._write_button = ttk.Button(
            self._control_frame,
            text="Write All",
            command=self._parent.write_all,
            state='disabled',
        )
        self._write_button.grid(column=write_col, row=write_row, sticky=(tk.W, tk.E), padx=write_pad)

        if hasattr(self._parent, "extra_global_controls"):
            self._frame.columnconfigure(200, weight=1)
            self._parent.extra_global_controls(self._frame, 200, 100, extra_pad)

        self._logging_button = ttk.Button(logging_frame, text="Logging", command=self._logging_helper.display_logging)
        self._logging_button.grid(column=logging_col, row=logging_row, sticky=(tk.W, tk.E), padx=logging_pad)

        self._i2c_controller.register_connection_callback(self._connection_update)

    def _connection_update(self, value):
        if value:
            if hasattr(self, "_read_button"):
                self._read_button.config(state="normal")
                self._write_button.config(state="normal")
        else:
            if hasattr(self, "_read_button"):
                self._read_button.config(state="disabled")
                self._write_button.config(state="disabled")

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

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging

class Status_Display(GUI_Helper):
    _red_col = '#ff0000'
    _orange_col = '#f0c010'
    _yellow_col = '#f0e000'
    _green_col = '#00ff00'
    _black_col = '#000000'
    _white_col = '#ffffff'

    def __init__(self, parent: Base_GUI, max_len: int = 100):
        super().__init__(parent, None, parent._logger)

        self._connection_status_var = tk.StringVar()
        self._connection_status_var.set("Not Connected")

        self._local_status_var = tk.StringVar()
        self._local_status_var.set("Unknown")

        self._message_var = tk.StringVar()

        self._max_len = max_len

    @property
    def connection_status(self):
        return self._connection_status_var.get()

    @connection_status.setter
    def connection_status(self, value):
        if value not in ["Not Connected", "Connected", "Error"]:
            raise ValueError("Invalid connection status was attempted to be set: \"{}\"".format(value))

        if hasattr(self, "_connection_status_label"):
            if value == "Connected":
                self._connection_status_label.config(background = self._green_col, foreground = self._black_col)
                #if self._connection_status_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._connection_status_label.config(foreground = self._green_col)
            elif value == "Error":
                self._connection_status_label.config(background = self._red_col, foreground = self._black_col)
                #if self._connection_status_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._connection_status_label.config(foreground = self._red_col)
            else:
                self._connection_status_label.config(background = self._yellow_col, foreground = self._black_col)
                #if self._connection_status_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._connection_status_label.config(foreground = self._yellow_col)

        self._connection_status_var.set(value)

    @property
    def local_status(self):
        return self._local_status_var.get()

    @local_status.setter
    def local_status(self, value):
        if value not in ["Unknown", "Modified", "Unmodified", "Error"]:
            raise ValueError("Invalid local status was attempted to be set: \"{}\"".format(value))

        if hasattr(self, "_local_status_label"):
            if value == "Unmodified":
                self._local_status_label.config(background = self._green_col, foreground = self._black_col)
                #if self._local_status_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._local_status_label.config(background = '', foreground = self._green_col)
            elif value == "Error":
                self._local_status_label.config(background = self._red_col, foreground = self._black_col)
                #if self._local_status_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._local_status_label.config(background = '', foreground = self._red_col)
            elif value == "Unknown":
                self._local_status_label.config(background = self._orange_col, foreground = self._black_col)
                #if self._local_status_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._local_status_label.config(background = '', foreground = self._orange_col)
            else:  # Modified
                self._local_status_label.config(background = self._red_col, foreground = self._black_col)
                #if self._local_status_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._local_status_label.config(background = '', foreground = self._red_col)


        self._local_status_var.set(value)

    @property
    def last_message(self):
        return self._message_var.get()

    def display_progress(self, message, percentage):
        self.send_message("")  # Clear the bar so we have space

        if not hasattr(self, "_progress") or self._progress is None:
            self._progress_label = ttk.Label(self._frame, text=message)
            self._progress_label.grid(column=249, row=100, sticky=(tk.W, tk.E))
            self._progress = ttk.Progressbar(self._frame, mode='determinate', length='300')
            self._progress.grid(column=250, row=100, sticky=(tk.W, tk.E), padx=(0,15))

        self._progress_label.config(text=message)
        self._progress['value'] = int(percentage)

    def clear_progress(self):
        if hasattr(self, "_progress") and self._progress is not None:
            self._progress.destroy()
            self._progress_label.destroy()

            self._progress = None

    def prepare_display(self, element: tk.Tk, col, row):
        self._frame = ttk.Frame(element)
        self._style = ttk.Style(self._frame)
        self._frame.grid(column=col, row=row, sticky=(tk.N, tk.W, tk.E, tk.S))

        self._connection_status_title = ttk.Label(self._frame, text="I2C Bus:")
        self._connection_status_title.grid(column=100, row=100, sticky=(tk.W, tk.E))
        self._connection_status_label = ttk.Label(self._frame, textvariable=self._connection_status_var)
        self._connection_status_label.grid(column=101, row=100, sticky=(tk.W, tk.E), padx=(0,15))

        self._local_status_title = ttk.Label(self._frame, text="Status:")
        self._local_status_title.grid(column=200, row=100, sticky=(tk.W, tk.E))
        self._local_status_label = ttk.Label(self._frame, textvariable=self._local_status_var)
        self._local_status_label.grid(column=201, row=100, sticky=(tk.W, tk.E), padx=(0,15))

        self._message_label = ttk.Label(self._frame, textvariable=self._message_var)
        self._message_label.grid(column=300, row=100, sticky=tk.E)
        self._frame.columnconfigure(300, weight=1)

        self.connection_status = self.connection_status
        self.local_status = self.local_status

    def send_message(self, message: str, status:str = "Message"):
        if status == "Error":
            self._logger.warn("Error Message: {}".format(message))
        else:
            self._logger.info("Message: {}".format(message))

        if hasattr(self, "_message_label"):
            if status == "Error":
                self._message_label.config(background = self._red_col, foreground = self._black_col)
                #if self._message_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._message_label.config(foreground = self._red_col)
            elif status == "Warning":
                self._message_label.config(background = self._orange_col, foreground = self._black_col)
                #if self._message_label.cget('background') == '':
                if self._style.theme_use() == 'aqua':
                    self._message_label.config(foreground = self._orange_col)
            else:
                self._message_label.config(background = '', foreground = '')

        if len(message) > self._max_len:
            message = message[:self._max_len - 3] + " ⋯"  # "…"
        self._message_var.set(message)
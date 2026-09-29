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

from .base_gui import Base_GUI

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging

import importlib.resources
from PIL import ImageTk, Image

from tkinter import filedialog as tkfd

i2c_conf_extension = "i2c_conf"

class AD5593R_GUI(Base_GUI):
    _config_filetypes = (
        ('I2C config files', '*.'+i2c_conf_extension),
        ('All files', '*.*')
    )
    _red_col = '#c00000'
    _green_col = '#00c000'

    def __init__(self, root: tk.Tk, logger: logging.Logger):
        self._valid_i2c_address = False

        super().__init__("AD5593R I2C GUI", root, logger)

    def _load_config(self):
        if not hasattr(self, "_chip") or self._chip is None:
            return

        filename = tkfd.askopenfilename(
            parent=self._parent,
            title='Load I2C Config',
            initialdir='./',
            filetypes=self._config_filetypes,
        )

        if filename is None or filename == "":
            return

        self._logger.trace("Loading file: {}".format(filename))

        self._chip.load_config(filename)

    def _save_config(self):
        if not hasattr(self, "_chip") or self._chip is None:
            return

        filename = tkfd.asksaveasfilename(
            parent=self._parent,
            title='Save I2C Config',
            initialdir='./',
            initialfile='ad5593r.'+i2c_conf_extension,
            defaultextension=i2c_conf_extension,
            filetypes=[('I2C config files', '*.'+i2c_conf_extension)],  # TODO: Not sure about this parameter...
        )

        if filename is None or filename == "":
            return

        self._logger.trace("Saving file: {}".format(filename))

        self._chip.save_config(filename)

    def _reset_config(self):
        if not hasattr(self, "_chip") or self._chip is None:
            return

        self.send_message("Resetting current chip configuration to default values")
        self._chip.reset_config()

    def _revert_config(self):
        if not hasattr(self, "_chip") or self._chip is None:
            return

        self.send_message("Reverting current chip configuration to last read values")
        self._chip.revert_config()

    def _file_menu(self, menubar: tk.Menu):
        self._filemenu = tk.Menu(menubar, name='file')

        self._filemenu.add_command(label='Load Chip Config', command=self._load_config, state='disabled')
        self._filemenu.add_command(label='Save Chip Config', command=self._save_config, state='disabled')
        self._filemenu.add_separator()
        self._filemenu.add_command(label='Reset Chip Config', command=self._reset_config, state='disabled')
        self._filemenu.add_command(label='Revert Chip Config', command=self._revert_config, state='disabled')

        menubar.add_cascade(menu=self._filemenu, label='File')

#    def _about_contents(self, element: tk.Tk, column: int, row: int):
#        self._about_img = ImageTk.PhotoImage(Image.open(importlib.resources.open_binary("i2c_gui.static", "ETROC2_Emulator.png")))
#        self._about_img_label = tk.Label(element, image = self._about_img)
#        self._about_img_label.grid(column=column, row=row, sticky='')
#        element.rowconfigure(row, weight=1)
#
#        self._about_info_label = tk.Label(element, justify=tk.LEFT, wraplength=450, text="The ETROC2 I2C GUI was developed to read and write I2C registers from a connected ETROC2 device using a USB-ISS serial adapter. The code was developed and tested using the ETROC2 Emulator")
#        self._about_info_label.grid(column=column, row=row + 100, sticky='')

    def _fill_notebook(self):
        from .chips import AD5593R_Chip
        self._chip = AD5593R_Chip(parent=self, i2c_controller=self._i2c_controller)

        self._full_chip_display(self._chip)

    def _connection_update(self, value):
        super()._connection_update(value)
        if value:
            if hasattr(self, "_i2c_address_entry"):
                self._i2c_address_entry.config(state='normal')
                self.check_i2c_address()
            if hasattr(self, "_filemenu"):
                self._filemenu.entryconfigure('Load Chip Config', state='normal')
                self._filemenu.entryconfigure('Save Chip Config', state='normal')
                self._filemenu.entryconfigure('Reset Chip Config', state='normal')
                self._filemenu.entryconfigure('Revert Chip Config', state='normal')
        else:
            if hasattr(self, "_i2c_address_entry"):
                self._i2c_address_entry.config(state='disabled')
                self._chip_i2c_status_var.set("")
                self._valid_i2c_address = False
            if hasattr(self, "_filemenu"):
                self._filemenu.entryconfigure('Load Chip Config', state='disabled')
                self._filemenu.entryconfigure('Save Chip Config', state='disabled')
                self._filemenu.entryconfigure('Reset Chip Config', state='disabled')
                self._filemenu.entryconfigure('Revert Chip Config', state='disabled')

    def extra_global_controls(self, element: tk.Tk, column: int, row: int, extra_pad: tuple[int, int] = (0,0)):
        self._frame_extra_global = ttk.Frame(element)
        self._frame_extra_global.grid(column=column, row=row, sticky=(tk.W, tk.E), padx=extra_pad)

        self._extra_i2c_label = ttk.Label(self._frame_extra_global, text="I2C Address:")
        self._extra_i2c_label.grid(column=100, row=100)

        self._chip_i2c_address_var = tk.StringVar()
        self._chip_i2c_address_var.set("0x10")
        self._i2c_address_entry = ttk.Entry(self._frame_extra_global, textvariable=self._chip_i2c_address_var, width=5, state='disabled')
        self._i2c_address_entry.grid(column=101, row=100, sticky=(tk.W, tk.E))

        from .functions import validate_i2c_address
        self._i2c_validate_cmd = (self._frame.register(validate_i2c_address), '%P')
        self._i2c_invalid_cmd  = (self._frame.register(self.invalid_i2c_address), '%P')
        self._i2c_address_entry.config(validate='key', validatecommand=self._i2c_validate_cmd, invalidcommand=self._i2c_invalid_cmd)
        self._chip_i2c_address_var.trace('w', self.check_i2c_address)

        self._chip_i2c_status_var = tk.StringVar()
        self._chip_i2c_status_var.set("")
        self._i2c_status_label = ttk.Label(self._frame_extra_global, textvariable=self._chip_i2c_status_var)
        self._i2c_status_label.grid(column=200, row=100, padx=(15,25))

    def check_i2c_address(self, var=None, index=None, mode=None):
        address = self._chip_i2c_address_var.get()
        if address == "0x" or address == "":
            address = "0x0"
        else:
            address = hex(int(address, 0))

        if self._i2c_controller.check_i2c_device(address):
            self._i2c_status_label.config(foreground=self._green_col)
            self._chip_i2c_status_var.set("(Available)")
            self._chip.config_i2c_address(int(address, 16))
            self._valid_i2c_address = True
        else:
            self._i2c_status_label.config(foreground=self._red_col)
            self._chip_i2c_status_var.set("(Not available)")
            self._chip.config_i2c_address(None)
            self._valid_i2c_address = False

    def read_all(self):
        if self._valid_i2c_address:
            self.send_message("Reading full AD5593R chip")
            self._chip.read_all()
        else:
            self.send_message("Unable to read full AD5593R chip", "Error")

    def write_all(self):
        if self._valid_i2c_address:
            self.send_message("Writing full AD5593R chip")
            if not self._chip.write_all(self._chip.enable_readback):
                self.send_message("Failed writing the full chip, one or more address spaces were not written to.", "Error")
        else:
            self.send_message("Unable to write full AD5593R chip", "Error")

    def set_enable_readback(self, value):
        self._chip.enable_readback = value
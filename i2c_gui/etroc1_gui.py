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

class ETROC1_GUI(Base_GUI):
    _config_filetypes = (
        ('I2C config files', '*.'+i2c_conf_extension),
        ('All files', '*.*')
    )
    _red_col = '#c00000'
    _green_col = '#00c000'
    _orange_col = '#f0c010'

    def __init__(self, root: tk.Tk, logger: logging.Logger):
        self._valid_i2c_address_a = False
        self._valid_i2c_address_b = False
        self._valid_i2c_address_full_pixel = False
        self._valid_i2c_address_tdc_test = False

        super().__init__("ETROC1 I2C GUI", root, logger, stack_global_controls=True)

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
            initialfile='etroc1.'+i2c_conf_extension,
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

    def _about_contents(self, element: tk.Tk, column: int, row: int):
        self._about_img = ImageTk.PhotoImage(Image.open(importlib.resources.open_binary("i2c_gui.static", "ETROC1.png")))
        self._about_img_label = tk.Label(element, image = self._about_img)
        self._about_img_label.grid(column=column, row=row, sticky='')
        element.rowconfigure(row, weight=1)

        self._about_info_label = tk.Label(element, justify=tk.LEFT, wraplength=450, text="The ETROC1 I2C GUI was developed to read and write I2C registers from a connected ETROC1 device using a USB-ISS serial adapter. The code was developed and tested using a FSxx board and during a testbeam with an ETROC1 telescope")
        self._about_info_label.grid(column=column, row=row + 100, sticky='')

    def _fill_notebook(self):
        from .chips import ETROC1_Chip
        self._chip = ETROC1_Chip(parent=self, i2c_controller=self._i2c_controller)

        self._full_chip_display(self._chip)

    def _connection_update(self, value):
        super()._connection_update(value)
        if value:
            if hasattr(self, "_reg_a_frame"):
                self._reg_a_address_1_checkbox.config(state='normal')
                self._reg_a_address_0_checkbox.config(state='normal')
                self._reg_b_address_1_checkbox.config(state='normal')
                self._reg_b_address_0_checkbox.config(state='normal')
                self._reg_full_pixel_check_button.config(state='normal')
                self._reg_tdc_address_0_checkbox.config(state='normal')
                self.check_i2c_address_a()
                self.check_i2c_address_b()
                self.check_i2c_address_full_pixel()
                self.check_i2c_address_tdc()
            if hasattr(self, "_filemenu"):
                self._filemenu.entryconfigure('Load Chip Config', state='normal')
                self._filemenu.entryconfigure('Save Chip Config', state='normal')
                self._filemenu.entryconfigure('Reset Chip Config', state='normal')
                self._filemenu.entryconfigure('Revert Chip Config', state='normal')
        else:
            if hasattr(self, "_reg_a_frame"):
                self._reg_a_address_1_checkbox.config(state='disabled')
                self._reg_a_address_0_checkbox.config(state='disabled')
                self._reg_b_address_1_checkbox.config(state='disabled')
                self._reg_b_address_0_checkbox.config(state='disabled')
                self._reg_full_pixel_check_button.config(state='disabled')
                self._reg_tdc_address_0_checkbox.config(state='disabled')
                self._reg_a_status_var.set("Unknown")
                self._reg_b_status_var.set("Unknown")
                self._reg_full_pixel_status_var.set("Unknown")
                self._reg_tdc_status_var.set("Unknown")
                self._reg_a_status_label.config(foreground=self._orange_col)
                self._reg_b_status_label.config(foreground=self._orange_col)
                self._reg_full_pixel_status_label.config(foreground=self._orange_col)
                self._reg_tdc_status_label.config(foreground=self._orange_col)
                self._valid_i2c_address_a = False
                self._valid_i2c_address_b = False
                self._valid_i2c_address_full_pixel = False
                self._valid_i2c_address_tdc_test = False
            if hasattr(self, "_filemenu"):
                self._filemenu.entryconfigure('Load Chip Config', state='disabled')
                self._filemenu.entryconfigure('Save Chip Config', state='disabled')
                self._filemenu.entryconfigure('Reset Chip Config', state='disabled')
                self._filemenu.entryconfigure('Revert Chip Config', state='disabled')

    def extra_global_controls(self, element: tk.Tk, column: int, row: int, extra_pad: tuple[int, int] = (0,0)):
        self._frame_extra_global = ttk.LabelFrame(element, text="I2C Addresses")
        self._frame_extra_global.grid(column=column, row=row, sticky=(tk.W, tk.E), padx=extra_pad)

        reg_a_col = 100
        reg_b_col = 200
        reg_pix_col = 300
        reg_tdc_col = 400
        # Set up main columns to have specific widths
        self._frame_extra_global.columnconfigure(reg_a_col, weight=1)
        self._frame_extra_global.columnconfigure(reg_b_col, weight=1)
        self._frame_extra_global.columnconfigure(reg_pix_col, weight=1)
        self._frame_extra_global.columnconfigure(reg_tdc_col, weight=1)

        ## REG_A Frame
        self._reg_a_frame = ttk.LabelFrame(self._frame_extra_global, text="REG_A")
        self._reg_a_frame.grid(column=reg_a_col, row=100, sticky=(tk.W, tk.E, tk.S, tk.N), padx=2)
        self._reg_a_frame.columnconfigure(0, weight=1)
        self._reg_a_frame.columnconfigure(200, weight=1)

        self._reg_a_display_var = tk.StringVar(value="0b00000xx")
        self._reg_a_display_label = ttk.Label(self._reg_a_frame, textvariable=self._reg_a_display_var)
        self._reg_a_display_label.grid(column=100, row=0)

        self._reg_a_frame.rowconfigure(100, weight=1)
        self._reg_a_inner_frame = ttk.Frame(self._reg_a_frame)
        self._reg_a_inner_frame.grid(column=100, row=100)

        self._reg_a_address_1_var = tk.BooleanVar(value="0")
        self._reg_a_address_1_checkbox = ttk.Checkbutton(self._reg_a_inner_frame, variable=self._reg_a_address_1_var, text="A1", state='disabled')
        self._reg_a_address_1_checkbox.grid(column=100, row=100, padx=(0, 10))
        self._reg_a_address_1_var.trace('w', self.check_i2c_address_a)

        self._reg_a_address_0_var = tk.BooleanVar(value="0")
        self._reg_a_address_0_checkbox = ttk.Checkbutton(self._reg_a_inner_frame, variable=self._reg_a_address_0_var, text="A0", state='disabled')
        self._reg_a_address_0_checkbox.grid(column=200, row=100)
        self._reg_a_address_0_var.trace('w', self.check_i2c_address_a)

        self._reg_a_status_var = tk.StringVar(value="Unknown")
        self._reg_a_status_label = ttk.Label(self._reg_a_frame, textvariable=self._reg_a_status_var)
        self._reg_a_status_label.grid(column=100, row=200)
        self._reg_a_status_label.config(foreground=self._orange_col)

        ## REG_B Frame
        self._reg_b_frame = ttk.LabelFrame(self._frame_extra_global, text="REG_B")
        self._reg_b_frame.grid(column=reg_b_col, row=100, sticky=(tk.W, tk.E, tk.S, tk.N), padx=2)
        self._reg_b_frame.columnconfigure(0, weight=1)
        self._reg_b_frame.columnconfigure(200, weight=1)

        self._reg_b_display_var = tk.StringVar(value="0b11111xx")
        self._reg_b_display_label = ttk.Label(self._reg_b_frame, textvariable=self._reg_b_display_var)
        self._reg_b_display_label.grid(column=100, row=0)

        self._reg_b_frame.rowconfigure(100, weight=1)
        self._reg_b_inner_frame = ttk.Frame(self._reg_b_frame)
        self._reg_b_inner_frame.grid(column=100, row=100)

        self._reg_b_address_1_var = tk.BooleanVar(value="0")
        self._reg_b_address_1_checkbox = ttk.Checkbutton(self._reg_b_inner_frame, variable=self._reg_b_address_1_var, text="B1", state='disabled')
        self._reg_b_address_1_checkbox.grid(column=100, row=100, padx=(0, 10))
        self._reg_b_address_1_var.trace('w', self.check_i2c_address_b)

        self._reg_b_address_0_var = tk.BooleanVar(value="0")
        self._reg_b_address_0_checkbox = ttk.Checkbutton(self._reg_b_inner_frame, variable=self._reg_b_address_0_var, text="B0", state='disabled')
        self._reg_b_address_0_checkbox.grid(column=200, row=100)
        self._reg_b_address_0_var.trace('w', self.check_i2c_address_b)

        self._reg_b_status_var = tk.StringVar(value="Unknown")
        self._reg_b_status_label = ttk.Label(self._reg_b_frame, textvariable=self._reg_b_status_var)
        self._reg_b_status_label.grid(column=100, row=200)
        self._reg_b_status_label.config(foreground=self._orange_col)

        ## Full Pixel Frame
        self._reg_full_pixel_frame = ttk.LabelFrame(self._frame_extra_global, text="Full Pixel")
        self._reg_full_pixel_frame.grid(column=reg_pix_col, row=100, sticky=(tk.W, tk.E, tk.S, tk.N), padx=2)
        self._reg_full_pixel_frame.columnconfigure(0, weight=1)
        self._reg_full_pixel_frame.columnconfigure(200, weight=1)

        self._reg_full_pixel_display_var = tk.StringVar(value="0b1001110")
        self._reg_full_pixel_display_label = ttk.Label(self._reg_full_pixel_frame, textvariable=self._reg_full_pixel_display_var)
        self._reg_full_pixel_display_label.grid(column=100, row=0)

        self._reg_full_pixel_frame.rowconfigure(100, weight=1)
        self._reg_full_pixel_inner_frame = ttk.Frame(self._reg_full_pixel_frame)
        self._reg_full_pixel_inner_frame.grid(column=100, row=100)

        self._reg_full_pixel_check_button = ttk.Button(self._reg_full_pixel_inner_frame, text="Check", command=self.check_i2c_address_full_pixel, state='disabled')
        self._reg_full_pixel_check_button.grid(column=100, row=100)

        self._reg_full_pixel_status_var = tk.StringVar(value="Unknown")
        self._reg_full_pixel_status_label = ttk.Label(self._reg_full_pixel_frame, textvariable=self._reg_full_pixel_status_var)
        self._reg_full_pixel_status_label.grid(column=100, row=200)
        self._reg_full_pixel_status_label.config(foreground=self._orange_col)

        ## TDC Frame
        self._reg_tdc_frame = ttk.LabelFrame(self._frame_extra_global, text="TDC Test Block")
        self._reg_tdc_frame.grid(column=reg_tdc_col, row=100, sticky=(tk.W, tk.E, tk.S, tk.N), padx=2)
        self._reg_tdc_frame.columnconfigure(0, weight=1)
        self._reg_tdc_frame.columnconfigure(200, weight=1)

        self._reg_tdc_display_var = tk.StringVar(value="0b010001x")
        self._reg_tdc_display_label = ttk.Label(self._reg_tdc_frame, textvariable=self._reg_tdc_display_var)
        self._reg_tdc_display_label.grid(column=100, row=0)

        self._reg_tdc_frame.rowconfigure(100, weight=1)
        self._reg_tdc_inner_frame = ttk.Frame(self._reg_tdc_frame)
        self._reg_tdc_inner_frame.grid(column=100, row=100)

        self._reg_tdc_address_0_var = tk.BooleanVar(value="0")
        self._reg_tdc_address_0_checkbox = ttk.Checkbutton(self._reg_tdc_inner_frame, variable=self._reg_tdc_address_0_var, text="bit0", state='disabled')
        self._reg_tdc_address_0_checkbox.grid(column=100, row=100)
        self._reg_tdc_address_0_var.trace('w', self.check_i2c_address_tdc)

        self._reg_tdc_status_var = tk.StringVar(value="Unknown")
        self._reg_tdc_status_label = ttk.Label(self._reg_tdc_frame, textvariable=self._reg_tdc_status_var)
        self._reg_tdc_status_label.grid(column=100, row=200)
        self._reg_tdc_status_label.config(foreground=self._orange_col)

    def check_i2c_address_a(self, var=None, index=None, mode=None):
        bit_1 = self._reg_a_address_1_var.get()
        bit_0 = self._reg_a_address_0_var.get()

        if bit_0:
            bit_0 = "1"
        else:
            bit_0 = "0"
        if bit_1:
            bit_1 = "1"
        else:
            bit_1 = "0"

        address = "0b00000{}{}".format(bit_1, bit_0)
        self._reg_a_display_var.set(address)

        if self._i2c_controller.check_i2c_device(address):
            self._reg_a_status_label.config(foreground=self._green_col)
            self._reg_a_status_var.set("Available")
            self._chip.config_i2c_address_a(int(address, 0))
            self._valid_i2c_address_a = True
        else:
            self._reg_a_status_label.config(foreground=self._red_col)
            self._reg_a_status_var.set("Not available")
            self._chip.config_i2c_address_a(None)
            self._valid_i2c_address_a = False

    def check_i2c_address_b(self, var=None, index=None, mode=None):
        bit_1 = self._reg_b_address_1_var.get()
        bit_0 = self._reg_b_address_0_var.get()

        if bit_0:
            bit_0 = "1"
        else:
            bit_0 = "0"
        if bit_1:
            bit_1 = "1"
        else:
            bit_1 = "0"

        address = "0b11111{}{}".format(bit_1, bit_0)
        self._reg_b_display_var.set(address)

        if self._i2c_controller.check_i2c_device(address):
            self._reg_b_status_label.config(foreground=self._green_col)
            self._reg_b_status_var.set("Available")
            self._chip.config_i2c_address_b(int(address, 0))
            self._valid_i2c_address_b = True
        else:
            self._reg_b_status_label.config(foreground=self._red_col)
            self._reg_b_status_var.set("Not available")
            self._chip.config_i2c_address_b(None)
            self._valid_i2c_address_b = False

    def check_i2c_address_full_pixel(self, var=None, index=None, mode=None):
        address = self._reg_full_pixel_display_var.get()

        if self._i2c_controller.check_i2c_device(address):
            self._reg_full_pixel_status_label.config(foreground=self._green_col)
            self._reg_full_pixel_status_var.set("Available")
            self._chip.config_i2c_address_full_pixel(int(address, 0))
            self._valid_i2c_address_full_pixel = True
        else:
            self._reg_full_pixel_status_label.config(foreground=self._red_col)
            self._reg_full_pixel_status_var.set("Not available")
            self._chip.config_i2c_address_full_pixel(None)
            self._valid_i2c_address_full_pixel = False

    def check_i2c_address_tdc(self, var=None, index=None, mode=None):
        bit_0 = self._reg_tdc_address_0_var.get()

        if bit_0:
            bit_0 = "1"
        else:
            bit_0 = "0"

        address = "0b010001{}".format(bit_0)
        self._reg_tdc_display_var.set(address)

        if self._i2c_controller.check_i2c_device(address):
            self._reg_tdc_status_label.config(foreground=self._green_col)
            self._reg_tdc_status_var.set("Available")
            self._chip.config_i2c_address_tdc(int(address, 0))
            self._valid_i2c_address_tdc_test = True
        else:
            self._reg_tdc_status_label.config(foreground=self._red_col)
            self._reg_tdc_status_var.set("Not available")
            self._chip.config_i2c_address_tdc(None)
            self._valid_i2c_address_tdc_test = False

    def read_all(self):
        if self._valid_i2c_address_a and self._valid_i2c_address_b:
            self.send_message("Reading full ETROC1 chip")
            self._chip.read_all()
        else:
            self.send_message("Unable to read full ETROC1 chip", "Error")

    def write_all(self):
        if self._valid_i2c_address_a and self._valid_i2c_address_b:
            self.send_message("Writing full ETROC1 chip")
            self._chip.write_all(self._chip.enable_readback)
        else:
            self.send_message("Unable to write full ETROC1 chip", "Error")

    def set_enable_readback(self, value):
        self._chip.enable_readback = value
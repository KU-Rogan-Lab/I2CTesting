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

from ..gui_helper import GUI_Helper
from .base_chip import Base_Chip
from ..functions import hex_0fill

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging
import time

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
import pandas
import time

from tkinter import filedialog as tkfd

class Waveform_Sampler_Helper(GUI_Helper):
    _orange_col = '#f0c010'
    _green_col = '#08ef10'
    _black_col = '#000000'

    _parent: Base_Chip

    _control_decoded_assoc = {
        "Mode": ("sel1", ["Bypass", "VGA"]),
        "Power Mode": ("sel2", ["Single Shot", "Continuous"]),
        "Write Enable": ("sel3", ["on Chip", "off Chip"]),
    }
    def __init__(self, parent: Base_Chip):
        super().__init__(parent, None, parent._logger)
        self._is_connected = False

        self._decoded_display_vars = {}
        self._control_vars = {}
        self._control_var_updating = {}

        for control in self._control_decoded_assoc:
            var, values = self._control_decoded_assoc[control]
            self._decoded_display_vars[control] = self._parent.get_decoded_display_var("Waveform Sampler", "Config", var)
            self._control_vars[control] = tk.StringVar()
            self._control_var_updating[control] = None
            self._update_display_from_config(control)

            self._decoded_display_vars[control].trace_add('write', lambda var, index, mode, control_var=control : self._update_display_from_config(control_var, var, index, mode))
            self._control_vars[control].trace_add('write', lambda var, index, mode, control_var=control : self._update_config_from_display(control_var, var, index, mode))

        self._ws_read_en = self._parent.get_decoded_display_var("Waveform Sampler", "Config", "rd_en_I2C")
        self._ws_read_address = self._parent.get_decoded_display_var("Waveform Sampler", "Config", "rd_addr")
        self._ws_data_out = self._parent.get_decoded_display_var("Waveform Sampler", "Status", "dout")

        self._has_data = False
        self._configuration_read = False
        self._is_configured = False
        self._pll_enabled = False

    @property
    def has_data(self):
        return self._has_data

    @has_data.setter
    def has_data(self, value: bool):
        self._has_data = value

        state = "disabled"
        if value:
            state = "normal"

        if hasattr(self, "_save_raw_button"):
            self._save_raw_button.config(state=state)
        if hasattr(self, "_save_wave_button"):
            self._save_wave_button.config(state=state)

    @property
    def is_connected(self):
        return self._is_connected

    @is_connected.setter
    def is_connected(self, value: bool):
        self._is_connected = value

        state = "disabled"
        if value:
            state = "normal"
            if hasattr(self, "_status_display"):
                self._status_display.connection_status = "Connected"
        else:
            self.configuration_read = False
            self.is_configured = False
            self.pll_enabled = False
            if hasattr(self, "_status_display"):
                self._status_display.connection_status = "Not Connected"
                self._status_display.local_status = "Unknown"

        if hasattr(self, "_control_dropdowns"):
            for control_var in self._control_dropdowns:
                self._control_dropdowns[control_var].config(state=state)
        if hasattr(self, "_read_config_button"):
            self._read_config_button.config(state=state)

    @property
    def configuration_read(self):
        return self._configuration_read

    @configuration_read.setter
    def configuration_read(self, value: bool):
        self._configuration_read = value

        state = "disabled"
        if value:
            state = "normal"

        if hasattr(self, "_configure_button"):
            self._configure_button.config(state=state)
        if hasattr(self, "_pll_button"):
            self._pll_button.config(state=state)

    @property
    def is_configured(self):
        return self._is_configured

    @is_configured.setter
    def is_configured(self, value: bool):
        self._is_configured = value

        state = "disabled"
        if value and self.pll_enabled:
            state = "normal"

        if hasattr(self, "_read_button"):
            self._read_button.config(state=state)

    @property
    def pll_enabled(self):
        return self._pll_enabled

    @pll_enabled.setter
    def pll_enabled(self, value: bool):
        self._pll_enabled = value

        state = "disabled"
        if value and self.is_configured:
            state = "normal"

        if hasattr(self, "_read_button"):
            self._read_button.config(state=state)

    def _update_config_from_display(self, control_var, var=None, index=None, mode=None):
        if self._control_var_updating[control_var] is not None and self._control_var_updating[control_var] == "from config":
            return
        control_values = self._control_decoded_assoc[control_var][1]

        self._control_var_updating[control_var] = "from display"

        selected_value = self._control_vars[control_var].get()
        idx = control_values.index(selected_value)
        self._decoded_display_vars[control_var].set(idx)

        self._control_var_updating[control_var] = None

    def _update_display_from_config(self, control_var, var=None, index=None, mode=None):
        if self._control_var_updating[control_var] is not None and self._control_var_updating[control_var] == "from display":
            return
        control_values = self._control_decoded_assoc[control_var][1]

        self._control_var_updating[control_var] = "from config"

        idx = int(self._decoded_display_vars[control_var].get())
        selected_value = control_values[idx]
        self._control_vars[control_var].set(selected_value)

        self._control_var_updating[control_var] = None

    def _connection_update(self, value):
        self.is_connected = value

    def display_window(self):
        if hasattr(self, "_window"):
            self._logger.info("Waveform Sampler window already open")
            self._window.focus()
            return

        state = "disabled"
        if self.is_connected:
            state = "normal"

        self._window = tk.Toplevel(self._parent._parent._root)
        self._window.title(self._parent._parent._title + " - Waveform Sampler Monitor")
        self._window.protocol('WM_DELETE_WINDOW', self.close_window)
        self._window.columnconfigure(200, weight=1)
        self._window.rowconfigure(100, weight=1)

        self._sidebar_frame = ttk.Frame(self._window)
        self._sidebar_frame.grid(column=100, row=100, padx=5, pady=5)
        self._main_frame = ttk.Frame(self._window)
        self._main_frame.grid(column=200, row=100, padx=5, pady=5)

        self._control_frame = ttk.LabelFrame(self._sidebar_frame, text="Control")
        self._control_frame.grid(column=100, row=100, sticky=(tk.E, tk.W))
        self._control_frame.columnconfigure(0, weight=1)
        self._control_frame.columnconfigure(200, weight=1)

        self._read_config_button = ttk.Button(self._control_frame, text="Read Config", state=state)
        self._read_config_button.grid(column=110, row=90)

        self._control_labels = {}
        self._control_dropdowns = {}
        current_row = 100
        for control_var in self._control_decoded_assoc:
            values = self._control_decoded_assoc[control_var][1]

            self._control_labels[control_var] = ttk.Label(self._control_frame, text=control_var+":")
            self._control_labels[control_var].grid(column=100, row=current_row)

            self._control_dropdowns[control_var] = ttk.OptionMenu(self._control_frame, self._control_vars[control_var], self._control_vars[control_var].get(), *values)
            self._control_dropdowns[control_var].grid(column=110, row=current_row)
            self._control_dropdowns[control_var].config(state=state)

            current_row += 10

        config_state = "disabled"
        if self.configuration_read:
            config_state = "normal"

        self._configure_button = ttk.Button(self._control_frame, text="Config WS", state=config_state)
        self._configure_button.grid(column=110, row=current_row)


        self._daq_frame = ttk.LabelFrame(self._sidebar_frame, text="DAQ")
        self._daq_frame.grid(column=100, row=110)

        pll_state = config_state

        self._pll_button = ttk.Button(self._daq_frame, text="Enable PLL", state=pll_state)
        self._pll_button.grid(column=100, row=100)

        read_state = "disabled"
        if self.pll_enabled and self.is_configured:
            read_state = "normal"

        self._read_button = ttk.Button(self._daq_frame, text="Read Memory", command=self._read_memory_show_progress, state=read_state)
        self._read_button.grid(column=110, row=100)

        data_state = "disabled"
        if self.has_data:
            data_state = "normal"

        self._save_raw_button = ttk.Button(self._daq_frame, text="Save Raw", state=data_state, command=self._save_raw_data_dialog)
        self._save_raw_button.grid(column=100, row=110)

        self._save_wave_button = ttk.Button(self._daq_frame, text="Save Waveform", state=data_state, command=self._save_waveform_data_dialog)
        self._save_wave_button.grid(column=110, row=110)


        #import numpy as np
        #t = np.arange(0.0,3.0,0.01)
        #self._df = pandas.DataFrame({'t':t, 's':np.sin(2*np.pi*t), 'u':np.sin(np.pi*t)})  # Test df contents
        self._df = pandas.DataFrame()

        self._fig = Figure(figsize=(7,5), dpi=100)
        self._ax = self._fig.add_subplot(111)

        # Test plot
        #self._df.plot(x='t', y='s', ax=self._ax)
        #self._df.plot(x='t', y='u', ax=self._ax)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self._main_frame)
        self._canvas.get_tk_widget().grid(row=0, column=0)

        # Original approach, but the above seems more flexible
        #fig = df.plot(x='t', y='s').get_figure()
        #plot = FigureCanvasTkAgg(fig, master=self._main_frame)
        #plot.get_tk_widget().grid(row=0, column=0)

        self._window.update()
        self._window.minsize(self._window.winfo_width(), self._window.winfo_height())

    def _show_progress_diag(self):
        self._dialog = tk.Toplevel(self._window)
        # Idea from https://tkdocs.com/tutorial/windows.html; but I have not been able to get the combination of properties I want
        #self._dialog.tk.call("::tk::unsupported::MacWindowStyle", "style", self._dialog._w, "help")
        self._dialog.title("WS Read Memory Progress")
        self._read_early_stop = False

        self._dialog_info_label = ttk.Label(self._dialog, text="Data is being read from the WS memory, please do not disconnect.")
        self._dialog_info_label.grid(column=0, row=0)

        self._dialog_inner_frame = ttk.Frame(self._dialog)
        self._dialog_inner_frame.grid(column=0, row=1)

        self._dialog_progress_label = ttk.Label(self._dialog_inner_frame, text="Progress:")
        self._dialog_progress_label.grid(column=0, row=0)
        self._dialog_progress = ttk.Progressbar(self._dialog_inner_frame, mode='determinate', length='300')
        self._dialog_progress.grid(column=1, row=0)

        self._dialog_stop_button = ttk.Button(self._dialog, text="Stop", command=self._trigger_early_stop)
        self._dialog_stop_button.grid(column=0, row=2)

        self._dialog.protocol("WM_DELETE_WINDOW", self._trigger_early_stop)  # Redirect the close dialog
        self._dialog.transient(self._window)   # dialog window is related to main window
        self._dialog.wait_visibility() # can't grab until window appears, so we wait
        self._dialog.grab_set()        # ensure all input goes to our window
        #self._dialog.wait_window()     # block until window is destroyed / stops code here

    def _trigger_early_stop(self):
        self._read_early_stop = True

    def _delete_progress_diag(self):
        self._dialog.grab_release()
        self._dialog.destroy()
        del self._dialog_progress

    def _read_memory_show_progress(self):
        self._ax.clear()

        self._show_progress_diag()
        self.read_memory()
        self._delete_progress_diag()

        #print(self._df)
        self._df.plot(x='Time [ns]', y='Dout', ax=self._ax)
        self._df.plot(x='Time [ns]', y='Dout_S1', ax=self._ax)
        self._df.plot(x='Time [ns]', y='Dout_S2', ax=self._ax)
        self._canvas.draw()

    def read_memory(self):
        # Enable reading data from WS (change the value, then write it):
        self._ws_read_en.set(1)
        self._parent.write_decoded_value("Waveform Sampler", "Config", "rd_en_I2C", no_message=True)

        # For loop to read data from WS
        max_steps = 1024  # Size of the data buffer inside the WS
        lastUpdateTime = time.time_ns()
        base_data = []
        coeff=0.04/5*8.5  # This number comes from the example script in the manual
        time_coeff = 1/2.56  # 2.56 GHz WS frequency
        for address in range(max_steps):
            self._ws_read_address.set(hex_0fill(address, 10))
            self._parent.write_decoded_value("Waveform Sampler", "Config", "rd_addr", no_message=True)

            self._parent.read_decoded_value("Waveform Sampler", "Status", "dout", no_message=True)
            data = self._ws_data_out.get()

            #if time_idx == 1:
            #    data = hex_0fill(int(data, 0) + 8192, 14)

            binary_data = bin(int(data, 0))[2:].zfill(14)  # because dout is 14 bits long
            Dout_S1 = int('0b'+binary_data[1:7], 0)
            Dout_S2 = int(binary_data[ 7]) * 24 + \
                      int(binary_data[ 8]) * 16 + \
                      int(binary_data[ 9]) * 10 + \
                      int(binary_data[10]) *  6 + \
                      int(binary_data[11]) *  4 + \
                      int(binary_data[12]) *  2 + \
                      int(binary_data[13])

            base_data.append(
                {
                    "Data Address": address,
                    "Data": int(data, 0),
                    "Raw Data": bin(int(data, 0))[2:].zfill(14),
                    "pointer": int(binary_data[0]),
                    "Dout_S1": Dout_S1,
                    "Dout_S2": Dout_S2,
                    "Dout": Dout_S1 - coeff * Dout_S2,
                }
            )

            thisTime = time.time_ns()
            if thisTime - lastUpdateTime > 0.3 * 10**9:
                lastUpdateTime = thisTime
                if hasattr(self, "_dialog_progress"):
                    self._dialog_progress['value'] = int(address*100.0/max_steps)
                if hasattr(self, "_window"):
                    self._window.update()

            if self._read_early_stop:
                break

        self._df = pandas.DataFrame(base_data)

        df_length = len(self._df)
        channels = 8

        df_per_ch : list[pandas.DataFrame] = []
        for ch in range(channels):
            df_per_ch += [self._df.iloc[int(ch * df_length/channels):int((ch + 1) * df_length/channels)].copy()]
            df_per_ch[ch].reset_index(inplace = True, drop = True)

        pointer_idx = df_per_ch[-1]["pointer"].loc[df_per_ch[-1]["pointer"] != 0].index  # TODO: Maybe add a search of the pointer in any channel, not just the last one
        if len(pointer_idx) != 0:  # If pointer found, reorder the data
            pointer_idx = pointer_idx[0]
            new_idx = list(set(range(len(df_per_ch[-1]))).difference(range(pointer_idx+1))) + list(range(pointer_idx+1))
            for ch in range(channels):
                df_per_ch[ch] = df_per_ch[ch].iloc[new_idx].reset_index(drop = True)  # Fix indexes after reordering

        # interleave the channels
        for ch in range(channels):
            df_per_ch[ch]["Time Index"] = df_per_ch[ch].index * channels + (channels - 1 - ch)  # Flip the order of the channels in the interleave...
            df_per_ch[ch]["Channel"] = ch + 1

        # Actually put it all together in one dataframe and sort the data correctly
        self._df = pandas.concat(df_per_ch)
        self._df["Time [ns]"] = self._df["Time Index"] * time_coeff
        self._df.set_index('Time Index', inplace=True)
        self._df.sort_index(inplace=True)

        # Disable reading data from WS:
        self._ws_read_en.set(0)
        self._parent.write_decoded_value("Waveform Sampler", "Config", "rd_en_I2C", no_message=True)

        self.has_data = True

    def _save_raw_data_dialog(self):
        raw_extension = "csv"

        filename = tkfd.asksaveasfilename(
            parent=self._window,
            title='Save WS Raw Data',
            initialdir='./',
            initialfile='ws_raw_data.'+raw_extension,
            defaultextension=raw_extension,
            filetypes=[('CSV files', '*.'+raw_extension)],  # TODO: Not sure about this parameter...
        )

        if filename is None or filename == "":
            return

        self._logger.trace("Saving WS Raw data to file: {}".format(filename))

        self.save_raw_data(filename)

    def save_raw_data(self, filename):  # data is saved as a CSV
        self._df.to_csv(filename, columns=["Raw Data"])

    def _save_waveform_data_dialog(self):
        raw_extension = "csv"

        filename = tkfd.asksaveasfilename(
            parent=self._window,
            title='Save WS Waveform',
            initialdir='./',
            initialfile='ws_waveform.'+raw_extension,
            defaultextension=raw_extension,
            filetypes=[('CSV files', '*.'+raw_extension)],  # TODO: Not sure about this parameter...
        )

        if filename is None or filename == "":
            return

        self._logger.trace("Saving WS waveform to file: {}".format(filename))

        self.save_waveform_data(filename)

    def save_waveform_data(self, filename):  # data is saved as a CSV
        self._df.to_csv(filename, columns=["Time [ns]", "Dout"], index=False)

    def close_window(self):
        if not hasattr(self, "_window"):
            self._logger.info("Waveform Sampler window does not exist")
            return

        self.is_logging = False

        self._window.destroy()
        del self._window

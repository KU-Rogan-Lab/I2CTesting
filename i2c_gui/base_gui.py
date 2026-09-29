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
from .chips.base_chip import Base_Chip

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging

import importlib.resources
from PIL import ImageTk, Image

from tkinter import filedialog as tkfd
from tkinter.messagebox import showinfo

class Base_GUI(GUI_Helper):
    def __init__(self, title, root: tk.Tk, logger: logging.Logger, do_status: bool = True, do_global_controls: bool = True, stack_global_controls: bool = False):
        super().__init__(None, ttk.Frame(root, padding="5 5 5 5"), logger)
        self._root = root
        self._title = title
        self._canvases = []
        self._min_internal_width = 0
        self._min_internal_height = 300

        from . import __platform__
        if __platform__ not in ["x11", "win32", "aqua"]:
            raise RuntimeError("Unknown platform: {}".format(__platform__))

        self._root.protocol('WM_DELETE_WINDOW', self._close_window)  # In order that we can control shutdown and safely close anything if needed
        self._root.title(self._title)
        self._root.columnconfigure(100, weight=1)  # Make the row and column expand to use the full space
        self._root.rowconfigure(100, weight=1)

        self._frame.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))  # Position the base frame
        self._frame.columnconfigure(100, weight=1)

        from .logging import Logging_Helper
        self._logging_helper = Logging_Helper(self)

        from .about import About_Helper
        self._about_helper = About_Helper(self)

        self._build_menu()

        from .connection_controller import Connection_Controller
        self._i2c_controller = Connection_Controller(self)
        self._i2c_controller.prepare_display(self._frame, 100, 100)
        self._i2c_controller.register_connection_callback(self._connection_update)

        self._frame.rowconfigure(200, weight=1)  # Main content is placed in this row, so it should expand to adjust to window size
        self._notebook = ttk.Notebook(self._frame)
        self._notebook.grid(column=100, row=200, sticky=(tk.N, tk.W, tk.E, tk.S))

        self._fill_notebook()

        if do_global_controls:
            from .global_controls import Global_Controls
            self._global_controls = Global_Controls(self, stack_controls=stack_global_controls)
            self._global_controls.prepare_display(self._frame, 100, 900)

        if do_status:
            from .status_display import Status_Display
            self._status_display = Status_Display(self)
            self._status_display.prepare_display(self._frame, 100, 1000)

        self._frame.update_idletasks()
        if hasattr(self, "_tab_frame_data"):
            for entry in self._tab_frame_data:
                if "canvas" not in self._tab_frame_data[entry]:
                    frame: ttk.Frame = self._tab_frame_data[entry]["frame"]
                    if frame.winfo_reqheight() > self._min_internal_height:
                        self._min_internal_height = frame.winfo_reqheight()
            for entry in self._tab_frame_data:
                if "canvas" in self._tab_frame_data[entry]:
                    canvas: tk.Canvas = self._tab_frame_data[entry]["canvas"]
                    frame: ttk.Frame = self._tab_frame_data[entry]["internal frame"]
                    scrollbar: ttk.Scrollbar = self._tab_frame_data[entry]["scrollbar"]

                    canvas.config(width=frame.winfo_reqwidth(), height=min(self._min_internal_height, frame.winfo_reqheight()))
                    canvas.config(
                        yscrollcommand=scrollbar.set,
                        scrollregion=(
                            0,
                            0,
                            frame.winfo_reqwidth(),
                            frame.winfo_reqheight()
                        )
                    )

    @property
    def is_connected(self):
        return self._i2c_controller.is_connected

    def _connection_update(self, value):
        if value:
            if hasattr(self, "_status_display"):
                self._status_display.connection_status = "Connected"
        else:
            if hasattr(self, "_status_display"):
                self._status_display.connection_status = "Not Connected"
                self._status_display.local_status = "Unknown"

    def _local_status_update(self, value):
        if hasattr(self, "_status_display"):
            if self._status_display.connection_status == "Connected":
                self._status_display.local_status = value

    def _close_window(self):
        self._i2c_controller.disconnect()
        if not hasattr(self, "_root"):
            self._logger.info("Root window does not exist")
            return

        self._root.destroy()
        del self._root

    def _build_menu(self):
        # Configure Menu
        self._root.option_add('*tearOff', tk.FALSE)

        self._menubar = tk.Menu(self._root)

        from . import __platform__

        # Create apple menu for macOS
        if __platform__ == "aqua":
            # MacOS Guidelines: https://developer.apple.com/design/human-interface-guidelines/platforms/designing-for-macos/#//apple_ref/doc/uid/20000957-CH23-SW1
            # https://developer.apple.com/design/human-interface-guidelines/components/system-experiences/the-menu-bar
            self._apple_menu = tk.Menu(self._menubar, name='apple')
            self._apple_menu.add_command(label='About ' + self._title, command=self._about_helper.display_about)
            self._apple_menu.add_separator()
            self._menubar.add_cascade(menu=self._apple_menu)

            # If a preferences window exists:
            # self._root.createcommand('tk::mac::ShowPreferences', showMyPreferencesDialog)
            self._root.createcommand('tk::mac::Quit', self._close_window)  # Handle closing from menu correctly

        # Create File menu
        if hasattr(self, "_file_menu"):
            self._file_menu(self._menubar)

        # Create Monitor menu
        self._monitor_menu(self._menubar)

        # Create Utility menu
        self._utility_menu(self._menubar)

        # Create window menu for macOS
        if __platform__ == "aqua":
            self._windowmenu = tk.Menu(self._menubar, name='window')
            self._menubar.add_cascade(menu=self._windowmenu, label='Window')

        # Create help menu
        if __platform__ == "aqua":
            self._helpmenu = tk.Menu(self._menubar, name='help')
            self._menubar.add_cascade(menu=self._helpmenu, label='Help')
            self._root.createcommand('tk::mac::ShowHelp', self._about_helper.display_about)  # For now, we will use the about menu for help since the program is simple
        # elif __platform__ == "x11":  # Linux will handle the help menu specially and place it at the end
        elif __platform__ != "aqua":
            self._helpmenu = tk.Menu(self._menubar, name='help')
            self._helpmenu.add_command(label='About ETROC I2C GUI', command=self._about_helper.display_about)
            self._menubar.add_cascade(menu=self._helpmenu, label='Help')

        # Create system menu for windows
        if __platform__ == "win32":
            self._sysmenu = tk.Menu(self._menubar, name='system')
            self._menubar.add_cascade(menu=self._sysmenu)
            # Note: This will be auto-populated, but this handle allows to add more entries to the end
            # https://tkdocs.com/tutorial/menus.html

        self._root.config(menu=self._menubar)

    def _monitor_menu(self, menubar: tk.Menu):
        self._monitormenu = tk.Menu(menubar, name='monitor')

        self._create_monitor_menu_entries(self._monitormenu)

        menubar.add_cascade(menu=self._monitormenu, label='Monitor')

    def _utility_menu(self, menubar: tk.Menu):
        self._utilitymenu = tk.Menu(menubar, name='utility')

        self._create_utility_menu_entries(self._utilitymenu)

        menubar.add_cascade(menu=self._utilitymenu, label='Utilities')

    def _create_monitor_menu_entries(self, monitormenu: tk.Menu):
        monitormenu.add_command(label='Open I2C Monitor', command=self._open_i2c_monitor)#, state='disabled')
        monitormenu.add_command(label='Open Logging Monitor', command=self._open_logging_monitor)#, state='disabled')

    def _create_utility_menu_entries(self, utilitymenu: tk.Menu):
        utilitymenu.add_command(label='Scan I2C Devices', command=self._open_i2c_scan)#, state='disabled')

    def _open_i2c_monitor(self):
        if hasattr(self, '_i2c_controller') and self._i2c_controller is not None:
            self._i2c_controller.display_i2c_window()

    def _open_logging_monitor(self):
        if hasattr(self, '_logging_helper') and self._logging_helper is not None:
            self._logging_helper.display_logging()

    def _open_i2c_scan(self):
        if hasattr(self, '_i2c_controller') and self._i2c_controller is not None:
            self._i2c_controller.display_i2c_scan_window()

    def display_progress(self, message, percentage):
        if hasattr(self, '_status_display'):
            self._status_display.display_progress(message, percentage)
        else:
            self._logger.debug("{}: Progress {}/100".format(message, int(percentage)))

    def clear_progress(self):
        if hasattr(self, '_status_display'):
            self._status_display.clear_progress()

    def send_message(self, message: str, status:str = "Message"):
        self._status_display.send_message(message=message, status=status)

    def _about_contents(self, element: tk.Tk, column: int, row: int):
        self._about_img = ImageTk.PhotoImage(Image.open(importlib.resources.open_binary("i2c_gui.static", "ETROC1.png")))
        self._about_img_label = tk.Label(element, image = self._about_img)
        self._about_img_label.grid(column=column, row=row, sticky='')
        element.rowconfigure(row, weight=1)

        self._about_info_label = tk.Label(element, justify=tk.LEFT, wraplength=450, text="The ETROC I2C GUI was developed to read and write I2C registers from a connected ETROC device using a USB-ISS serial adapter. The code was developed and tested using the ETROC2 Emulator")
        self._about_info_label.grid(column=column, row=row + 200, sticky='')

    def _fill_notebook(self):
        self._base_gui_info_frame = ttk.Frame(self._notebook)
        self._base_gui_info_frame.columnconfigure(100, weight=1)
        self._base_gui_info_frame.rowconfigure(100, weight=1)
        self.register_tab(self._base_gui_info_frame, "Base GUI Info")

        self._base_gui_info_label = ttk.Label(self._base_gui_info_frame, text="This is the default text by the Base_GUI class. The content generation function should be overriden in order to replace this text")
        self._base_gui_info_label.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

    def register_tab(self, frame, title):
        self._notebook.add(frame, text=title)

    def _full_chip_display(self, chip: Base_Chip):
        self._tab_frame_data = {}
        for tab in chip.tabs:
            frame = ttk.Frame(self._notebook)
            self._tab_frame_data[tab] = {
                "frame": frame,
            }
            self.register_tab(frame, tab)

            if chip.tab_needs_canvas(tab):
                frame.columnconfigure(100, weight=1)
                frame.rowconfigure(100, weight=1)

                canvas = tk.Canvas(frame, borderwidth=0, highlightthickness=0)
                self._tab_frame_data[tab]["canvas"] = canvas
                canvas.grid(column=100, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

                scrollbar = ttk.Scrollbar(frame, command=canvas.yview)
                self._tab_frame_data[tab]["scrollbar"] = scrollbar
                scrollbar.grid(column=101, row=100, sticky=(tk.N, tk.W, tk.E, tk.S))

                frame = ttk.Frame(canvas)
                self._tab_frame_data[tab]["internal frame"] = frame

                window = canvas.create_window(0, 0, window=frame, anchor=tk.N+tk.W)
                self._tab_frame_data[tab]["window"] = window

                canvas.bind('<Configure>', lambda event, canvas=canvas, window=window: self._update_canvas(canvas, window, event))
                frame.bind('<Enter>', lambda event, canvas=canvas: self._bind_canvas_to_mousewheel(canvas, event))
                frame.bind('<Leave>', lambda event, canvas=canvas: self._unbind_canvas_from_mousewheel(canvas, event))

            chip.build_tab(tab, frame)
        pass

    def _update_canvas(self, canvas: tk.Canvas, window: tk._CanvasItemId, event: tk.Event):
        canvas.itemconfigure(window, width=event.width)

    def _bind_canvas_to_mousewheel(self, canvas: tk.Canvas, event: tk.Event):
        canvas.bind_all("<MouseWheel>", lambda event, canvas=canvas: self._canvas_on_mousewheel(canvas, event))

    def _unbind_canvas_from_mousewheel(self, canvas: tk.Canvas, event: tk.Event):
        canvas.unbind_all("<MouseWheel>")

    def invalid_i2c_address(self, address: str):
        self.send_message("{} is an invalid I2C device address".format(address))

    def _canvas_on_mousewheel(self, canvas: tk.Canvas, event: tk.Event):
        from . import __platform__
        if __platform__ == "aqua":
            canvas.yview_scroll(int(-1*(event.delta)), "units")
        else:
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def extra_global_controls(self, element: tk.Tk, column: int, row: int, extra_pad: tuple[int, int] = (0,0)):
        pass

    def read_all(self):
        pass

    def write_all(self):
        pass

    def set_enable_readback(self, value):
        pass

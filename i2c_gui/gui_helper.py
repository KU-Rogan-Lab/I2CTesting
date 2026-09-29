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

import tkinter as tk
import logging

class GUI_Helper:
    def __init__(self, parent: 'GUI_Helper', frame: tk.Tk, logger: logging.Logger):
        self._parent = parent
        self._frame = frame
        self._logger = logger

    @property
    def is_connected(self):
        if self._parent is None:
            raise RuntimeError("You can only find if the app is connected from a stack of classes which handle the connection correctly")
        return self._parent.is_connected

    def send_message(self, message:str, status:str = "Message"):
        if self._parent is None:
            raise RuntimeError("You can only call send_message from a stack of classes which route the message correctly")
        self._parent.send_message(message=message, status=status)

    def display_progress(self, message, percentage):
        if self._parent is None:
            raise RuntimeError("You can only call display_progress from a stack of classes which route the progress correctly")
        self._parent.display_progress(message=message, percentage=percentage)

    def clear_progress(self):
        if self._parent is None:
            raise RuntimeError("You can only call clear_progress from a stack of classes which route the progress correctly")
        self._parent.clear_progress()
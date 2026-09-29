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
import logging

class ScriptHelper(GUI_Helper):
    def __init__(self, logger: logging.Logger):
        # self._root = tk.Tk()  # Needed for some of the variables to work correctly
        super().__init__("Script Helper", tk.Tk(), logger)

    def _local_status_update(self, value):
        self._logger.info("Updating local status to: {}".format(value))

    def send_message(self, message:str, status:str = "Message"):
        if status != "Message":
            self._logger.error("GUI Message of type {}: {}".format(status, message))
        else:
            self._logger.info("GUI Message of type {}: {}".format(status, message))

    def display_progress(self, message, percentage):
        self._logger.info("{}: Progress {}/100".format(message, int(percentage)))

    def clear_progress(self):
        self._logger.info("Finished progress")

    def get_all_indexed_blocks(self, indexer_info, block_name):
        indexed_blocks = {}
        for idx in range(len(indexer_info['vars'])):
            var = indexer_info['vars'][idx]
            min = indexer_info['min'][idx]
            max = indexer_info['max'][idx]

            old_indexed_blocks = indexed_blocks
            indexed_blocks = {}

            if var == "block" and min is None and max is None:
                param = block_name
                if len(old_indexed_blocks) == 0:
                    indexed_blocks[param] = {
                        'indexers': {'block': param},
                    }
                else:
                    for old in old_indexed_blocks:
                        indexed_blocks[old + ":" + param] = {}
                        indexed_blocks[old + ":" + param]['indexers'] = old_indexed_blocks[old]['indexers']
                        indexed_blocks[old + ":" + param]['indexers']['block'] = str(param)
            else:
                for val_idx in range(max - min):
                    i = min + val_idx
                    if len(old_indexed_blocks) == 0:
                        indexed_blocks[i] = {
                            'indexers': {var: i},
                        }
                    else:
                        for old in old_indexed_blocks:
                            indexed_blocks[old + ":" + str(i)] = {}
                            indexed_blocks[old + ":" + str(i)]['indexers'] = (old_indexed_blocks[old]['indexers']).copy()
                            indexed_blocks[old + ":" + str(i)]['indexers'][var] = i
        return indexed_blocks
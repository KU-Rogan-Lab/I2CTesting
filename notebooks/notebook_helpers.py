#############################################################################
# zlib License
#
# (C) 2023 Zach FLowers, Murtaza Safdari <musafdar@cern.ch>, Cristóvão Beirão da Cruz e Silva
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
#import visa
import threading
import numpy as np
import os, sys
from queue import Queue
from collections import deque
import queue
import datetime
from tqdm import tqdm
import pandas
import logging
import pickle
import matplotlib.pyplot as plt
import multiprocessing
from pathlib import Path
os.chdir(f'/home/{os.getlogin()}/ETROC2/ETROC_DAQ')
import run_script
import parser_arguments
import importlib
importlib.reload(run_script)
importlib.reload(parser_arguments)
from fnmatch import fnmatch
import scipy.stats as stats
import hist
import mplhep as hep
import subprocess
import sqlite3
plt.style.use(hep.style.CMS)
import i2c_gui
import i2c_gui.chips
from i2c_gui.usb_iss_helper import USB_ISS_Helper
from i2c_gui.fpga_eth_helper import FPGA_ETH_Helper
from i2c_gui.chips.etroc2_chip import register_decoding
from numpy import savetxt
from mpl_toolkits.axes_grid1 import make_axes_locatable
#========================================================================================#
'''
@author: Zach Flowers, Murtaza Safdari
@date: 2023-03-24
This script is composed of all the helper functions needed for I2C comms, FPGA, etc
'''
#--------------------------------------------------------------------------#

## TODO Broadcast function check

valid_power_modes = ['low', '010', '101', 'high']

class i2c_connection():
    _chips = None

    def __init__(self, port, chip_addresses, ws_addresses, chip_names, chip_fc_delays):
        self.chip_addresses = chip_addresses
        self.ws_addresses = ws_addresses
        self.chip_names = chip_names
        # 2-tuple of binary numbers represented as strings ("0","1")
        # Here "0" is the "fcClkDelayEn" and "1" is the fcDataDelayEn
        self.chip_fc_delays = chip_fc_delays
        i2c_gui.__no_connect__ = False  # Set to fake connecting to an ETROC2 device
        i2c_gui.__no_connect_type__ = "echo"  # for actually testing readback
        #i2c_gui.__no_connect_type__ = "check"  # default behaviour
        ## Logger
        log_level=30
        logging.basicConfig(format='%(asctime)s - %(levelname)s:%(name)s:%(message)s')
        logger = logging.getLogger("Script_Logger")
        self.Script_Helper = i2c_gui.ScriptHelper(logger)
        self.conn = i2c_gui.Connection_Controller(self.Script_Helper)
        self.conn.connection_type = "USB-ISS"
        self.conn.handle: USB_ISS_Helper
        self.conn.handle.port = port
        self.conn.handle.clk = 100
        self.conn.connect()
        logger.setLevel(log_level)

        self.BL_map_THCal = {}
        self.NW_map_THCal = {}
        self.BLOffset_map = {}
        self.BL_df = {}
        for chip_address in chip_addresses:
            self.BL_map_THCal[chip_address] = np.zeros((16,16))
            self.NW_map_THCal[chip_address] = np.zeros((16,16))
            self.BLOffset_map[chip_address] = np.zeros((16,16))
            self.BL_df[chip_address] = []

    # func_string is an 8-bit binary number, LSB->MSB is function 0->7
    # "0" means don't call the corr function, and vice-versa
    def config_chips(self, func_string = '00000000'):
        for chip_address, chip_name, chip_fc_delay, ws_address in zip(self.chip_addresses, self.chip_names, self.chip_fc_delays, self.ws_addresses):
            chip = self.get_chip_i2c_connection(chip_address, ws_address)
            if(int(func_string[-1])): self.pixel_check(chip_address, chip)
            if(int(func_string[-2])): self.basic_peripheral_register_check(chip_address, chip)
            if(int(func_string[-3])): self.set_chip_peripherals(chip_address, chip_fc_delay, chip)
            if(int(func_string[-4])): self.disable_all_pixels(chip_address, chip, check_broadcast=True)
            if(int(func_string[-5])): self.auto_calibration(chip_address, chip_name, chip)
            if(int(func_string[-6])):
                if(int(func_string[-4])):
                    self.auto_calibration_and_disable(chip_address, chip_name, chip, check_broadcast=True)
                else:
                    self.auto_calibration_and_disable(chip_address, chip_name, chip, check_broadcast=False)
            if(int(func_string[-7])): self.set_chip_offsets(chip_address, offset=20, chip=chip)
            if(int(func_string[-8])): self.prepare_ws_testing(chip_address, ws_address, chip)

    def __del__(self):
        self.conn.disconnect()

    #--------------------------------------------------------------------------#
    ## Useful helper functions to streamline register reading and writing
    def pixel_decoded_register_write(self, decodedRegisterName, data_to_write, chip=None, chip_address=None):
        if(chip==None and chip_address!=None):
            chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None): print("Need either a chip or chip address to access registers!")
        bit_depth = register_decoding["ETROC2"]["Register Blocks"]["Pixel Config"][decodedRegisterName]["bits"]
        handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", decodedRegisterName)
        chip.read_decoded_value("ETROC2", "Pixel Config", decodedRegisterName)
        if len(data_to_write)!=bit_depth: print("Binary data_to_write is of incorrect length for",decodedRegisterName, "with bit depth", bit_depth)
        data_hex_modified = hex(int(data_to_write, base=2))
        if(bit_depth>1): handle.set(data_hex_modified)
        elif(bit_depth==1): handle.set(data_to_write)
        else: print(decodedRegisterName, "!!!ERROR!!! Bit depth <1, how did we get here...")
        chip.write_decoded_value("ETROC2", "Pixel Config", decodedRegisterName)

    def pixel_decoded_register_read(self, decodedRegisterName, key, chip=None, chip_address=None, need_int=False):
        if(chip==None and chip_address!=None):
            chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None): print("Need either a chip or chip address to access registers!")
        handle = chip.get_decoded_indexed_var("ETROC2", f"Pixel {key}", decodedRegisterName)
        chip.read_decoded_value("ETROC2", f"Pixel {key}", decodedRegisterName)
        if(need_int): return int(handle.get(), base=16)
        else: return handle.get()

    def peripheral_decoded_register_write(self, decodedRegisterName, data_to_write, chip=None, chip_address=None):
        if(chip==None and chip_address!=None):
            chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None): print("Need either a chip or chip address to access registers!")
        bit_depth = register_decoding["ETROC2"]["Register Blocks"]["Peripheral Config"][decodedRegisterName]["bits"]
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", decodedRegisterName)
        chip.read_decoded_value("ETROC2", "Peripheral Config", decodedRegisterName)
        if len(data_to_write)!=bit_depth: print("Binary data_to_write is of incorrect length for",decodedRegisterName, "with bit depth", bit_depth)
        data_hex_modified = hex(int(data_to_write, base=2))
        if(bit_depth>1): handle.set(data_hex_modified)
        elif(bit_depth==1): handle.set(data_to_write)
        else: print(decodedRegisterName, "!!!ERROR!!! Bit depth <1, how did we get here...")
        chip.write_decoded_value("ETROC2", "Peripheral Config", decodedRegisterName)

    def peripheral_decoded_register_read(self, decodedRegisterName, key, chip=None, need_int=False, chip_address=None):
        if(chip==None and chip_address!=None):
            chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None): print("Need either a chip or chip address to access registers!")
        handle = chip.get_decoded_display_var("ETROC2", f"Peripheral {key}", decodedRegisterName)
        chip.read_decoded_value("ETROC2", f"Peripheral {key}", decodedRegisterName)
        value_to_return = handle.get()
        if(need_int): return int(value_to_return, base=16)
        else: return value_to_return

    def ws_decoded_register_write(self, decodedRegisterName, data_to_write, chip=None, chip_address=None, ws_address=None):
        if(chip==None and chip_address!=None and ws_address!=None):
            chip = self.get_chip_i2c_connection(chip_address, ws_address)
        elif(chip==None and (chip_address==None or ws_address==None)): print("Need either a chip or chip+ws address to access registers!")
        bit_depth = register_decoding["Waveform Sampler"]["Register Blocks"]["Config"][decodedRegisterName]["bits"]
        handle = chip.get_decoded_display_var("Waveform Sampler", "Config", decodedRegisterName)
        chip.read_decoded_value("Waveform Sampler", "Config", decodedRegisterName)
        if len(data_to_write)!=bit_depth: print("Binary data_to_write is of incorrect length for",decodedRegisterName, "with bit depth", bit_depth)
        data_hex_modified = hex(int(data_to_write, base=2))
        if(bit_depth>1): handle.set(data_hex_modified)
        elif(bit_depth==1): handle.set(data_to_write)
        else: print(decodedRegisterName, "!!!ERROR!!! Bit depth <1, how did we get here...")
        chip.write_decoded_value("Waveform Sampler", "Config", decodedRegisterName)

    def ws_decoded_config_read(self, decodedRegisterName, need_int=False, chip=None, chip_address=None, ws_address=None):
        if(chip==None and chip_address!=None and ws_address!=None):
            chip = self.get_chip_i2c_connection(chip_address, ws_address)
        elif(chip==None and (chip_address==None or ws_address==None)): print("Need either a chip or chip+ws address to access registers!")
        handle = chip.get_decoded_display_var("Waveform Sampler", f"Config", decodedRegisterName)
        chip.read_decoded_value("Waveform Sampler", f"Config", decodedRegisterName)
        if(need_int): return int(handle.get(), base=16)
        else: return handle.get()

    def ws_decoded_status_read(self, decodedRegisterName, need_int=False, chip=None, chip_address=None, ws_address=None):
        if(chip==None and chip_address!=None and ws_address!=None):
            chip = self.get_chip_i2c_connection(chip_address, ws_address)
        elif(chip==None and (chip_address==None or ws_address==None)): print("Need either a chip or chip+ws address to access registers!")
        handle = chip.get_decoded_display_var("Waveform Sampler", f"Status", decodedRegisterName)
        chip.read_decoded_value("Waveform Sampler", f"Status", decodedRegisterName)
        if(need_int): return int(handle.get(), base=16)
        else: return handle.get()

    #--------------------------------------------------------------------------#
    ## Function to get cached chip objects
    def get_chip_i2c_connection(self, chip_address, ws_address=None):
        if self._chips is None:
            self._chips = {}

        if chip_address not in self._chips:
            self._chips[chip_address] = i2c_gui.chips.ETROC2_Chip(parent=self.Script_Helper, i2c_controller=self.conn)
            self._chips[chip_address].config_i2c_address(chip_address)
            if(ws_address!=None): self._chips[chip_address].config_waveform_sampler_i2c_address(ws_address)  # Not needed if you do not access WS registers

        # logger.setLevel(log_level)
        return self._chips[chip_address]

    def get_pixel_chip(self, chip_address, row, col, ws_address=None):
        chip = self.get_chip_i2c_connection(chip_address, ws_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        row_indexer_handle.set(row)
        column_indexer_handle.set(col)
        return chip

    #--------------------------------------------------------------------------#
    ## Library of basic config functions
    # Function 0
    def pixel_check(self, chip_address, chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        pixel_flag_fail = False
        for row in range(16):
            for col in range(16):
                column_indexer_handle.set(col)
                row_indexer_handle.set(row)
                fetched_row = self.pixel_decoded_register_read("PixelID-Row", "Status", chip=chip, need_int=True)
                fetched_col = self.pixel_decoded_register_read("PixelID-Col", "Status", chip=chip, need_int=True)
                if(row!=fetched_row or col!=fetched_col):
                    print(chip_address, f"Pixel ({row},{col}) returned ({fetched_row}{fetched_col}), failed consistency check!")
                    pixel_flag_fail = True
        if(not pixel_flag_fail):
            print(f"Passed pixel check for chip: {hex(chip_address)}")

    # Function 1
    def basic_peripheral_register_check(self,chip_address,chip:i2c_gui.chips.ETROC2_Chip =None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        peri_flag_fail = False
        peripheralRegisterKeys = [i for i in range(32)]

        # Initial read
        chip.read_all_block("ETROC2", "Peripheral Config")
        for peripheralRegisterKey in peripheralRegisterKeys:
            # Fetch the register
            handle_PeriCfgX = chip.get_display_var("ETROC2", "Peripheral Config", f"PeriCfg{peripheralRegisterKey}")
            data_PeriCfgX = int(handle_PeriCfgX.get(), 0)
            # Make the flipped bits
            data_modified_PeriCfgX = data_PeriCfgX ^ 0xff

            # Set the register with the value
            handle_PeriCfgX.set(hex(data_modified_PeriCfgX))
            chip.write_register("ETROC2", "Peripheral Config", f"PeriCfg{peripheralRegisterKey}", write_check=True)  # Implicit read after write

            # Perform second read to verify the persistence of the change
            data_new_1_PeriCfgX = int(handle_PeriCfgX.get(), 0)
            chip.read_register("ETROC2", "Peripheral Config", f"PeriCfg{peripheralRegisterKey}")
            data_new_2_PeriCfgX = int(handle_PeriCfgX.get(), 0)

            # Undo the change to recover the original register value, and check for consistency
            handle_PeriCfgX.set(hex(data_PeriCfgX))
            chip.write_register("ETROC2", "Peripheral Config", f"PeriCfg{peripheralRegisterKey}")
            chip.read_register("ETROC2", "Peripheral Config", f"PeriCfg{peripheralRegisterKey}")
            data_recover_PeriCfgX = int(handle_PeriCfgX.get(), 0)

            # Handle what we learned from the tests
            # print(f"PeriCfg{peripheralRegisterKey:2}", data_bin_PeriCfgX, "To", data_bin_new_1_PeriCfgX,  "To", data_bin_new_2_PeriCfgX, "To", data_bin_recover_PeriCfgX)
            if(data_new_1_PeriCfgX!=data_new_2_PeriCfgX or data_new_2_PeriCfgX!=data_modified_PeriCfgX or data_recover_PeriCfgX!=data_PeriCfgX):
                print(f"{chip_address}, PeriCfg{peripheralRegisterKey:2}", "FAILURE")
                peri_flag_fail = True
        if(not peri_flag_fail):
            print(f"Passed peripheral write check for chip: {hex(chip_address)}")
        # Delete created components
        del peripheralRegisterKeys

    # Function 2
    def set_chip_peripherals(self, chip_address, chip_fc_delay, chip:i2c_gui.chips.ETROC2_Chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        chip.read_all_block("ETROC2", "Peripheral Config")

        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "EFuse_Prog")           # chip ID
        handle.set(hex(0x00017f0f))
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "singlePort")           # Set data output to right port only
        handle.set('1')
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "serRateLeft")          # Set Data Rates to 320 mbps
        handle.set(hex(0b00))
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "serRateRight")         # ^^
        handle.set(hex(0b00))
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "onChipL1AConf")        # Switches off the onboard L1A
        handle.set(hex(0b00))
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "PLL_ENABLEPLL")        # "Enable PLL mode, active high. Debugging use only."
        handle.set('1')
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "chargeInjectionDelay") # User tunable delay of Qinj pulse
        handle.set(hex(0x0a))
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "triggerGranularity")   # only for trigger bit
        handle.set(hex(0x01))
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "fcClkDelayEn")
        handle.set(chip_fc_delay[0])
        handle = chip.get_decoded_display_var("ETROC2", "Peripheral Config", "fcDataDelayEn")
        handle.set(chip_fc_delay[1])

        chip.write_all_block("ETROC2", "Peripheral Config")
        print(f"Peripherals set for chip: {hex(chip_address)}")

    # Function 3
    def disable_all_pixels(self, chip_address, chip:i2c_gui.chips.ETROC2_Chip=None, check_broadcast=False):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        broadcast_handle,_,_ = chip.get_indexer("broadcast")
        column_indexer_handle.set(0)
        row_indexer_handle.set(0)

        chip.read_all_block("ETROC2", "Pixel Config")

        disDataReadout_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "disDataReadout")
        QInjEn_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "QInjEn")
        disTrigPath_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "disTrigPath")
        upperTOATrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOATrig")
        lowerTOATrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOATrig")
        upperTOTTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOTTrig")
        lowerTOTTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOTTrig")
        upperCalTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperCalTrig")
        lowerCalTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerCalTrig")
        upperTOA_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOA")
        lowerTOA_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOA")
        upperTOT_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOT")
        lowerTOT_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOT")
        upperCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperCal")
        lowerCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerCal")
        enable_TDC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "enable_TDC")
        IBSel_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "IBSel")
        Bypass_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "Bypass_THCal")
        TH_offset_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "TH_offset")
        DAC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "DAC")

        disDataReadout = "1"
        QInjEn = "0"
        disTrigPath = "1"
        upperTOA = hex(0x000)
        lowerTOA = hex(0x000)
        upperTOT = hex(0x1ff)
        lowerTOT = hex(0x1ff)
        upperCal = hex(0x3ff)
        lowerCal = hex(0x3ff)
        enable_TDC = "0"
        # IBSel        = hex(0)     ## High power mode
        IBSel        = hex(7)     ## Low power mode
        Bypass_THCal = "1"        ## Byass Mode
        TH_offset    = hex(0x3f)  ## Max Offset
        DAC          = hex(0x3ff) ## Max DAC

        disDataReadout_handle.set(disDataReadout)
        QInjEn_handle.set(QInjEn)
        disTrigPath_handle.set(disTrigPath)
        upperTOATrig_handle.set(upperTOA)
        lowerTOATrig_handle.set(lowerTOA)
        upperTOTTrig_handle.set(upperTOT)
        lowerTOTTrig_handle.set(lowerTOT)
        upperCalTrig_handle.set(upperCal)
        lowerCalTrig_handle.set(lowerCal)
        upperTOA_handle.set(upperTOA)
        lowerTOA_handle.set(lowerTOA)
        upperTOT_handle.set(upperTOT)
        lowerTOT_handle.set(lowerTOT)
        upperCal_handle.set(upperCal)
        lowerCal_handle.set(lowerCal)
        enable_TDC_handle.set(enable_TDC)
        IBSel_handle.set(IBSel)
        Bypass_THCal_handle.set(Bypass_THCal)
        TH_offset_handle.set(TH_offset)
        DAC_handle.set(DAC)

        broadcast_handle.set(True)
        chip.write_all_block("ETROC2", "Pixel Config")
        print(f"Disabled pixels (Bypass, TH-3f DAC-3ff) for chip: {hex(chip_address)}")
        if(check_broadcast):
            return

        broadcast_ok = True
        for row in range(16):
            for col in range(16):
                column_indexer_handle.set(col)
                row_indexer_handle.set(row)

                chip.read_all_block("ETROC2", "Pixel Config")

                if int(disDataReadout_handle.get(), 0) != int(disDataReadout, 0):
                    broadcast_ok = False
                    break
                if int(QInjEn_handle.get(), 0) != int(QInjEn, 0):
                    broadcast_ok = False
                    break
                if int(disTrigPath_handle.get(), 0) != int(disTrigPath, 0):
                    broadcast_ok = False
                    break
                if int(upperTOATrig_handle.get(), 0) != int(upperTOA, 0):
                    broadcast_ok = False
                    break
                if int(lowerTOATrig_handle.get(), 0) != int(lowerTOA, 0):
                    broadcast_ok = False
                    break
                if int(upperTOTTrig_handle.get(), 0) != int(upperTOT, 0):
                    broadcast_ok = False
                    break
                if int(lowerTOTTrig_handle.get(), 0) != int(lowerTOT, 0):
                    broadcast_ok = False
                    break
                if int(upperCalTrig_handle.get(), 0) != int(upperCal, 0):
                    broadcast_ok = False
                    break
                if int(lowerCalTrig_handle.get(), 0) != int(lowerCal, 0):
                    broadcast_ok = False
                    break
                if int(upperTOA_handle.get(), 0) != int(upperTOA, 0):
                    broadcast_ok = False
                    break
                if int(lowerTOA_handle.get(), 0) != int(lowerTOA, 0):
                    broadcast_ok = False
                    break
                if int(upperTOT_handle.get(), 0) != int(upperTOT, 0):
                    broadcast_ok = False
                    break
                if int(lowerTOT_handle.get(), 0) != int(lowerTOT, 0):
                    broadcast_ok = False
                    break
                if int(upperCal_handle.get(), 0) != int(upperCal, 0):
                    broadcast_ok = False
                    break
                if int(lowerCal_handle.get(), 0) != int(lowerCal, 0):
                    broadcast_ok = False
                    break
                if int(enable_TDC_handle.get(), 0) != int(enable_TDC, 0):
                    broadcast_ok = False
                    break
                if int(IBSel_handle.get(), 0) != int(IBSel, 0):
                    broadcast_ok = False
                    break
                if int(Bypass_THCal_handle.get(), 0) != int(Bypass_THCal, 0):
                    broadcast_ok = False
                    break
                if int(TH_offset_handle.get(), 0) != int(TH_offset, 0):
                    broadcast_ok = False
                    break
                if int(DAC_handle.get(), 0) != int(DAC, 0):
                    broadcast_ok = False
                    break
            if not broadcast_ok:
                break

        if not broadcast_ok:
            print("Broadcast failed! \n Will manually disable pixels")
            for row in tqdm(range(16), desc="Disabling row", position=0):
                for col in range(16):
                    column_indexer_handle.set(col)
                    row_indexer_handle.set(row)

                    chip.read_all_block("ETROC2", "Pixel Config")

                    disDataReadout_handle.set(disDataReadout)
                    QInjEn_handle.set(QInjEn)
                    disTrigPath_handle.set(disTrigPath)
                    upperTOATrig_handle.set(upperTOA)
                    lowerTOATrig_handle.set(lowerTOA)
                    upperTOTTrig_handle.set(upperTOT)
                    lowerTOTTrig_handle.set(lowerTOT)
                    upperCalTrig_handle.set(upperCal)
                    lowerCalTrig_handle.set(lowerCal)
                    upperTOA_handle.set(upperTOA)
                    lowerTOA_handle.set(lowerTOA)
                    upperTOT_handle.set(upperTOT)
                    lowerTOT_handle.set(lowerTOT)
                    upperCal_handle.set(upperCal)
                    lowerCal_handle.set(lowerCal)
                    enable_TDC_handle.set(enable_TDC)
                    IBSel_handle.set(IBSel)
                    Bypass_THCal_handle.set(Bypass_THCal)
                    TH_offset_handle.set(TH_offset)
                    DAC_handle.set(DAC)

                    chip.write_all_block("ETROC2", "Pixel Config")
        print(f"Disabled pixels (Bypass, TH-3f DAC-3ff) for chip: {hex(chip_address)}")

    # Function 4
    def auto_calibration(self, chip_address, chip_name, chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        data = []
        # Loop for threshold calibration
        for row in tqdm(range(16), desc="Calibrating row", position=0):
            for col in range(16):
                self.auto_cal_pixel(chip_name=chip_name, row=row, col=col, verbose=False, chip_address=chip_address, chip=chip, data=data, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        BL_df = pandas.DataFrame(data = data)
        self.BL_df[chip_address] = BL_df
        # Delete created components
        del data
        print(f"Auto calibration finished for chip: {hex(chip_address)}")

    # Function 5
    def auto_calibration_and_disable(self, chip_address, chip_name, chip=None, check_broadcast=False):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        self.disable_all_pixels(chip_address=chip_address, chip=chip, check_broadcast=check_broadcast)
        self.auto_calibration(chip_address, chip_name, chip)

    # Function 6
    def set_chip_offsets(self, chip_address, offset=10, chip=None, pixel_list=None, verbose=False):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        if(pixel_list is None):
            for row in tqdm(range(16), desc="Setting Offsets for row", position=0):
                for col in range(16):
                    self.set_pixel_offsets(chip_address=chip_address, row=row, col=col, offset=offset, chip=chip, verbose=verbose, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        else:
            for row,col in pixel_list:
                self.set_pixel_offsets(chip_address=chip_address, row=row, col=col, offset=offset, chip=chip, verbose=verbose, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        print(f"Offset set to {hex(offset)} for chip: {hex(chip_address)}")

    # Function 7
    def prepare_ws_testing(self, chip_address, ws_address, chip=None):
        if(chip==None and chip_address!=None and ws_address!=None):
            chip = self.get_chip_i2c_connection(chip_address, ws_address)
        elif(chip==None and (chip_address==None or ws_address==None)): print("Need either a chip or chip+ws address to access registers!")
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        row = 0
        col = 14
        column_indexer_handle.set(col)
        row_indexer_handle.set(row)
        ### WS and pixel initialization
        self.enable_pixel_modular(row=row, col=col, verbose=True, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=True, Bypass_THCal=False, triggerWindow=True, cbWindow=True, power_mode="high")
        self.pixel_decoded_register_write("TH_offset", format(0x14, '06b'), chip=chip)  # Offset used to add to the auto BL for real triggering
        self.pixel_decoded_register_write("RFSel", format(0x00, '02b'), chip=chip)      # Set Largest feedback resistance -> maximum gain
        self.pixel_decoded_register_write("QSel", format(0x1e, '05b'), chip=chip)       # Ensure we inject 30 fC of charge
        print(f"WS Pixel (R0,C14) TH_Offset, RFSel, QSel Initialized for chip: {hex(chip_address)}")
        regOut1F_handle = chip.get_display_var("Waveform Sampler", "Config", "regOut1F")
        regOut1F_handle.set("0x22")
        chip.write_register("Waveform Sampler", "Config", "regOut1F")
        regOut1F_handle.set("0x0b")
        chip.write_register("Waveform Sampler", "Config", "regOut1F")
        # self.ws_decoded_register_write("mem_rstn", "0", chip=chip)                      # 0: reset memory
        # self.ws_decoded_register_write("clk_gen_rstn", "0", chip=chip)                  # 0: reset clock generation
        # self.ws_decoded_register_write("sel1", "0", chip=chip)                          # 0: Bypass mode, 1: VGA mode
        self.ws_decoded_register_write("DDT", format(0, '016b'), chip=chip)             # Time Skew Calibration set to 0
        self.ws_decoded_register_write("CTRL", format(0x2, '02b'), chip=chip)           # CTRL default = 0x10 for regOut0D
        self.ws_decoded_register_write("comp_cali", format(0, '03b'), chip=chip)        # Comparator calibration should be off
        print(f"WS Pixel Peripherals Set for chip: {hex(chip_address)}")

    #--------------------------------------------------------------------------#
    def save_baselines(self,
                       chip_fignames,
                       fig_title="",
                       fig_path="",
                       histdir="../ETROC-History",
                       histfile="",
                       show_BLs=True,
                       uBL_vmin=0,
                       uBL_vmax=0,
                       uNW_vmin=0,
                       uNW_vmax=16,
                       save_notes: str = "",
                ):
        if(histfile == ""):
            histdir = Path('../ETROC-History')
            histdir.mkdir(exist_ok=True)
            histfile = histdir / 'BaselineHistory.sqlite'

        for chip_address, chip_figname, chip_figtitle in zip(self.chip_addresses,chip_fignames,chip_fignames):
            BL_map_THCal,NW_map_THCal,BL_df,offset_map = self.get_auto_cal_maps(chip_address)
            fig = plt.figure(dpi=200, figsize=(20,10))
            gs = fig.add_gridspec(1,2)

            ax0 = fig.add_subplot(gs[0,0])
            if(uBL_vmin == 0): BL_vmin = np.min(BL_map_THCal[np.nonzero(BL_map_THCal)])
            else: BL_vmin = uBL_vmin
            if(uBL_vmax == 0): BL_vmax = np.max(BL_map_THCal[np.nonzero(BL_map_THCal)])
            else: BL_vmax = uBL_vmax
            ax0.set_title(f"{chip_figname}: BL (DAC LSB)\n{fig_title}", size=17, loc="right")
            img0 = ax0.imshow(BL_map_THCal, interpolation='none',vmin=BL_vmin,vmax=BL_vmax)
            ax0.set_aspect("equal")
            ax0.invert_xaxis()
            ax0.invert_yaxis()
            plt.xticks(range(16), range(16), rotation="vertical")
            plt.yticks(range(16), range(16))
            hep.cms.text(loc=0, ax=ax0, fontsize=17, text="Preliminary")
            divider = make_axes_locatable(ax0)
            cax = divider.append_axes('right', size="5%", pad=0.05)
            fig.colorbar(img0, cax=cax, orientation="vertical")#,boundaries=np.linspace(vmin,vmax,int((vmax-vmin)*30)))

            ax1 = fig.add_subplot(gs[0,1])
            ax1.set_title(f"{chip_figname}: NW (DAC LSB)\n{fig_title}", size=17, loc="right")
            img1 = ax1.imshow(NW_map_THCal, interpolation='none',vmin=uNW_vmin,vmax=uNW_vmax)
            ax1.set_aspect("equal")
            ax1.invert_xaxis()
            ax1.invert_yaxis()
            plt.xticks(range(16), range(16), rotation="vertical")
            plt.yticks(range(16), range(16))
            hep.cms.text(loc=0, ax=ax1, fontsize=17, text="Preliminary")
            divider = make_axes_locatable(ax1)
            cax = divider.append_axes('right', size="5%", pad=0.05)
            fig.colorbar(img1, cax=cax, orientation="vertical")#,boundaries=np.linspace(vmin,vmax,int((vmax-vmin)*5)))

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")

            for x in range(16):
                for y in range(16):
                    ax0.text(x,y,f"{BL_map_THCal.T[x,y]:.0f}", c="white", size=10, rotation=45, fontweight="bold", ha="center", va="center")
                    ax1.text(x,y,f"{NW_map_THCal.T[x,y]:.0f}", c="white", size=10, rotation=45, fontweight="bold", ha="center", va="center")
            plt.tight_layout()
            if(fig_path == ""):
                fig_outdir = Path('../ETROC-figures')
                fig_outdir = fig_outdir / (datetime.date.today().isoformat() + '_Array_Test_Results')
                fig_outdir.mkdir(exist_ok=True)
                fig_path = str(fig_outdir)
            savefigname = str(fig_path)+"/BL_NW_"+chip_figname+"_"+timestamp+".png"
            plt.savefig(savefigname)
            print("Saved fig to:",savefigname)
            plt.show()

            # BL_df.loc[:, "save_notes"] = save_notes
            with sqlite3.connect(histfile) as sqlconn:
                BL_df.to_sql('baselines', sqlconn, if_exists='append', index=False)

            savetxt(histdir / f'{chip_figname}_BL_{timestamp}.csv', BL_map_THCal, delimiter=',')
            savetxt(histdir / f'{chip_figname}_NW_{timestamp}.csv', NW_map_THCal, delimiter=',')
            if not show_BLs:
                plt.close()

    #--------------------------------------------------------------------------#

    def make_1d_nw_plot(
            self,
            chip_fignames,
            fig_title="",
            fig_path="",
        ):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        for chip_address, chip_figname in zip(self.chip_addresses,chip_fignames):
            _, NW_map_THCal, _, _ = self.get_auto_cal_maps(chip_address)
            fig, ax = plt.subplots(figsize=(10, 9))
            hep.cms.text(loc=0, ax=ax, fontsize=17, text="ETL ETROC")
            tmp_hist = hist.Hist(hist.axis.Regular(16, 0, 16, name='nw', label='NW [DAC]'))
            tmp_hist.fill(pandas.DataFrame(NW_map_THCal).to_numpy().flatten())
            mean, std = pandas.DataFrame(NW_map_THCal).to_numpy().flatten().mean(), pandas.DataFrame(NW_map_THCal).to_numpy().flatten().std()
            tmp_hist.plot1d(ax=ax, yerr=False, label=f'Mean: {mean:.2f}, Std: {std:.2f}')
            ax.set_title(f"{chip_figname}: NW (DAC LSB)\n{fig_title}", size=17, loc="right")
            ax.legend(fontsize=16)
            plt.xticks(range(16), range(16))
            plt.tight_layout()
            plt.show()
            fig.savefig(fig_path+"/NW_1D"+chip_figname+"_"+timestamp+".png")

    ## Power Mode Functions
    def set_power_mode(self, chip_address: int, row: int, col: int, power_mode: str = 'high', verbose: bool = False):
        if power_mode not in valid_power_modes:
            power_mode = "low"

        chip: i2c_gui.chips.ETROC2_Chip = self.get_chip_i2c_connection(chip_address)

        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        column_indexer_handle.set(col)
        row_indexer_handle.set(row)

        IBSel = hex(7)

        if power_mode == "high":
            IBSel = hex(0)
        elif power_mode == "010":
            IBSel = hex(2)
        elif power_mode == "101":
            IBSel = hex(5)
        elif power_mode == "low":
            IBSel = hex(7)
        else:
            IBSel = hex(7)

        self.pixel_decoded_register_write("IBSel", format(int(IBSel, 0), '03b'), chip=chip)

        if(verbose): print(f"Set pixel ({row},{col}) to power mode: {IBSel}")

    def set_power_mode_scan_list(self, chip_address: int, scan_list: list[tuple], power_mode: str = 'high', verbose: bool = False):
        if power_mode not in valid_power_modes:
            power_mode = "low"

        chip: i2c_gui.chips.ETROC2_Chip = self.get_chip_i2c_connection(chip_address)

        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")

        IBSel = hex(7)

        if power_mode == "high":
            IBSel = hex(0)
        elif power_mode == "010":
            IBSel = hex(2)
        elif power_mode == "101":
            IBSel = hex(5)
        elif power_mode == "low":
            IBSel = hex(7)
        else:
            IBSel = hex(7)

        for row, col in scan_list:
            column_indexer_handle.set(col)
            row_indexer_handle.set(row)

            self.pixel_decoded_register_write("IBSel", format(int(IBSel, 0), '03b'), chip=chip)

            if(verbose): print(f"Set pixel ({row},{col}) to power mode: {IBSel}")

    #--------------------------------------------------------------------------#
    ## I2C Dump Config Functions
    def dump_config(self, base_dir: Path, title: str):
        for idx in range(len(self.chip_addresses)):
            address = self.chip_addresses[idx]
            name = self.chip_names[idx]
            chip: i2c_gui.chips.ETROC2_Chip = self.get_chip_i2c_connection(address)

            chip.read_all()
            chip.save_config(base_dir / "{}_{}_{}.pckl".format(datetime.datetime.now().isoformat().replace(":","-"),name,title))

    #--------------------------------------------------------------------------#
    ## Broadcast Utils
    def test_broadcast(self, chip_address, chip=None, row=0, col=0):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        column_indexer_handle.set(col)
        row_indexer_handle.set(row)
        # Broadcast self consistency check
        upperTOT = self.pixel_decoded_register_read("upperTOT", "Config", chip=chip)
        lowerTOT = self.pixel_decoded_register_read("lowerTOT", "Config", chip=chip)
        upperTOA = self.pixel_decoded_register_read("upperTOA", "Config", chip=chip)
        lowerTOA = self.pixel_decoded_register_read("lowerTOA", "Config", chip=chip)
        upperCAL = self.pixel_decoded_register_read("upperCal", "Config", chip=chip)
        lowerCAL = self.pixel_decoded_register_read("lowerCal", "Config", chip=chip)
        upperTOTTrig = self.pixel_decoded_register_read("upperTOTTrig", "Config", chip=chip)
        lowerTOTTrig = self.pixel_decoded_register_read("lowerTOTTrig", "Config", chip=chip)
        upperTOATrig = self.pixel_decoded_register_read("upperTOATrig", "Config", chip=chip)
        lowerTOATrig = self.pixel_decoded_register_read("lowerTOATrig", "Config", chip=chip)
        upperCALTrig = self.pixel_decoded_register_read("upperCalTrig", "Config", chip=chip)
        lowerCALTrig = self.pixel_decoded_register_read("lowerCalTrig", "Config", chip=chip)
        if (upperTOT != "0x1ff"):
            print("Broadcast failed for upperTOT")
        if (upperTOA != "0x000"):
            print("Broadcast failed for upperTOA")
        if (upperCAL != "0x3ff"):
            print("Broadcast failed for upperCAL")
        if (lowerTOT != "0x1ff"):
            print("Broadcast failed for lowerTOT")
        if (lowerTOA != "0x000"):
            print("Broadcast failed for lowerTOA")
        if (lowerCAL != "0x3ff"):
            print("Broadcast failed for lowerCAL")
        if (upperTOTTrig != "0x1ff"):
            print("Broadcast failed for upperTOTTrig")
        if (upperTOATrig != "0x000"):
            print("Broadcast failed for upperTOATrig")
        if (upperCALTrig != "0x3ff"):
            print("Broadcast failed for upperCALTrig")
        if (lowerTOTTrig != "0x1ff"):
            print("Broadcast failed for lowerTOTTrig")
        if (lowerTOATrig != "0x000"):
            print("Broadcast failed for lowerTOATrig")
        if (lowerCALTrig != "0x3ff"):
            print("Broadcast failed for lowerCALTrig")
            # for row in tqdm(range(16), desc="Disabling row", position=0):
            #     for col in range(16):
            #         self.disable_pixel(row=row, col=col, verbose=False, chip_address=None, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        else:
            print(f"Broadcast worked for pixel ({row},{col})")

    #--------------------------------------------------------------------------#
    ## Functions relating to fetching or saving the BL/NW/Offset Maps
    def get_auto_cal_maps(self, chip_address):
        return self.BL_map_THCal[chip_address],self.NW_map_THCal[chip_address],self.BL_df[chip_address],self.BLOffset_map[chip_address]

    def save_auto_cal_BL_map(self, chip_address, chip_name, user_path=""):
        outdir = Path('../ETROC-Data/'+(datetime.date.today().isoformat() + '_Array_Test_Results/')+user_path)
        outdir.mkdir(parents=True,exist_ok=True)
        outfile_BL_map = outdir / (chip_name+"_BL_map.pickle")
        with open(outfile_BL_map,'wb') as f:
            pickle.dump(self.BL_map_THCal[chip_address],f,pickle.HIGHEST_PROTOCOL)

    def save_auto_cal_NW_map(self, chip_address, chip_name, user_path=""):
        outdir = Path('../ETROC-Data/'+(datetime.date.today().isoformat() + '_Array_Test_Results/')+user_path)
        outdir.mkdir(parents=True,exist_ok=True)
        outfile_NW_map = outdir / (chip_name+"_NW_map.pickle")
        with open(outfile_NW_map,'wb') as f:
            pickle.dump(self.NW_map_THCal[chip_address],f,pickle.HIGHEST_PROTOCOL)

    def save_auto_cal_BL_df(self, chip_address, chip_name, user_path=""):
        outdir = Path('../ETROC-Data/'+(datetime.date.today().isoformat() + '_Array_Test_Results')+user_path)
        outdir.mkdir(parents=True,exist_ok=True)
        outfile_BL_df = outdir / (chip_name+"_BL_df.pickle")
        with open(outfile_BL_df,'wb') as f:
            pickle.dump(self.BL_df[chip_address],f,pickle.HIGHEST_PROTOCOL)

    def load_auto_cal_BL_map(self, chip_address, chip_name, user_path=""):
        indir = Path('../ETROC-Data/'+(datetime.date.today().isoformat() + '_Array_Test_Results/')+user_path)
        infile_BL_map = indir / (chip_name+"_BL_map.pickle")
        with open(infile_BL_map, 'rb') as f:
            self.BL_map_THCal[chip_address]=pickle.load(f)

    def load_auto_cal_NW_map(self, chip_address, chip_name, user_path=""):
        indir = Path('../ETROC-Data/'+(datetime.date.today().isoformat() + '_Array_Test_Results/')+user_path)
        infile_NW_map = indir / (chip_name+"_NW_map.pickle")
        with open(infile_NW_map, 'rb') as f:
            self.NW_map_THCal[chip_address]=pickle.load(f)

    def load_auto_cal_BL_df(self, chip_address, chip_name, user_path=""):
        indir = Path('../ETROC-Data/'+(datetime.date.today().isoformat() + '_Array_Test_Results/')+user_path)
        infile_BL_df = indir / (chip_name+"_BL_df.pickle")
        with open(infile_BL_df, 'rb') as f:
            self.BL_df[chip_address]=pickle.load(f)

    def save_auto_cal_maps(self, chip_address, chip_name, user_path=""):
        self.save_auto_cal_BL_map(chip_address, chip_name, user_path)
        self.save_auto_cal_NW_map(chip_address, chip_name, user_path)
        self.save_auto_cal_BL_df(chip_address, chip_name, user_path)

    def load_auto_cal_maps(self, chip_address, chip_name, user_path=""):
        self.load_auto_cal_BL_map(chip_address, chip_name, user_path)
        self.load_auto_cal_NW_map(chip_address, chip_name, user_path)
        self.load_auto_cal_BL_df(chip_address, chip_name, user_path)

    #--------------------------------------------------------------------------#
    ## Bulk Pixel Enable Functions
    def enable_select_pixels_in_chips(self, pixel_list, QInjEn=True, Bypass_THCal=True, triggerWindow=True, cbWindow=True, verbose=True, specified_addresses=[], power_mode="high"):
        if power_mode not in valid_power_modes:
            power_mode = "low"
        if(len(specified_addresses)==0):
            full_list = self.chip_addresses
        else:
            full_list = specified_addresses
        for chip_address in full_list:
            chip = self.get_chip_i2c_connection(chip_address)
            row_indexer_handle,_,_ = chip.get_indexer("row")
            column_indexer_handle,_,_ = chip.get_indexer("column")
            for row,col in tqdm(pixel_list):
                self.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=QInjEn, Bypass_THCal=Bypass_THCal, triggerWindow=triggerWindow, cbWindow=cbWindow, power_mode=power_mode)
        del full_list

    def enable_all_pixels(self, chip_address, chip=None, QInjEn=True, Bypass_THCal=True, triggerWindow=True, cbWindow=True, verbose=False, power_mode="high"):
        if power_mode not in valid_power_modes:
            power_mode = "low"
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        for row in tqdm(range(16), desc="Enabling row", position=0):
            for col in range(16):
                self.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=QInjEn, Bypass_THCal=Bypass_THCal, triggerWindow=triggerWindow, cbWindow=cbWindow, power_mode=power_mode)
        print(f"Enabled pixels for chip: {hex(chip_address)}")

    #--------------------------------------------------------------------------#
    ## Single Pixel Operation Functions
    def disable_pixel(self, row, col, verbose=False, chip_address=None, chip:i2c_gui.chips.ETROC2_Chip=None, row_indexer_handle=None, column_indexer_handle=None):
        if(chip==None and chip_address!=None):
            chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None):
            print("Need chip address to make a new chip in disable pixel!")
            return
        if(row_indexer_handle==None):
            row_indexer_handle,_,_ = chip.get_indexer("row")
        if(column_indexer_handle==None):
            column_indexer_handle,_,_ = chip.get_indexer("column")
        column_indexer_handle.set(col)
        row_indexer_handle.set(row)

        chip.read_all_block("ETROC2", "Pixel Config")

        disDataReadout_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "disDataReadout")
        QInjEn_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "QInjEn")
        disTrigPath_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "disTrigPath")
        upperTOATrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOATrig")
        lowerTOATrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOATrig")
        upperTOTTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOTTrig")
        lowerTOTTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOTTrig")
        upperCalTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperCalTrig")
        lowerCalTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerCalTrig")
        upperTOA_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOA")
        lowerTOA_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOA")
        upperTOT_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOT")
        lowerTOT_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOT")
        upperCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperCal")
        lowerCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerCal")
        enable_TDC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "enable_TDC")

        disDataReadout = "1"
        QInjEn = "0"
        disTrigPath = "1"
        upperTOA = hex(0x000)
        lowerTOA = hex(0x000)
        upperTOT = hex(0x1ff)
        lowerTOT = hex(0x1ff)
        upperCal = hex(0x3ff)
        lowerCal = hex(0x3ff)
        enable_TDC = "0"

        disDataReadout_handle.set(disDataReadout)
        QInjEn_handle.set(QInjEn)
        disTrigPath_handle.set(disTrigPath)
        upperTOATrig_handle.set(upperTOA)
        lowerTOATrig_handle.set(lowerTOA)
        upperTOTTrig_handle.set(upperTOT)
        lowerTOTTrig_handle.set(lowerTOT)
        upperCalTrig_handle.set(upperCal)
        lowerCalTrig_handle.set(lowerCal)
        upperTOA_handle.set(upperTOA)
        lowerTOA_handle.set(lowerTOA)
        upperTOT_handle.set(upperTOT)
        lowerTOT_handle.set(lowerTOT)
        upperCal_handle.set(upperCal)
        lowerCal_handle.set(lowerCal)
        enable_TDC_handle.set(enable_TDC)

        chip.write_all_block("ETROC2", "Pixel Config")

        if(verbose): print(f"Disabled pixel (no change in IBSel or DAC) ({row},{col}) for chip: {hex(chip_address)}")

    def enable_pixel_modular(self, row, col, verbose=False, chip_address=None, chip:i2c_gui.chips.ETROC2_Chip=None, row_indexer_handle=None, column_indexer_handle=None, QInjEn=False, Bypass_THCal=True, triggerWindow=True, cbWindow=True, power_mode = "high"):
        if power_mode not in valid_power_modes:
            power_mode = "low"
        if(chip==None and chip_address!=None):
            chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None):
            print("Need chip address to make a new chip in disable pixel!")
            return
        if(row_indexer_handle==None):
            row_indexer_handle,_,_ = chip.get_indexer("row")
        if(column_indexer_handle==None):
            column_indexer_handle,_,_ = chip.get_indexer("column")
        column_indexer_handle.set(col)
        row_indexer_handle.set(row)

        chip.read_all_block("ETROC2", "Pixel Config")

        disDataReadout_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "disDataReadout")
        QInjEn_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "QInjEn")
        disTrigPath_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "disTrigPath")
        L1Adelay_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "L1Adelay")
        Bypass_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "Bypass_THCal")
        TH_offset_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "TH_offset")
        QSel_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "QSel")
        DAC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "DAC")
        enable_TDC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "enable_TDC")
        IBSel_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "IBSel")

        disDataReadout_handle.set("0")
        QInjEn_handle.set("1" if QInjEn else "0")
        disTrigPath_handle.set("0")
        L1Adelay_handle.set(hex(0x01f5)) # Change L1A delay - circular buffer in ETROC2 pixel
        Bypass_THCal_handle.set("1" if Bypass_THCal else "0")
        TH_offset_handle.set(hex(0x14))  # Offset 20 used to add to the auto BL for real
        QSel_handle.set(hex(0x1e))       # Ensure we inject 30 fC of charge
        DAC_handle.set(hex(0x3ff))
        enable_TDC_handle.set("1")
        self.set_TDC_window_vars(chip=chip, triggerWindow=triggerWindow, cbWindow=cbWindow)
        if power_mode == "high":
            IBSel_handle.set(hex(0))
        elif power_mode == "010":
            IBSel_handle.set(hex(2))
        elif power_mode == "101":
            IBSel_handle.set(hex(5))
        elif power_mode == "low":
            IBSel_handle.set(hex(7))
        else:
            IBSel_handle.set(hex(7))

        chip.write_all_block("ETROC2", "Pixel Config")

        if(verbose): print(f"Enabled pixel ({row},{col}) for chip: {hex(chip_address)}")

    def broadcast_calibrate_pixels(self, chip_address, chip_name, chip:i2c_gui.chips.ETROC2_Chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        broadcast_indexer_handle,_,_ = chip.get_indexer("broadcast")
        data = []

        column_indexer_handle.set(15)
        row_indexer_handle.set(15)

        chip.read_all_block("ETROC2", "Pixel Config")

        enable_TDC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "enable_TDC")
        CLKEn_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "CLKEn_THCal")
        BufEn_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "BufEn_THCal")
        Bypass_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "Bypass_THCal")
        TH_offset_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "TH_offset")
        RSTn_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "RSTn_THCal")
        ScanStart_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "ScanStart_THCal")
        DAC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "DAC")
        ScanDone_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Status", "ScanDone")
        BL_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Status", "BL")
        NW_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Status", "NW")

        # Disable TDC
        enable_TDC_handle.set("0")
        # Enable THCal clock and buffer, disable bypass
        CLKEn_THCal_handle.set("1")
        BufEn_THCal_handle.set("1")
        Bypass_THCal_handle.set("0")
        TH_offset_handle.set(hex(0x0a))

        # Send changes to all pixels
        broadcast_indexer_handle.set(True)
        chip.write_all_block("ETROC2", "Pixel Config")

        # Reset the calibration block (active low)
        RSTn_THCal_handle.set("0")
        broadcast_indexer_handle.set(True)
        chip.write_decoded_value("ETROC2", "Pixel Config", "RSTn_THCal")
        RSTn_THCal_handle.set("1")
        broadcast_indexer_handle.set(True)
        chip.write_decoded_value("ETROC2", "Pixel Config", "RSTn_THCal")

        # Start and Stop the calibration, (25ns x 2**15 ~ 800 us, ACCumulator max is 2**15)
        ScanStart_THCal_handle.set("1")
        broadcast_indexer_handle.set(True)
        chip.write_decoded_value("ETROC2", "Pixel Config", "ScanStart_THCal")
        ScanStart_THCal_handle.set("0")
        broadcast_indexer_handle.set(True)
        chip.write_decoded_value("ETROC2", "Pixel Config", "ScanStart_THCal")

        for row in range(16):
            for col in range(16):
                column_indexer_handle.set(col)
                row_indexer_handle.set(row)

                # Wait for the calibration to be done correctly
                retry_counter = 0
                chip.read_all_block("ETROC2", "Pixel Status")
                while ScanDone_handle.get() != "1":
                    time.sleep(0.01)
                    chip.read_all_block("ETROC2", "Pixel Status")
                    retry_counter += 1
                    if retry_counter == 5 and ScanDone_handle.get() != "1":
                        print(f"!!!ERROR!!! Scan not done for row {row}, col {col}!!!")
                        break

                self.BL_map_THCal[chip_address][row, col] = int(BL_handle.get(), 0)
                self.NW_map_THCal[chip_address][row, col] = int(NW_handle.get(), 0)
                if(data != None):
                    data += [{
                        'col': col,
                        'row': row,
                        'baseline': self.BL_map_THCal[chip_address][row, col],
                        'noise_width': self.NW_map_THCal[chip_address][row, col],
                        'timestamp': datetime.datetime.now(),
                        'chip_name': chip_name,
                    }]

        # Enable TDC
        enable_TDC_handle.set("1")
        # Disable THCal clock and buffer, enable bypass
        CLKEn_THCal_handle.set("0")
        BufEn_THCal_handle.set("0")
        Bypass_THCal_handle.set("1")
        DAC_handle.set(hex(0x3ff))

        # Send changes to chip
        broadcast_indexer_handle.set(True)
        chip.write_all_block("ETROC2", "Pixel Config")

        BL_df = pandas.DataFrame(data = data)
        self.BL_df[chip_address] = BL_df
        # Delete created components
        del data
        print(f"Broadcast auto calibration finished for chip: {hex(chip_address)}")

    def auto_cal_pixel(self, chip_name, row, col, verbose=False, chip_address=None, chip:i2c_gui.chips.ETROC2_Chip=None, data=None, row_indexer_handle=None, column_indexer_handle=None):
        if(chip==None and chip_address!=None):
            chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None):
            print("Need chip address to make a new chip in disable pixel!")
            return
        if(row_indexer_handle==None):
            row_indexer_handle,_,_ = chip.get_indexer("row")
        if(column_indexer_handle==None):
            column_indexer_handle,_,_ = chip.get_indexer("column")
        column_indexer_handle.set(col)
        row_indexer_handle.set(row)

        chip.read_all_block("ETROC2", "Pixel Config")

        enable_TDC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "enable_TDC")
        CLKEn_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "CLKEn_THCal")
        BufEn_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "BufEn_THCal")
        Bypass_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "Bypass_THCal")
        TH_offset_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "TH_offset")
        RSTn_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "RSTn_THCal")
        ScanStart_THCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "ScanStart_THCal")
        DAC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "DAC")
        ScanDone_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Status", "ScanDone")
        BL_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Status", "BL")
        NW_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Status", "NW")

        # Disable TDC
        enable_TDC_handle.set("0")
        # Enable THCal clock and buffer, disable bypass
        CLKEn_THCal_handle.set("1")
        BufEn_THCal_handle.set("1")
        Bypass_THCal_handle.set("0")
        # TH_offset_handle.set(hex(0x0a))

        # Send changes to chip
        chip.write_all_block("ETROC2", "Pixel Config")

        # Reset the calibration block (active low)
        RSTn_THCal_handle.set("0")
        chip.write_decoded_value("ETROC2", "Pixel Config", "RSTn_THCal")
        RSTn_THCal_handle.set("1")
        chip.write_decoded_value("ETROC2", "Pixel Config", "RSTn_THCal")

        # Start and Stop the calibration, (25ns x 2**15 ~ 800 us, ACCumulator max is 2**15)
        ScanStart_THCal_handle.set("1")
        chip.write_decoded_value("ETROC2", "Pixel Config", "ScanStart_THCal")
        ScanStart_THCal_handle.set("0")
        chip.write_decoded_value("ETROC2", "Pixel Config", "ScanStart_THCal")

        # Wait for the calibration to be done correctly
        retry_counter = 0
        chip.read_all_block("ETROC2", "Pixel Status")
        while ScanDone_handle.get() != "1":
            time.sleep(0.1)
            chip.read_all_block("ETROC2", "Pixel Status")
            retry_counter += 1
            if retry_counter == 5 and ScanDone_handle.get() != "1":
                print(f"!!!ERROR!!! Scan not done for row {row}, col {col}!!!")
                break

        self.BL_map_THCal[chip_address][row, col] = int(BL_handle.get(), 0)
        self.NW_map_THCal[chip_address][row, col] = int(NW_handle.get(), 0)
        self.BLOffset_map[chip_address][row, col] = 0
        if(data != None):
            data += [{
                'col': col,
                'row': row,
                'baseline': self.BL_map_THCal[chip_address][row, col],
                'noise_width': self.NW_map_THCal[chip_address][row, col],
                'timestamp': datetime.datetime.now(),
                'chip_name': chip_name,
            }]

        # Disable TDC
        enable_TDC_handle.set("0")
        # Disable THCal clock and buffer
        CLKEn_THCal_handle.set("0")
        BufEn_THCal_handle.set("0")
        # Enable bypass and set the BL to the DAC
        Bypass_THCal_handle.set("1")
        DAC_handle.set(hex(0x3ff))

        # Send changes to chip
        chip.write_all_block("ETROC2", "Pixel Config")

        if(verbose): print(f"Auto calibration done (enTDC=0 + DAC=1023) for pixel ({row},{col}) on chip: {hex(chip_address)}")

    def set_pixel_offsets(self, chip_address, row, col, offset=10, chip=None, verbose=False, row_indexer_handle=None, column_indexer_handle=None):
        if(chip==None and chip_address!=None):
            chip: i2c_gui.chips.ETROC2_Chip = self.get_chip_i2c_connection(chip_address)
        elif(chip==None and chip_address==None):
            print("Need chip address to make a new chip in disable pixel!")
            return
        if(row_indexer_handle==None):
            row_indexer_handle,_,_ = chip.get_indexer("row")
        if(column_indexer_handle==None):
            column_indexer_handle,_,_ = chip.get_indexer("column")
        column_indexer_handle.set(col)
        row_indexer_handle.set(row)
        DAC_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "DAC")
        chip.read_decoded_value("ETROC2", "Pixel Config", "DAC")
        old_DAC = int(DAC_handle.get(), 0)
        DAC_handle.set(hex(int(self.BL_map_THCal[chip_address][row, col]+offset)))
        chip.write_decoded_value("ETROC2", "Pixel Config", "DAC")
        new_DAC = int(DAC_handle.get(), 0)
        self.BLOffset_map[chip_address][row, col] = offset
        if(verbose): print(f"Offset set to {hex(offset)} (DAC from {old_DAC} to {new_DAC}) for pixel ({row},{col}) (BL={self.BL_map_THCal[chip_address][row, col]}) for chip: {hex(chip_address)}")

    def set_TDC_window_vars(self, chip, triggerWindow=True, cbWindow=True):
        upperTOATrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOATrig")
        lowerTOATrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOATrig")
        upperTOTTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOTTrig")
        lowerTOTTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOTTrig")
        upperCalTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperCalTrig")
        lowerCalTrig_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerCalTrig")
        upperTOA_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOA")
        lowerTOA_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOA")
        upperTOT_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperTOT")
        lowerTOT_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerTOT")
        upperCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "upperCal")
        lowerCal_handle = chip.get_decoded_indexed_var("ETROC2", "Pixel Config", "lowerCal")

        upperTOATrig_handle.set(hex(0x3ff if triggerWindow else 0x000))
        lowerTOATrig_handle.set(hex(0x000))
        upperTOTTrig_handle.set(hex(0x1ff if triggerWindow else 0x000))
        lowerTOTTrig_handle.set(hex(0x000))
        upperCalTrig_handle.set(hex(0x3ff if triggerWindow else 0x000))
        lowerCalTrig_handle.set(hex(0x000))
        upperTOA_handle.set(hex(0x3ff if cbWindow else 0x000))
        lowerTOA_handle.set(hex(0x000))
        upperTOT_handle.set(hex(0x1ff if cbWindow else 0x000))
        lowerTOT_handle.set(hex(0x000))
        upperCal_handle.set(hex(0x3ff if cbWindow else 0x000))
        lowerCal_handle.set(hex(0x000))

    def open_TDC_all(self, chip_address, chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        for row in tqdm(range(16), desc="Disabling row", position=0):
            for col in tqdm(range(16), desc=" col", position=1, leave=False):
                column_indexer_handle.set(col)
                row_indexer_handle.set(row)
                chip.read_all_block("ETROC2", "Pixel Config")
                self.set_TDC_window_vars(chip=chip, triggerWindow=True, cbWindow=True)
                chip.write_all_block("ETROC2", "Pixel Config")
        print(f"Opened TDC for pixels for chip: {hex(chip_address)}")

    def close_TDC_all(self, chip_address, chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        row_indexer_handle,_,_ = chip.get_indexer("row")
        column_indexer_handle,_,_ = chip.get_indexer("column")
        for row in tqdm(range(16), desc="Disabling row", position=0):
            for col in tqdm(range(16), desc=" col", position=1, leave=False):
                column_indexer_handle.set(col)
                row_indexer_handle.set(row)
                chip.read_all_block("ETROC2", "Pixel Config")
                self.set_TDC_window_vars(chip=chip, triggerWindow=True, cbWindow=False)
                chip.write_all_block("ETROC2", "Pixel Config")
        print(f"Closed TDC for pixels for chip: {hex(chip_address)}")

    #--------------------------------------------------------------------------#
    ## Chip Calibration Util Functions
    def onchipL1A(self, chip_address, chip=None, comm='00'):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        self.peripheral_decoded_register_write("onChipL1AConf", comm, chip=chip)
        print(f"OnChipL1A action {comm} done for chip: {hex(chip_address)}")

    def asyAlignFastcommand(self, chip_address, chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        self.peripheral_decoded_register_write("asyAlignFastcommand", "1", chip=chip)
        time.sleep(0.2)
        self.peripheral_decoded_register_write("asyAlignFastcommand", "0", chip=chip)
        print(f"asyAlignFastcommand action done for chip: {hex(chip_address)}")

    def asyResetGlobalReadout(self, chip_address, chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        self.peripheral_decoded_register_write("asyResetGlobalReadout", "0", chip=chip)
        time.sleep(0.2)
        self.peripheral_decoded_register_write("asyResetGlobalReadout", "1", chip=chip)
        print(f"Reset Global Readout done for chip: {hex(chip_address)}")

    def calibratePLL(self, chip_address, chip=None):
        if(chip==None):
            chip = self.get_chip_i2c_connection(chip_address)
        self.peripheral_decoded_register_write("asyPLLReset", "0", chip=chip)
        time.sleep(0.2)
        self.peripheral_decoded_register_write("asyPLLReset", "1", chip=chip)
        self.peripheral_decoded_register_write("asyStartCalibration", "0", chip=chip)
        time.sleep(0.2)
        self.peripheral_decoded_register_write("asyStartCalibration", "1", chip=chip)
        print(f"PLL Calibrated for chip: {hex(chip_address)}")

    #--------------------------------------------------------------------------#
    #--------------------------------------------------------------------------#

#--------------------------------------------------------------------------#
#  Functions separate from the i2c_conn class

def pixel_turnon_points(i2c_conn, chip_address, chip_figname, s_flag, d_flag, a_flag, p_flag, scan_list, verbose=False, attempt='', today='', calibrate=False, hostname = "192.168.2.3", power_mode="high"):
    scan_name = chip_figname+"_VRef_SCurve_BinarySearch_TurnOn"
    fpga_time = 3

    if(today==''): today = datetime.date.today().isoformat()
    todaystr = "../ETROC-Data/" + today + "_Array_Test_Results/"
    base_dir = Path(todaystr)
    base_dir.mkdir(exist_ok=True)

    chip = i2c_conn.get_chip_i2c_connection(chip_address)
    row_indexer_handle,_,_ = chip.get_indexer("row")
    column_indexer_handle,_,_ = chip.get_indexer("column")

    BL_map_THCal,NW_map_THCal,_,_ = i2c_conn.get_auto_cal_maps(chip_address)
    for row, col in tqdm(scan_list, leave=False):
        turnon_point = -1
        if(calibrate):
            i2c_conn.auto_cal_pixel(chip_name=chip_figname, row=row, col=col, verbose=False, chip_address=chip_address, chip=chip, data=None, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
            # i2c_conn.disable_pixel(row, col, verbose=False, chip_address=chip_address, chip=None, row_indexer_handle=None, column_indexer_handle=None)
        i2c_conn.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=True, Bypass_THCal=True, triggerWindow=True, cbWindow=False, power_mode=power_mode)
        # pixel_connected_chip = i2c_conn.get_pixel_chip(chip_address, row, col)
        row_indexer_handle.set(row)
        column_indexer_handle.set(col)
        threshold_name = scan_name+f'_Pixel_C{col}_R{row}'+attempt
        parser = parser_arguments.create_parser()
        (options, args) = parser.parse_args(args=f"-f --useIPC --hostname {hostname} -o {threshold_name} -v -w -s {s_flag} -d {d_flag} -a {a_flag} -p {p_flag} --counter_duration 0x0001 --fpga_data_time_limit {int(fpga_time)} --fpga_data_QInj --nodaq".split())
        IPC_queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=run_script.main_process, args=(IPC_queue, options, f'process_outputs/main_process_link'))
        process.start()
        process.join()

        a = 0
        b = BL_map_THCal[row][col] + 3*(NW_map_THCal[row][col])
        while b-a>1:
            DAC = int(np.floor((a+b)/2))
            # Set the DAC to the value being scanned
            i2c_conn.pixel_decoded_register_write("DAC", format(DAC, '010b'), chip=chip)
            (options, args) = parser.parse_args(args=f"--useIPC --hostname {hostname} -o {threshold_name} -v --counter_duration 0x0001 --fpga_data_time_limit {int(fpga_time)} --fpga_data_QInj --nodaq --DAC_Val {int(DAC)}".split())
            IPC_queue = multiprocessing.Queue()
            process = multiprocessing.Process(target=run_script.main_process, args=(IPC_queue, options, f'process_outputs/main_process_{DAC}'))
            process.start()
            process.join()

            continue_flag = False
            root = '../ETROC-Data'
            file_pattern = "*FPGA_Data.dat"
            path_pattern = f"*{today}_Array_Test_Results/{threshold_name}"
            file_list = []
            for path, subdirs, files in os.walk(root):
                if not fnmatch(path, path_pattern): continue
                for name in files:
                    pass
                    if fnmatch(name, file_pattern):
                        file_list.append(os.path.join(path, name))
            for file_index, file_name in enumerate(file_list):
                with open(file_name) as infile:
                    lines = infile.readlines()
                    last_line = lines[-1]
                    first_line = lines[0]
                    text_list = last_line.split(',')
                    FPGA_state = text_list[0]
                    line_DAC = int(text_list[-1])
                    if(FPGA_state==0 or line_DAC!=DAC):
                        continue_flag=True
                        continue
                    TDC_tb = int(text_list[-2])
                    turnon_point = line_DAC
                    # Condition handling for Binary Search
                    if(TDC_tb>0):
                        b = DAC
                    else:
                        a = DAC
            if(continue_flag): continue
        i2c_conn.disable_pixel(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        if(verbose): print(f"Turn-On point for Pixel ({row},{col}) for chip {hex(chip_address)} is found to be DAC:{turnon_point}")
        del IPC_queue, process, parser

def trigger_bit_noisescan(i2c_conn, chip_address, chip_figname, s_flag, d_flag, a_flag, p_flag, scan_list, verbose=False, pedestal_scan_step = 1, attempt='', today='', busyCB=False, tp_tag='', neighbors=False, allon=False, hostname = "192.168.2.3", override_baseline=None, power_mode="high"):
    root = '../ETROC-Data'
    file_pattern = "*FPGA_Data.dat"
    thresholds = np.arange(-10,10,pedestal_scan_step) # relative to BL
    scan_name = chip_figname+"_VRef_SCurve_NoiseOnly"
    fpga_time = 3
    if(today==''): today = datetime.date.today().isoformat()
    todaystr = root+"/" + today + "_Array_Test_Results/"
    base_dir = Path(todaystr)
    base_dir.mkdir(exist_ok=True)
    BL_map_THCal,NW_map_THCal,_,_ = i2c_conn.get_auto_cal_maps(chip_address)
    chip = i2c_conn.get_chip_i2c_connection(chip_address)
    row_indexer_handle,_,_ = chip.get_indexer("row")
    column_indexer_handle,_,_ = chip.get_indexer("column")
    if(allon):
        for first_idx in tqdm(range(16), leave=False):
            for second_idx in range(16):
                i2c_conn.enable_pixel_modular(row=first_idx, col=second_idx, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=False, triggerWindow=False, cbWindow=True, power_mode=power_mode)
    for row,col in scan_list:
        # turnon_point = -1
        # path_pattern = f"*{today}_Array_Test_Results/{chip_figname}_VRef_SCurve_BinarySearch_TurnOn_Pixel_C{col}_R{row}"+tp_tag
        # file_list = []
        # for path, subdirs, files in os.walk(root):
        #     if not fnmatch(path, path_pattern): continue
        #     for name in files:
        #         pass
        #         if fnmatch(name, file_pattern):
        #             file_list.append(os.path.join(path, name))
        # for file_index, file_name in enumerate(file_list):
        #     with open(file_name) as infile:
        #         lines = infile.readlines()
        #         last_line = lines[-1]
        #         text_list = last_line.split(',')
        #         line_DAC = int(text_list[-1])
        #         turnon_point = line_DAC
        turnon_point = override_baseline if override_baseline is not None else BL_map_THCal[row][col]
        if(allon or busyCB):
            i2c_conn.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=True, triggerWindow=True, cbWindow=True, power_mode=power_mode)
        else:
            i2c_conn.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=True, triggerWindow=True, cbWindow=False, power_mode=power_mode)
        if(neighbors and (not allon)):
            for first_idx in range(-1,2):
                row_nb = row+first_idx
                if(row_nb>15 or row_nb<0): continue
                for second_idx in range(-1,2):
                    col_nb = col+second_idx
                    if(col_nb>15 or col_nb<0): continue
                    if(col_nb==col and row_nb == row): continue
                    i2c_conn.enable_pixel_modular(row=row_nb, col=col_nb, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=True, triggerWindow=True, cbWindow=True, power_mode=power_mode)
        row_indexer_handle.set(row)
        column_indexer_handle.set(col)
        threshold_name = scan_name+f'_Pixel_C{col}_R{row}'+attempt
        parser = parser_arguments.create_parser()
        (options, args) = parser.parse_args(args=f"-f --useIPC --hostname {hostname} -o {threshold_name} -v -w --counter_duration 0x0001 --fpga_data_time_limit {int(fpga_time)} --fpga_data --nodaq -s {s_flag} -d {d_flag} -a {a_flag} -p {p_flag}".split())
        IPC_queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=run_script.main_process, args=(IPC_queue, options, f'process_outputs/main_process_noiseOnly'))
        process.start()
        process.join()

        for DAC in tqdm(thresholds, desc=f'DAC Loop for Chip {hex(chip_address)} Pixel ({row},{col})', leave=False):
        # for DAC in thresholds:
            threshold = int(DAC+turnon_point)
            if threshold < 1:
                threshold = 1
            # triggerbit_full_Scurve[row][col][threshold] = 0
            i2c_conn.pixel_decoded_register_write("DAC", format(threshold, '010b'), chip=chip)
            (options, args) = parser.parse_args(args=f"--useIPC --hostname {hostname} -o {threshold_name} -v --counter_duration 0x0001 --fpga_data_time_limit {int(fpga_time)} --fpga_data --nodaq --DAC_Val {int(threshold)}".split())
            IPC_queue = multiprocessing.Queue()
            process = multiprocessing.Process(target=run_script.main_process, args=(IPC_queue, options, f'process_outputs/main_process_NoiseOnly_{threshold}'))
            process.start()
            process.join()

        if(not allon):
            i2c_conn.disable_pixel(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
            if(neighbors):
                for first_idx in range(-1,2):
                    row_nb = row+first_idx
                    if(row_nb>15 or row_nb<0): continue
                    for second_idx in range(-1,2):
                        col_nb = col+second_idx
                        if(col_nb>15 or col_nb<0): continue
                        if(col_nb==col and row_nb == row): continue
                        i2c_conn.disable_pixel(row=row_nb, col=col_nb, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        else:
            i2c_conn.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=False, triggerWindow=False, cbWindow=True, power_mode=power_mode)
        del IPC_queue, process, parser
    if(allon):
        for first_idx in tqdm(range(16), leave=False):
            for second_idx in range(16):
                i2c_conn.disable_pixel(row=first_idx, col=second_idx, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)

def trigger_bit_noisescan_plot(i2c_conn, chip_address, chip_figtitle, chip_figname, scan_list, attempt='', today='', autoBL=False, gaus=True, tag=''):
    root = '../ETROC-Data'
    file_pattern = "*FPGA_Data.dat"
    scan_name = chip_figname+"_VRef_SCurve_NoiseOnly"
    if(autoBL): BL_map_THCal,NW_map_THCal,_,_ = i2c_conn.get_auto_cal_maps(chip_address)
    triggerbit_full_Scurve = {row:{col:{} for col in range(16)} for row in range(16)}

    if(today==''): today = datetime.date.today().isoformat()
    todaystr = root+"/" + today + "_Array_Test_Results/"
    base_dir = Path(todaystr)
    base_dir.mkdir(exist_ok=True)

    fig_outdir = Path('../ETROC-figures')
    fig_outdir = fig_outdir / (today + '_Array_Test_Results')
    fig_outdir.mkdir(exist_ok=True)
    fig_path = str(fig_outdir)

    for row,col in scan_list:
        path_pattern = f"*{today}_Array_Test_Results/{scan_name}_Pixel_C{col}_R{row}"+attempt
        file_list = []
        for path, subdirs, files in os.walk(root):
            if not fnmatch(path, path_pattern): continue
            for name in files:
                pass
                if fnmatch(name, file_pattern):
                    file_list.append(os.path.join(path, name))
        for file_index, file_name in enumerate(file_list):
            with open(file_name) as infile:
                for line in infile:
                    text_list = line.split(',')
                    FPGA_triggerbit = int(text_list[5])
                    DAC = int(text_list[-1])
                    if DAC == -1: continue
                    triggerbit_full_Scurve[row][col][DAC] = FPGA_triggerbit
    row_list, col_list = zip(*scan_list)
    u_cl = np.sort(np.unique(col_list))
    u_rl = np.sort(np.unique(row_list))

    fig = plt.figure(dpi=200, figsize=(len(np.unique(u_cl))*16,len(np.unique(u_rl))*10))
    gs = fig.add_gridspec(len(np.unique(u_rl)),len(np.unique(u_cl)))
    for ri,row in enumerate(u_rl):
        for ci,col in enumerate(u_cl):
            Y = np.array(list(triggerbit_full_Scurve[row][col].values()))
            X = np.array(list(triggerbit_full_Scurve[row][col].keys()))
            ax0 = fig.add_subplot(gs[len(u_rl)-ri-1,len(u_cl)-ci-1])
            ax0.plot(X, Y, '.-', color='b',lw=1.0)
            ax0.set_xlabel("DAC Value [decimal]")
            ax0.set_ylabel("Trigger Bit Counts [decimal]")
            hep.cms.text(loc=0, ax=ax0, text="Preliminary", fontsize=25)
            max_y_point = np.amax(Y)
            max_x_point = X[np.argmax(Y)]
            fwhm_key_array  = X[Y>.0000037*max_y_point]
            fwhm_val_array  = Y[Y>.0000037*max_y_point]
            left_index  = np.argmin(np.where(Y>.0000037*max_y_point,X,np.inf))-1
            right_index = np.argmax(np.where(Y>.0000037*max_y_point,X,-np.inf))+1
            ax0.set_xlim(left=max_x_point-20, right=max_x_point+20)
            if(gaus):
                ax0.plot([max_x_point, max_x_point], [0, max_y_point], 'w-', label=f"Max at {max_x_point}", lw=0.7)
                ax0.plot([X[left_index], X[right_index]], [Y[left_index], Y[right_index]], color='w', ls='--', label=f"99.9996% width = {(X[right_index]-X[left_index])/2.}", lw=0.7)
            if(autoBL):
                ax0.axvline(BL_map_THCal[row][col], color='k', label=f"AutoBL = {BL_map_THCal[row][col]}", lw=0.7)
                ax0.axvline(BL_map_THCal[row][col]+NW_map_THCal[row][col], color='k', ls='--', label=f"AutoNW = $\pm${NW_map_THCal[row][col]}", lw=0.7)
                ax0.axvline(BL_map_THCal[row][col]-NW_map_THCal[row][col], color='k', ls='--', lw=0.7)
            if(gaus or autoBL): plt.legend(loc="upper right", fontsize=20)
            plt.yscale("log")
            plt.title(f"{chip_figtitle}, Pixel ({row},{col}) Noise Peak"+tag,size=25, loc="right")
            plt.tight_layout()
    plt.savefig(fig_path+"/"+chip_figname+"_NoisePeak_Log"+attempt+"_"+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")+".png")
    plt.close()

    fig = plt.figure(dpi=200, figsize=(len(np.unique(u_cl))*16,len(np.unique(u_rl))*10))
    gs = fig.add_gridspec(len(np.unique(u_rl)),len(np.unique(u_cl)))
    for ri,row in enumerate(u_rl):
        for ci,col in enumerate(u_cl):
            Y = np.array(list(triggerbit_full_Scurve[row][col].values()))
            X = np.array(list(triggerbit_full_Scurve[row][col].keys()))
            ax0 = fig.add_subplot(gs[len(u_rl)-ri-1,len(u_cl)-ci-1])
            ax0.plot(X, Y, '.-', color='b',lw=1.0)
            ax0.set_xlabel("DAC Value [decimal]")
            ax0.set_ylabel("Trigger Bit Counts [decimal]")
            hep.cms.text(loc=1, ax=ax0, text="Preliminary", fontsize=25)
            max_y_point = np.amax(Y)
            max_x_point = X[np.argmax(Y)]
            fwhm_key_array  = X[Y>.0000037*max_y_point]
            fwhm_val_array  = Y[Y>.0000037*max_y_point]
            left_index  = np.argmin(np.where(Y>.0000037*max_y_point,X,np.inf))-1
            right_index = np.argmax(np.where(Y>.0000037*max_y_point,X,-np.inf))+1
            ax0.set_xlim(left=max_x_point-20, right=max_x_point+20)
            if(gaus):
                ax0.plot([max_x_point, max_x_point], [0, max_y_point], 'w-', label=f"Max at {max_x_point}", lw=0.7)
                ax0.plot([X[left_index], X[right_index]], [Y[left_index], Y[right_index]], color='w', ls='--', label=f"99.9996% width = {(X[right_index]-X[left_index])/2.}", lw=0.7)
            if(autoBL):
                ax0.axvline(BL_map_THCal[row][col], color='k', label=f"AutoBL = {BL_map_THCal[row][col]}", lw=0.7)
                ax0.axvline(BL_map_THCal[row][col]+NW_map_THCal[row][col], color='k', ls='--', label=f"AutoNW = $\pm${NW_map_THCal[row][col]}", lw=0.7)
                ax0.axvline(BL_map_THCal[row][col]-NW_map_THCal[row][col], color='k', ls='--', lw=0.7)
            if(gaus or autoBL): plt.legend(loc="upper right", fontsize=20)
            plt.yscale("linear")
            plt.title(f"{chip_figtitle}, Pixel ({row},{col}) Noise Peak"+tag,size=25, loc="right")
            plt.tight_layout()
    plt.savefig(fig_path+"/"+chip_figname+"_NoisePeak_Linear"+attempt+"_"+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")+".png")
    plt.close()
    del triggerbit_full_Scurve

def multiple_trigger_bit_noisescan_plot(i2c_conn, chip_address, chip_figtitle, chip_figname, scan_list, attempts=[], today='', autoBL=False, gaus=True, tags=[], colors = ['k']):
    root = '../ETROC-Data'
    file_pattern = "*FPGA_Data.dat"
    scan_name = chip_figname+"_VRef_SCurve_NoiseOnly"
    if(autoBL): BL_map_THCal,NW_map_THCal,_,_ = i2c_conn.get_auto_cal_maps(chip_address)
    # triggerbit_full_Scurve = {row:{col:{} for col in range(16)} for row in range(16)}
    triggerbit_full_Scurve = {row:{col:{attempt:{} for attempt in attempts} for col in range(16)} for row in range(16)}

    if(today==''): today = datetime.date.today().isoformat()
    todaystr = root+"/" + today + "_Array_Test_Results/"
    base_dir = Path(todaystr)
    base_dir.mkdir(exist_ok=True)

    fig_outdir = Path('../ETROC-figures')
    fig_outdir = fig_outdir / (today + '_Array_Test_Results')
    fig_outdir.mkdir(exist_ok=True)
    fig_path = str(fig_outdir)

    row_list, col_list = zip(*scan_list)
    u_cl = np.sort(np.unique(col_list))
    u_rl = np.sort(np.unique(row_list))

    for row,col in scan_list:
        for attempt in attempts:
            path_pattern = f"*_Array_Test_Results/{scan_name}_Pixel_C{col}_R{row}"+attempt
            file_list = []
            for path, subdirs, files in os.walk(root):
                if not fnmatch(path, path_pattern): continue
                for name in files:
                    pass
                    if fnmatch(name, file_pattern):
                        file_list.append(os.path.join(path, name))
            for file_index, file_name in enumerate(file_list):
                with open(file_name) as infile:
                    for line in infile:
                        text_list = line.split(',')
                        FPGA_triggerbit = int(text_list[5])
                        DAC = int(text_list[-1])
                        if DAC == -1: continue
                        triggerbit_full_Scurve[row][col][attempt][DAC] = FPGA_triggerbit

    old_min_x_point = 1000
    # old_min_y_point = 0
    old_max_x_point = 0
    # old_max_y_point = 0
    fig = plt.figure(dpi=200, figsize=(len(np.unique(u_cl))*16,len(np.unique(u_rl))*10))
    gs = fig.add_gridspec(len(np.unique(u_rl)),len(np.unique(u_cl)))
    for ri,row in enumerate(u_rl):
        for ci,col in enumerate(u_cl):
            ax0 = fig.add_subplot(gs[len(u_rl)-ri-1,len(u_cl)-ci-1])
            for attempt, tag, color in zip(attempts, tags, colors):
                Y = np.array(list(triggerbit_full_Scurve[row][col][attempt].values()))
                X = np.array(list(triggerbit_full_Scurve[row][col][attempt].keys()))
                ax0.plot(X, Y, '.-', color=color,lw=1.0,label=tag)
                ax0.set_xlabel("DAC Value [decimal]")
                ax0.set_ylabel("Trigger Bit Counts [decimal]")
                hep.cms.text(loc=0, ax=ax0, text="Preliminary", fontsize=25)
                # min_y_point = np.amin(Y)
                min_x_point = X[np.argmin(Y)]
                max_y_point = np.amax(Y)
                max_x_point = X[np.argmax(Y)]
                if(old_max_x_point > max_x_point):
                    max_x_point = old_max_x_point
                # if(old_max_y_point > max_y_point):
                #     max_y_point = old_max_y_point
                if(old_min_x_point < min_x_point):
                    min_x_point = old_min_x_point
                # if(old_min_y_point < min_y_point):
                #     min_y_point = old_min_y_point
                fwhm_key_array  = X[Y>.0000037*max_y_point]
                fwhm_val_array  = Y[Y>.0000037*max_y_point]
                left_index  = np.argmin(np.where(Y>.0000037*max_y_point,X,np.inf))-1
                right_index = np.argmax(np.where(Y>.0000037*max_y_point,X,-np.inf))+1
                ax0.set_xlim(left=min_x_point-20, right=max_x_point+20)
                if(gaus):
                    ax0.plot([max_x_point, max_x_point], [0, max_y_point], 'w-', label=f"Max at {max_x_point}", lw=0.7)
                    ax0.plot([X[left_index], X[right_index]], [Y[left_index], Y[right_index]], color=color, ls='--', label=f"99.9996% width = {(X[right_index]-X[left_index])/2.}", lw=0.7)
                if(autoBL):
                    ax0.axvline(BL_map_THCal[row][col], color=color, label=f"AutoBL = {BL_map_THCal[row][col]}", lw=0.7)
                    ax0.axvline(BL_map_THCal[row][col]+NW_map_THCal[row][col], color=color, ls='--', label=f"AutoNW = $\pm${NW_map_THCal[row][col]}", lw=0.7)
                    ax0.axvline(BL_map_THCal[row][col]-NW_map_THCal[row][col], color=color, ls='--', lw=0.7)
                if(gaus or autoBL): plt.legend(loc="upper right", fontsize=20)
                plt.yscale("log")
                plt.title(f"{chip_figtitle}, Pixel ({row},{col}) Noise Peak"+tag,size=25, loc="right")
                plt.tight_layout()
                plt.legend(loc="lower left", fontsize=14)
    plt.savefig(fig_path+"/"+chip_figname+"_NoisePeak_Log"+attempts[0]+"_multiple_"+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")+".png")
    plt.close()

    old_min_x_point = 1000
    # old_min_y_point = 0
    old_max_x_point = 0
    # old_max_y_point = 0
    fig = plt.figure(dpi=200, figsize=(len(np.unique(u_cl))*16,len(np.unique(u_rl))*10))
    gs = fig.add_gridspec(len(np.unique(u_rl)),len(np.unique(u_cl)))
    for ri,row in enumerate(u_rl):
        for ci,col in enumerate(u_cl):
            ax0 = fig.add_subplot(gs[len(u_rl)-ri-1,len(u_cl)-ci-1])
            for attempt, tag, color in zip(attempts, tags, colors):
                Y = np.array(list(triggerbit_full_Scurve[row][col][attempt].values()))
                X = np.array(list(triggerbit_full_Scurve[row][col][attempt].keys()))
                ax0.plot(X, Y, '.-', color=color,lw=1.0,label=tag)
                ax0.set_xlabel("DAC Value [decimal]")
                ax0.set_ylabel("Trigger Bit Counts [decimal]")
                hep.cms.text(loc=1, ax=ax0, text="Preliminary", fontsize=25)
                # min_y_point = np.amin(Y)
                min_x_point = X[np.argmin(Y)]
                max_y_point = np.amax(Y)
                max_x_point = X[np.argmax(Y)]
                if(old_max_x_point > max_x_point):
                    max_x_point = old_max_x_point
                # if(old_max_y_point > max_y_point):
                #     max_y_point = old_max_y_point
                if(old_min_x_point < min_x_point):
                    min_x_point = old_min_x_point
                # if(old_min_y_point < min_y_point):
                #     min_y_point = old_min_y_point
                fwhm_key_array  = X[Y>.0000037*max_y_point]
                fwhm_val_array  = Y[Y>.0000037*max_y_point]
                left_index  = np.argmin(np.where(Y>.0000037*max_y_point,X,np.inf))-1
                right_index = np.argmax(np.where(Y>.0000037*max_y_point,X,-np.inf))+1
                ax0.set_xlim(left=min_x_point-20, right=max_x_point+20)
                if(gaus):
                    ax0.plot([max_x_point, max_x_point], [0, max_y_point], 'w-', label=f"Max at {max_x_point}", lw=0.7)
                    ax0.plot([X[left_index], X[right_index]], [Y[left_index], Y[right_index]], color=color, ls='--', label=f"99.9996% width = {(X[right_index]-X[left_index])/2.}", lw=0.7)
                if(autoBL):
                    ax0.axvline(BL_map_THCal[row][col], color=color, label=f"AutoBL = {BL_map_THCal[row][col]}", lw=0.7)
                    ax0.axvline(BL_map_THCal[row][col]+NW_map_THCal[row][col], color=color, ls='--', label=f"AutoNW = $\pm${NW_map_THCal[row][col]}", lw=0.7)
                    ax0.axvline(BL_map_THCal[row][col]-NW_map_THCal[row][col], color=color, ls='--', lw=0.7)
                if(gaus or autoBL): plt.legend(loc="upper right", fontsize=20)
                plt.yscale("linear")
                plt.title(f"{chip_figtitle}, Pixel ({row},{col}) Noise Peak"+tag,size=25, loc="right")
                plt.tight_layout()
            plt.legend(loc="lower left", fontsize=14)
    plt.savefig(fig_path+"/"+chip_figname+"_NoisePeak_Linear"+attempts[0]+"_multiple_"+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")+".png")
    plt.close()
    del triggerbit_full_Scurve


def pixel_turnoff_points(i2c_conn, chip_address, chip_figname, s_flag, d_flag, a_flag, p_flag, scan_list, verbose=False, QInjEns=[27], attempt='', today='', calibrate=False, hostname = "192.168.2.3", power_mode='high', triggerbit=True):
    if power_mode not in valid_power_modes:
        power_mode = 'low'
    DAC_scan_max = 1020
    scan_name = chip_figname+"_VRef_SCurve_BinarySearch_TurnOff"
    fpga_time = 3

    if(today==''): today = datetime.date.today().isoformat()
    todaystr = "../ETROC-Data/" + today + "_Array_Test_Results/"
    base_dir = Path(todaystr)
    base_dir.mkdir(exist_ok=True)

    chip = i2c_conn.get_chip_i2c_connection(chip_address)
    row_indexer_handle,_,_ = chip.get_indexer("row")
    column_indexer_handle,_,_ = chip.get_indexer("column")

    BL_map_THCal,_,_,_ = i2c_conn.get_auto_cal_maps(chip_address)
    for row, col in scan_list:
        if(calibrate):
            i2c_conn.auto_cal_pixel(chip_name=chip_figname, row=row, col=col, verbose=False, chip_address=chip_address, chip=chip, data=None, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
            # i2c_conn.disable_pixel(row, col, verbose=False, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        i2c_conn.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=True, Bypass_THCal=True, triggerWindow=True, cbWindow=True, power_mode=power_mode)
        row_indexer_handle.set(row)
        column_indexer_handle.set(col)
        for QInj in tqdm(QInjEns, desc=f'QInj Loop for Chip {hex(chip_address)} Pixel ({row},{col})', leave=False):
            i2c_conn.pixel_decoded_register_write("QSel", format(QInj, '05b'), chip=chip)
            threshold_name = scan_name+f'_Pixel_C{col}_R{row}_QInj_{QInj}'+attempt
            parser = parser_arguments.create_parser()
            (options, args) = parser.parse_args(args=f"-f --useIPC --hostname {hostname} -o {threshold_name} -v -w -s {s_flag} -d {d_flag} -a {a_flag} -p {p_flag} --counter_duration 0x0001 --fpga_data_time_limit {int(fpga_time)} --fpga_data_QInj --nodaq".split())
            IPC_queue = multiprocessing.Queue()
            process = multiprocessing.Process(target=run_script.main_process, args=(IPC_queue, options, f'process_outputs/main_process_link'))
            process.start()
            process.join()

            a = BL_map_THCal[row][col]
            b = DAC_scan_max
            header_max = -1
            while b-a>1:
                DAC = int(np.floor((a+b)/2.0))
                # Set the DAC to the value being scanned
                i2c_conn.pixel_decoded_register_write("DAC", format(DAC, '010b'), chip=chip)
                (options, args) = parser.parse_args(args=f"--useIPC --hostname {hostname} -o {threshold_name} -v --counter_duration 0x0001 --fpga_data_time_limit {int(fpga_time)} --fpga_data_QInj --nodaq --DAC_Val {DAC}".split())
                IPC_queue = multiprocessing.Queue()
                process = multiprocessing.Process(target=run_script.main_process, args=(IPC_queue, options, f'process_outputs/main_process_{QInj}_{DAC}'))
                process.start()
                process.join()

                continue_flag = False
                root = '../ETROC-Data'
                file_pattern = "*FPGA_Data.dat"
                path_pattern = f"*{today}_Array_Test_Results/{threshold_name}"
                file_list = []
                for path, subdirs, files in os.walk(root):
                    if not fnmatch(path, path_pattern): continue
                    for name in files:
                        pass
                        if fnmatch(name, file_pattern):
                            file_list.append(os.path.join(path, name))
                for file_index, file_name in enumerate(file_list):
                    with open(file_name) as infile:
                        lines = infile.readlines()
                        last_line = lines[-1]
                        first_line = lines[0]
                        header_max = int(first_line.split(',')[4])
                        text_list = last_line.split(',')
                        FPGA_state = text_list[0]
                        line_DAC = int(text_list[-1])
                        # if(FPGA_state==0 or line_DAC!=DAC):
                        if(FPGA_state==0 or line_DAC==-1):
                            continue_flag=True
                            continue
                        # Condition handling for Binary Search
                        # TDC_data = int(text_list[3])
                        # if(TDC_data>=header_max/2.):
                        if(triggerbit):
                            Triggerbits = int(text_list[-2])
                        else:
                            Triggerbits = int(text_list[3])
                        # print(a,b,header_max,Triggerbits,Triggerbits>=(header_max/2.),line_DAC)
                        if(Triggerbits>=(header_max/2.)):
                            a = DAC
                        else:
                            b = DAC
                if(continue_flag): continue
        i2c_conn.disable_pixel(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        if(verbose): print(f"Turn-Off points for Pixel ({row},{col}) for chip {hex(chip_address)} were found")
        del parser, IPC_queue, process

def charge_peakDAC_plot(i2c_conn, chip_address, chip_figtitle, chip_figname, scan_list, QInjEns, attempt='', today='', tag=''):
    root = '../ETROC-Data'
    file_pattern = "*FPGA_Data.dat"
    scan_name = chip_figname+"_VRef_SCurve_BinarySearch_TurnOff"
    BL_map_THCal,NW_map_THCal,_,_ = i2c_conn.get_auto_cal_maps(chip_address)
    QInj_Peak_DAC_map = {row:{col:{q:0 for q in QInjEns} for col in range(16)} for row in range(16)}

    if(today==''): today = datetime.date.today().isoformat()
    todaystr = root+"/" + today + "_Array_Test_Results/"
    base_dir = Path(todaystr)
    base_dir.mkdir(exist_ok=True)

    fig_outdir = Path('../ETROC-figures')
    fig_outdir = fig_outdir / (today + '_Array_Test_Results')
    fig_outdir.mkdir(exist_ok=True)
    fig_path = str(fig_outdir)

    for row,col in scan_list:
        for QInj in QInjEns:
            threshold_name = scan_name+f'_Pixel_C{col}_R{row}_QInj_{QInj}'+attempt
            path_pattern = f"*{today}_Array_Test_Results/{threshold_name}"
            file_list = []
            for path, subdirs, files in os.walk(root):
                if not fnmatch(path, path_pattern): continue
                for name in files:
                    pass
                    if fnmatch(name, file_pattern):
                        file_list.append(os.path.join(path, name))
            for file_index, file_name in enumerate(file_list):
                with open(file_name) as infile:
                    last_line = infile.readlines()[-1]
                    text_list = last_line.split(',')
                    DAC = int(text_list[-1])
                    QInj_Peak_DAC_map[row][col][QInj] = DAC

    row_list, col_list = zip(*scan_list)
    u_cl = np.sort(np.unique(col_list))
    u_rl = np.sort(np.unique(row_list))
    fig = plt.figure(dpi=200, figsize=(len(np.unique(u_cl))*16,len(np.unique(u_rl))*10))
    gs = fig.add_gridspec(len(np.unique(u_rl)),len(np.unique(u_cl)))
    for ri,row in enumerate(u_rl):
        for ci,col in enumerate(u_cl):
            BL = int(np.floor(BL_map_THCal[row][col]))
            NW = abs(int(np.floor(NW_map_THCal[row][col])))
            ax0 = fig.add_subplot(gs[len(u_rl)-ri-1,len(u_cl)-ci-1])
            ax0.axhline(BL, color='k', lw=0.8, label=f"BL = {BL} DAC LSB")
            ax0.axhline(BL+NW, color='k',ls="--", lw=0.8, label=f"NW = $\pm${NW} DAC LSB")
            ax0.axhline(BL-NW, color='k',ls="--", lw=0.8)
            X = []
            Y = []
            for QInj in QInjEns:
                ax0.plot(QInj, QInj_Peak_DAC_map[row][col][QInj], 'rx')
                X.append(QInj)
                Y.append(QInj_Peak_DAC_map[row][col][QInj])
            X = np.array(X[:])
            Y = np.array(Y[:])
            (m, b), cov = np.polyfit(X, Y, 1, cov = True)
            n = Y.size
            Yfit = np.polyval((m,b), X)
            errorbars = np.sqrt(np.diag(cov))
            x_range = np.linspace(0, 35, 100)
            y_est = b + m*x_range
            resid = Y - Yfit
            s_err = np.sqrt(np.sum(resid**2)/(n - 2))
            t = stats.t.ppf(0.95, n - 2)
            ci2= t * s_err * np.sqrt(    1/n + (x_range - np.mean(X))**2/(np.sum((X)**2)-n*np.sum((np.mean(X))**2)))

            ax0.plot(x_range, y_est, 'b-', lw=-.8, label=f"DAC_TH = ({m:.2f}$\pm${errorbars[0]:.2f})$\cdot$Q + ({b:.2f}$\pm${errorbars[1]:.2f})")
            plt.fill_between(x_range, y_est+ci2, y_est-ci2, color='b',alpha=0.2, label="95% Confidence Interval on Linear Fit")
            ax0.set_xlabel("Charge Injected [fC]")
            ax0.set_ylabel("DAC Threshold [LSB]")
            hep.cms.text(loc=0, ax=ax0, text="Preliminary", fontsize=25)
            plt.title(f"{chip_figtitle}, Pixel ({row},{col}) Qinj Sensitivity Plot"+tag, size=25, loc='right')
            plt.legend(loc=(0.04,0.65))
            plt.tight_layout()
    plt.savefig(fig_path+"/"+chip_figname+"_QInj_Sensitivity"+attempt+"_"+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")+".png")
    plt.close()
    del QInj_Peak_DAC_map

def run_daq(timePerPixel, deadTime, dirname, s_flag, d_flag, a_flag, p_flag, today="test", hostname = "192.168.2.3", run_options="--compressed_translation --skip_binary", ssd_path = "/run/media/daq/T7/"):

    total_scan_time = timePerPixel + deadTime

    parser = parser_arguments.create_parser()
    (options, args) = parser.parse_args(args=f"-f --useIPC --hostname {hostname} -t {int(total_scan_time)} -o {dirname} -v -w -s {s_flag} -p {p_flag} -d {d_flag} -a {a_flag} --start_DAQ_pulse --stop_DAQ_pulse --check_valid_data_start {run_options} --ssd_path {ssd_path} --run_name {today}".split())
    IPC_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=run_script.main_process, args=(IPC_queue, options, f'main_process'))
    process.start()

    IPC_queue.put('memoFC Start Triggerbit QInj L1A')
    while not IPC_queue.empty():
        pass
    time.sleep(timePerPixel)
    IPC_queue.put('stop DAQ')
    IPC_queue.put('memoFC Triggerbit')
    while not IPC_queue.empty():
        pass
    IPC_queue.put('allow threads to exit')

    process.join()

def full_scurve_scan(i2c_conn, chip_address, chip_figname, s_flag, d_flag, a_flag, p_flag, scan_list, verbose=False, QInjEns=[27], pedestal_scan_step=1, attempt='', tp_tag='', today='', allon=False, neighbors=False, hostname = "192.168.2.3", power_mode="high", upperlimit_turnoff=-1,timePerPixel=2, deadTime=1, run_options="--compressed_translation --skip_binary", ssd_path = "", BL_offset=5):
    if(ssd_path==""):
        root = '../ETROC-Data'
    else:
        root = ssd_path
    file_pattern = "*FPGA_Data.dat"
    scan_name = chip_figname+"_VRef_SCurve_TDC"
    BL_map_THCal,NW_map_THCal,_,_ = i2c_conn.get_auto_cal_maps(chip_address)

    if(today==''): today = datetime.date.today().isoformat()
    todaystub = today + "_Array_Test_Results"
    todaystr = root+"/" + today + "_Array_Test_Results/"
    base_dir = Path(todaystr)
    base_dir.mkdir(exist_ok=True)

    chip = i2c_conn.get_chip_i2c_connection(chip_address)
    row_indexer_handle,_,_ = chip.get_indexer("row")
    column_indexer_handle,_,_ = chip.get_indexer("column")

    if(allon):
        for first_idx in tqdm(range(16), leave=False):
            for second_idx in range(16):
                i2c_conn.enable_pixel_modular(row=first_idx, col=second_idx, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=False, triggerWindow=True, cbWindow=False, power_mode=power_mode)

    for row,col in scan_list:
        i2c_conn.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=True, Bypass_THCal=True, triggerWindow=True, cbWindow=True, power_mode=power_mode)
        if(neighbors and (not allon)):
            for first_idx in range(-1,2):
                row_nb = row+first_idx
                if(row_nb>15 or row_nb<0): continue
                for second_idx in range(-1,2):
                    col_nb = col+second_idx
                    if(col_nb>15 or col_nb<0): continue
                    if(col_nb==col and row_nb == row): continue
                    i2c_conn.enable_pixel_modular(row=row_nb, col=col_nb, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=False, triggerWindow=True, cbWindow=False, power_mode=power_mode)
        row_indexer_handle.set(row)
        column_indexer_handle.set(col)
        # for QInj in tqdm(QInjEns, desc=f'QInj Loop for Chip {hex(chip_address)} Pixel ({row},{col})', leave=False):
        for QInj in QInjEns:
            turning_point = -1
            path_pattern = f"*{today}_Array_Test_Results/"+chip_figname+"_VRef_SCurve_BinarySearch_TurnOff"+f'_Pixel_C{col}_R{row}_QInj_{QInj}'+tp_tag
            file_list = []
            for path, subdirs, files in os.walk(root):
                if not fnmatch(path, path_pattern): continue
                for name in files:
                    pass
                    if fnmatch(name, file_pattern):
                        file_list.append(os.path.join(path, name))
            for file_index, file_name in enumerate(file_list):
                with open(file_name) as infile:
                    last_line = infile.readlines()[-1]
                    text_list = last_line.split(',')
                    DAC = int(text_list[-1])
                    turning_point = DAC
            if(isinstance(upperlimit_turnoff,int) and upperlimit_turnoff>0):
                if(turning_point>1000): turning_point = upperlimit_turnoff
            if(isinstance(upperlimit_turnoff,dict)):
                if(turning_point>1000): turning_point = upperlimit_turnoff[QInj]
            # thresholds = np.arange(BL_map_THCal[row][col]+NW_map_THCal[row][col],turning_point,pedestal_scan_step)
            thresholds = np.arange(BL_map_THCal[row][col]+BL_offset,turning_point,pedestal_scan_step)
            i2c_conn.pixel_decoded_register_write("QSel", format(QInj, '05b'), chip)
            # print("Before DAQ loop", thresholds)
            for DAC in tqdm(thresholds, desc=f'DAC Loop for Pixel ({col},{row}) & Charge {QInj} fC', leave=False):
                threshold = int(DAC)
                if threshold < 1:
                    threshold = 1
                # Set the DAC v, Qinj {Qinj}fCalue to the value being scanned
                i2c_conn.pixel_decoded_register_write("DAC", format(threshold, '010b'), chip=chip)
                # TH = i2c_conn.pixel_decoded_register_read("TH", "Status", pixel_connected_chip, need_int=True)
                threshold_name = scan_name+f'_Pixel_C{col}_R{row}_QInj_{QInj}_Threshold_{threshold}'+attempt
                run_daq(timePerPixel=timePerPixel, deadTime=deadTime, dirname=threshold_name, today=todaystub, s_flag=s_flag, d_flag=d_flag, a_flag=a_flag, p_flag=p_flag, hostname=hostname,run_options=run_options, ssd_path=os.path.abspath(Path(root)))

        # Disable
        if(not allon):
            i2c_conn.disable_pixel(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
            if(neighbors):
                for first_idx in range(-1,2):
                    row_nb = row+first_idx
                    if(row_nb>15 or row_nb<0): continue
                    for second_idx in range(-1,2):
                        col_nb = col+second_idx
                        if(col_nb>15 or col_nb<0): continue
                        if(col_nb==col and row_nb == row): continue
                        i2c_conn.disable_pixel(row=row_nb, col=col_nb, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)
        else:
            i2c_conn.enable_pixel_modular(row=row, col=col, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle, QInjEn=False, Bypass_THCal=False, triggerWindow=True, cbWindow=False, power_mode=power_mode)
    if(allon):
        for first_idx in tqdm(range(16), leave=False):
            for second_idx in range(16):
                i2c_conn.disable_pixel(row=first_idx, col=second_idx, verbose=verbose, chip_address=chip_address, chip=chip, row_indexer_handle=row_indexer_handle, column_indexer_handle=column_indexer_handle)

def return_empty_list(QInjEns, scan_list):
    return {(row,col,q):{} for q in QInjEns for row,col in scan_list}

def make_scurve_plot(QInjEns, scan_list, array, chip_figtitle, chip_figname, y_label="[LSB]", save_name='', isStd=False, fig_path=''):
    colors = [plt.cm.viridis(i) for i in np.linspace(0,0.95,len(QInjEns))]
    row_list, col_list = zip(*scan_list)
    u_cl = np.sort(np.unique(col_list))
    u_rl = np.sort(np.unique(row_list))
    fig = plt.figure(dpi=200, figsize=(len(np.unique(u_cl))*16,len(np.unique(u_rl))*10))
    gs = fig.add_gridspec(len(np.unique(u_rl)),len(np.unique(u_cl)))
    for ri,row in enumerate(u_rl):
        for ci,col in enumerate(u_cl):
            ax0 = fig.add_subplot(gs[len(u_rl)-ri-1,len(u_cl)-ci-1])
            for i, QInj in enumerate(QInjEns):
                ax0.plot(array[row, col, QInj].keys(), np.array(list(array[row, col, QInj].values())), '.-', label=f"{QInj} fC", color=colors[i],lw=1)
            if(isStd):
                # ax0.axhline(0.5, color='k', ls='--', label="0.5 LSB", lw=0.5)
                # ax0.set_ylim(top=10.0, bottom=0)
                pass
            ax0.set_xlabel("DAC Value [LSB]")
            ax0.set_ylabel(y_label)
            plt.grid()
            hep.cms.text(loc=0, ax=ax0, text="Preliminary", fontsize=25)
            plt.title(f"{chip_figtitle}, Pixel ({row},{col}) QInj S-Curve",size=25, loc="right")
            plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(fig_path+"/"+chip_figname+save_name+"_"+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")+".png")
    plt.close()

def process_scurves(chip_figtitle, chip_figname, QInjEns, scan_list, today='',attempt=""):
    if(today==''): today = datetime.date.today().isoformat()
    scan_name = f"*{today}_Array_Test_Results/"+chip_figname+"_VRef_SCurve_TDC"
    root = '../ETROC-Data'
    file_pattern = "*translated_[0-9]*.nem"
    path_pattern = f"*{scan_name}*{attempt}*"
    file_list = []
    for path, subdirs, files in os.walk(root):
        if not fnmatch(path, path_pattern): continue
        for name in files:
            pass
            if fnmatch(name, file_pattern):
                file_list.append(os.path.join(path, name))
                print(file_list[-1])
    hit_counts = return_empty_list(QInjEns, scan_list)
    # hit_counts_exc = return_empty_list(QInjEns, scan_list)
    CAL_sum = return_empty_list(QInjEns, scan_list)
    CAL_sum_sq = return_empty_list(QInjEns, scan_list)
    TOA_sum = return_empty_list(QInjEns, scan_list)
    TOA_sum_sq = return_empty_list(QInjEns, scan_list)
    TOT_sum = return_empty_list(QInjEns, scan_list)
    TOT_sum_sq = return_empty_list(QInjEns, scan_list)
    CAL_mean = return_empty_list(QInjEns, scan_list)
    CAL_std = return_empty_list(QInjEns, scan_list)
    TOA_mean = return_empty_list(QInjEns, scan_list)
    TOA_std = return_empty_list(QInjEns, scan_list)
    TOT_mean = return_empty_list(QInjEns, scan_list)
    TOT_std = return_empty_list(QInjEns, scan_list)
    path_offset = attempt.split("_")
    path_offset = np.array([len(po) for po in path_offset])
    path_offset = len(path_offset[path_offset>0])
    total_files = len(file_list)
    for file_index, file_name in enumerate(file_list):
        col = int(file_name.split('/')[-2].split('_')[-6-path_offset][1:])
        row = int(file_name.split('/')[-2].split('_')[-5-path_offset][1:])
        QInj = int(file_name.split('/')[-2].split('_')[-3-path_offset])
        DAC = int(file_name.split('/')[-2].split('_')[-1-path_offset])
        if((row,col) not in scan_list): continue
        hit_counts[row, col, QInj][DAC] = 0
        # hit_counts_exc[row, col, QInj][DAC] = 0
        CAL_sum[row, col, QInj][DAC] = 0
        CAL_sum_sq[row, col, QInj][DAC] = 0
        TOA_sum[row, col, QInj][DAC] = 0
        TOA_sum_sq[row, col, QInj][DAC] = 0
        TOT_sum[row, col, QInj][DAC] = 0
        TOT_sum_sq[row, col, QInj][DAC] = 0
        CAL_mean[row, col, QInj][DAC] = 0
        CAL_std[row, col, QInj][DAC] = 0
        TOA_mean[row, col, QInj][DAC] = 0
        TOA_std[row, col, QInj][DAC] = 0
        TOT_mean[row, col, QInj][DAC] = 0
        TOT_std[row, col, QInj][DAC] = 0
        with open(file_name) as infile:
            for line in infile:
                text_list = line.split()
                if text_list[0]=="H":
                    current_bcid = int(text_list[4])
                if text_list[0]=="T":
                    previous_bcid = current_bcid
                if text_list[0]!="D": continue
                # col = int(text_list[3])
                # row = int(text_list[4])
                TOA = int(text_list[5])
                TOT = int(text_list[6])
                CAL = int(text_list[7])

                # if(CAL<193 or CAL>196): continue
                hit_counts[row, col, QInj][DAC] += 1
                CAL_sum[row, col, QInj][DAC] += CAL
                CAL_sum_sq[row, col, QInj][DAC] += CAL*CAL
                # hit_counts_exc[row, col, QInj][DAC] += 1
                TOA_sum[row, col, QInj][DAC] += TOA
                TOA_sum_sq[row, col, QInj][DAC] += TOA*TOA
                TOT_sum[row, col, QInj][DAC] += TOT
                TOT_sum_sq[row, col, QInj][DAC] += TOT*TOT

    for row, col, QInj in hit_counts:
        for DAC in hit_counts[row, col, QInj]:
            if(hit_counts[row, col, QInj][DAC]==0):
                CAL_mean[row, col, QInj].pop(DAC)
                CAL_std[row, col, QInj].pop(DAC)
                TOA_mean[row, col, QInj].pop(DAC)
                TOA_std[row, col, QInj].pop(DAC)
                TOT_mean[row, col, QInj].pop(DAC)
                TOT_std[row, col, QInj].pop(DAC)
                continue
            CAL_mean[row, col, QInj][DAC] = CAL_sum[row, col, QInj][DAC]/hit_counts[row, col, QInj][DAC]
            CAL_std[row, col, QInj][DAC] = np.sqrt((CAL_sum_sq[row, col, QInj][DAC]/hit_counts[row, col, QInj][DAC]) - pow(CAL_mean[row, col, QInj][DAC], 2))
            # if(CAL_std[row, col, QInj][DAC]<2):
            TOA_mean[row, col, QInj][DAC] = TOA_sum[row, col, QInj][DAC]/hit_counts[row, col, QInj][DAC]
            TOA_std[row, col, QInj][DAC] = np.sqrt((TOA_sum_sq[row, col, QInj][DAC]/hit_counts[row, col, QInj][DAC]) - pow(TOA_mean[row, col, QInj][DAC], 2))
            TOT_mean[row, col, QInj][DAC] = TOT_sum[row, col, QInj][DAC]/hit_counts[row, col, QInj][DAC]
            TOT_std[row, col, QInj][DAC] = np.sqrt((TOT_sum_sq[row, col, QInj][DAC]/hit_counts[row, col, QInj][DAC]) - pow(TOT_mean[row, col, QInj][DAC], 2))
            # else:
            #     TOA_mean[row, col, QInj][DAC] = np.nan
            #     TOA_std[row, col, QInj][DAC] = np.nan
            #     TOT_mean[row, col, QInj][DAC] = np.nan
            #     TOT_std[row, col, QInj][DAC] = np.nan

    fig_outdir = Path('../ETROC-figures')
    fig_outdir = fig_outdir / (today + '_Array_Test_Results')
    fig_outdir.mkdir(exist_ok=True)
    fig_path = str(fig_outdir)

    make_scurve_plot(QInjEns, scan_list, TOA_std, chip_figtitle, chip_figname, y_label="TOA Std [LSB]", save_name='_TOA_STD', isStd=True, fig_path=fig_path)
    make_scurve_plot(QInjEns, scan_list, TOT_std, chip_figtitle, chip_figname, y_label="TOT Std [LSB]", save_name='_TOT_STD', isStd=True, fig_path=fig_path)
    make_scurve_plot(QInjEns, scan_list, CAL_std, chip_figtitle, chip_figname, y_label="CAL Std [LSB]", save_name='_CAL_STD', isStd=True, fig_path=fig_path)
    make_scurve_plot(QInjEns, scan_list, TOA_mean, chip_figtitle, chip_figname, y_label="TOA Mean [LSB]", save_name='_TOA_MEAN', isStd=False, fig_path=fig_path)
    make_scurve_plot(QInjEns, scan_list, TOT_mean, chip_figtitle, chip_figname, y_label="TOT Mean [LSB]", save_name='_TOT_MEAN', isStd=False, fig_path=fig_path)
    make_scurve_plot(QInjEns, scan_list, CAL_mean, chip_figtitle, chip_figname, y_label="CAL Mean [LSB]", save_name='_CAL_MEAN', isStd=False, fig_path=fig_path)

def read_BLNW_history_chips(sqlite_file: Path):
    with sqlite3.connect(sqlite_file) as sqlite3_connection:
        chip_df = pandas.read_sql_query("SELECT chip_name FROM baselines", sqlite3_connection)
        return chip_df.chip_name.unique()

def read_BLNW_history_chip_measurements(sqlite_file: Path, chip_name: str):
    with sqlite3.connect(sqlite_file) as sqlite3_connection:
        timestamp_df = pandas.read_sql_query(f"SELECT timestamp, save_notes FROM baselines WHERE chip_name='{chip_name}' AND ROW=0 AND COL=0", sqlite3_connection)
        max_timestamp_df = pandas.read_sql_query(f"SELECT timestamp FROM baselines WHERE chip_name='{chip_name}' AND ROW=15 AND COL=15", sqlite3_connection)
        timestamp_df['min_timestamp'] = pandas.to_datetime(timestamp_df['timestamp'], format='mixed')
        timestamp_df['max_timestamp'] = pandas.to_datetime(max_timestamp_df['timestamp'], format='mixed')

        return timestamp_df.drop('timestamp', axis=1).copy()

def read_BLNW_history_chip_measurement_df(sqlite_file: Path, chip_name: str, min_timestamp, max_timestamp):
    with sqlite3.connect(sqlite_file) as sqlite3_connection:
        data_df = pandas.read_sql_query(f"SELECT * FROM baselines WHERE chip_name='{chip_name}'", sqlite3_connection)
        data_df['timestamp'] = pandas.to_datetime(data_df['timestamp'], format='mixed')
        data_df = data_df.loc[data_df.timestamp >= min_timestamp]
        data_df = data_df.loc[data_df.timestamp <= max_timestamp]
        return data_df.copy()

def make_BLNW_history_1DNW_plot(data_df: pandas.DataFrame, chip_name, chip_figname, save_note: str, save: bool, fig_dir: Path):
    fig, ax = plt.subplots(figsize=(10, 9))
    hep.cms.text(loc=0, ax=ax, fontsize=17, text="ETL ETROC")
    tmp_hist = hist.Hist(hist.axis.Regular(16, 0, 16, name='nw', label='NW [DAC]'))
    nw_array = data_df['noise_width'].to_numpy().flatten()
    tmp_hist.fill(nw_array)
    mean, std = nw_array.mean(), nw_array.std()
    tmp_hist.plot1d(ax=ax, yerr=False, label=f'Mean: {mean:.2f}, Std: {std:.2f}')
    ax.set_title(f"{chip_figname}: NW (DAC LSB)\n{save_note}", size=17, loc="right")
    ax.legend(fontsize=16)
    plt.xticks(range(16), range(16))

    plt.tight_layout()
    plt.show()

    if save:
        keepcharacters = (' ','.','_')
        save_note_safe = "".join(c for c in save_note if c.isalnum() or c in keepcharacters).rstrip()
        save_note_safe = "_".join(save_note_safe.split())
        fig.savefig(fig_dir / ("NW_1D_"+chip_name+"_"+save_note_safe+".png"))

def make_BLNW_history_2D_plots(data_df: pandas.DataFrame, chip_name, chip_figname, save_note: str, save: bool, fig_dir: Path):
    fig = plt.figure(dpi=200, figsize=(20,10))
    gs = fig.add_gridspec(1,2)

    ax0 = fig.add_subplot(gs[0,0])
    BL_vmin = data_df.baseline.min()
    BL_vmax = data_df.baseline.max()
    NW_vmin = 0
    NW_vmax = 16

    pivot_data_df = data_df.pivot(
        index = ['row'],
        columns = ['col'],
        values = ['baseline', 'noise_width'],
    )

    ax0.set_title(f"{chip_figname}: BL (DAC LSB)\n{save_note}", size=17, loc="right")
    img0 = ax0.imshow(pivot_data_df.baseline, interpolation='none',vmin=BL_vmin,vmax=BL_vmax)
    ax0.set_aspect("equal")
    ax0.invert_xaxis()
    ax0.invert_yaxis()
    plt.xticks(range(16), range(16), rotation="vertical")
    plt.yticks(range(16), range(16))
    hep.cms.text(loc=0, ax=ax0, fontsize=17, text="ETL ETROC")
    divider = make_axes_locatable(ax0)
    cax = divider.append_axes('right', size="5%", pad=0.05)
    fig.colorbar(img0, cax=cax, orientation="vertical")#,boundaries=np.linspace(vmin,vmax,int((vmax-vmin)*30)))

    ax1 = fig.add_subplot(gs[0,1])
    ax1.set_title(f"{chip_figname}: NW (DAC LSB)\n{save_note}", size=17, loc="right")
    img1 = ax1.imshow(pivot_data_df.noise_width, interpolation='none',vmin=NW_vmin,vmax=NW_vmax)
    ax1.set_aspect("equal")
    ax1.invert_xaxis()
    ax1.invert_yaxis()
    plt.xticks(range(16), range(16), rotation="vertical")
    plt.yticks(range(16), range(16))
    hep.cms.text(loc=0, ax=ax1, fontsize=17, text="ETL ETROC")
    divider = make_axes_locatable(ax1)
    cax = divider.append_axes('right', size="5%", pad=0.05)
    fig.colorbar(img1, cax=cax, orientation="vertical")#,boundaries=np.linspace(vmin,vmax,int((vmax-vmin)*5)))

    for col in range(16):
        for row in range(16):
            ax0.text(col,row,f"{pivot_data_df.baseline[col][row]:.0f}", c="white", size=10, rotation=45, fontweight="bold", ha="center", va="center")
            ax1.text(col,row,f"{pivot_data_df.noise_width[col][row]:.0f}", c="white", size=10, rotation=45, fontweight="bold", ha="center", va="center")
    plt.tight_layout()
    plt.show()

    if save:
        keepcharacters = (' ','.','_')
        save_note_safe = "".join(c for c in save_note if c.isalnum() or c in keepcharacters).rstrip()
        save_note_safe = "_".join(save_note_safe.split())
        plt.savefig(fig_dir / ("BL_NW_"+chip_name+"_"+save_note_safe+".png"))

def make_BLNW_history_chip_measurement_plots(sqlite_file: Path, chip_name: str, measurement_idx: int, save: bool = False, save_dir: Path = None, figname_map = {}):
    measurement_df = read_BLNW_history_chip_measurements(sqlite_file, chip_name)
    if measurement_idx >= len(measurement_df) or measurement_idx < 0:
        print("You selected a measurement which does not exist, exiting")
        return
    if save and save_dir is None:
        save = False

    save_note     = measurement_df.save_notes[measurement_idx]
    min_timestamp = measurement_df.min_timestamp[measurement_idx]
    max_timestamp = measurement_df.max_timestamp[measurement_idx]
    chip_figname = chip_name
    if chip_name in figname_map:
        chip_figname = figname_map[chip_name]

    data_df = read_BLNW_history_chip_measurement_df(sqlite_file, chip_name, min_timestamp, max_timestamp)

    make_BLNW_history_2D_plots(data_df, chip_name, chip_figname, save_note, save, save_dir)
    make_BLNW_history_1DNW_plot(data_df, chip_name, chip_figname, save_note, save, save_dir)

def push_history_to_git(
        input_df: pandas.DataFrame,
        note: str,
        git_repo: str,
    ):
    # Store BL, NW dataframe for later use
    new_columns = {
        'note': f'{note}',
    }

    if not os.path.exists(f'/home/{os.getlogin()}/ETROC2/{git_repo}'):
        os.system(f'git clone git@github.com:CMS-ETROC/{git_repo}.git /home/{os.getlogin()}/ETROC2/{git_repo}')

    for col in new_columns:
        input_df[col] = new_columns[col]

    outdir = git_repo
    outfile = outdir / 'BaselineHistory.sqlite'

    init_cmd = [
        'cd ' + str(outdir.resolve()),
        'git stash -u',
        'git pull',
    ]
    end_cmd = [
        'cd ' + str(outdir.resolve()),
        'git add BaselineHistory.sqlite',
        'git commit -m "Added new history entry"',
        'git push',
        'git stash pop',
        'git stash clear',
    ]
    init_cmd = [x + '\n' for x in init_cmd]
    end_cmd  = [x + '\n' for x in end_cmd]

    p = subprocess.Popen(
        '/bin/bash',
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        )

    for cmd in init_cmd:
        p.stdin.write(cmd + "\n")
    p.stdin.close()
    p.wait()
    print(p.stdout.read())

    with sqlite3.connect(outfile) as sqlconn:
        input_df.to_sql('baselines', sqlconn, if_exists='append', index=False)

    p = subprocess.Popen(
        '/bin/bash',
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        )

    for cmd in end_cmd:
        p.stdin.write(cmd + "\n")
    p.stdin.close()
    p.wait()

    p.stdin.close()
    print(p.stdout.read())

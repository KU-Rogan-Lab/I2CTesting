# %%
#############################################################################
# zlib License
#
# (C) 2023 Zach Flowers, Murtaza Safdari <musafdar@cern.ch>
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

# %% [markdown]
# # Imports

# %%
#%%
%matplotlib inline
import matplotlib.pyplot as plt
import logging
import i2c_gui
import i2c_gui.chips
from i2c_gui.usb_iss_helper import USB_ISS_Helper
from i2c_gui.fpga_eth_helper import FPGA_ETH_Helper
import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable
# import time
from tqdm import tqdm
# from i2c_gui.chips.etroc2_chip import register_decoding
import os, sys
import multiprocessing
os.chdir(f'/home/{os.getlogin()}/ETROC2/ETROC_DAQ')
import run_script
import parser_arguments
import importlib
importlib.reload(run_script)
import datetime
import pandas
from pathlib import Path
import subprocess
import sqlite3
from notebooks.notebook_helpers import *
from fnmatch import fnmatch
import scipy.stats as stats
from math import ceil
from numpy import savetxt


# !!!!!!!!!!!!
# It is very important to correctly set the chip name, this value is stored with the data
chip_names = ["ET2p01_PolyamidedRemoved_D01"]
chip_fignames = ["ET2.01 Polyamide Removed 01"]
chip_figtitles = chip_names

# 'The port name the USB-ISS module is connected to. Default: /dev/ttyACM0'
port = "/dev/ttyACM0"#changed from 0
# I2C addresses for the pixel block and WS
#chip_addresses = [0x60]
#ws_addresses = [None]
chip_address = 0x60
ws_address = None


fig_outdir = Path('../ETROC-figures')
fig_outdir = fig_outdir / (datetime.date.today().isoformat() + '_Array_Test_Results')
fig_outdir.mkdir(exist_ok=True)
fig_path = str(fig_outdir)


i2c_conn = i2c_connection(port,chip_addresses,ws_addresses,chip_names,[("1","1"),("1","1"),("1","1"), ("1","1")])

#perform auto calibration
i2c_conn.config_chips('00100101')

# ## Set power mode to high if currents are too low

# %%
full_col_list, full_row_list = np.meshgrid(np.arange(16),np.arange(16))
full_scan_list = list(zip(full_row_list.flatten(),full_col_list.flatten()))
for address in chip_addresses:
    i2c_conn.set_power_mode_scan_list(address, full_scan_list, 'high')

highPowerMode = False
if highPowerMode:
	i2c_conn.set_power_mode_scan_list(address, full_scan_list, 'high')

# %% [markdown]
# ## Visualize the learned Baselines (BL) and Noise Widths (NW)
# 
# Note that the NW represents the full width on either side of the BL

# %%
#%%
%matplotlib inline
import matplotlib.pyplot as plt
plt.figure()
plt.show()

# %%
print(i2c_conn.NW_map_THCal)
##new stuff i added for testing multiple BL/NW to compare results per pixel (over N tests)
print(i2c_conn.BL_map_THCal)
#also print the BL map then save these to a text file for later analysis
chipInfo = "ET5-3"
TestNumber = "1PIN"
#TestNumber = "1BV"
#TestNumber = "1NOPIN"
#TestNumber = "1"
targetpath = '../Korea_hybrid_test_9-15-26/W04F2_h63/'
np.savetxt(targetpath+"NW"+chipInfo+TestNumber+".csv", i2c_conn.NW_map_THCal[96], delimiter=' ')
np.savetxt(targetpath+"BL"+chipInfo+TestNumber+".csv", i2c_conn.BL_map_THCal[96], delimiter=' ')
print("savedtxt")


# %%
#histdir = Path('../hybrid_testing/')
histdir = Path(targetpath)
histdir.mkdir(exist_ok=True)
histfile = histdir / 'BaselineHistory.sqlite'
i2c_conn.save_baselines(chip_fignames,fig_path,histdir,histfile)


# do i care if this executes?
# %%
for chip_address, chip_name in zip(chip_addresses, chip_names):
    i2c_conn.save_auto_cal_BL_map(chip_address, chip_name, "")
    i2c_conn.save_auto_cal_NW_map(chip_address, chip_name, "")

# %%
for chip_address, chip_name in zip(chip_addresses, chip_names):
    i2c_conn.load_auto_cal_BL_map(chip_address, chip_name, "")
    i2c_conn.load_auto_cal_NW_map(chip_address, chip_name, "")






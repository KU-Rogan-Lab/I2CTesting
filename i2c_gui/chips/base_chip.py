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

from .address_space_controller import Address_Space_Controller

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..connection_controller import Connection_Controller

import tkinter as tk
import tkinter.ttk as ttk  # For themed widgets (gives a more native visual to the elements)
import logging
import itertools
import pickle

from ..functions import hex_0fill

class Base_Chip(GUI_Helper):
    newid = itertools.count()
    def __init__(self, parent: GUI_Helper, chip_name: str, version: str, i2c_controller: Connection_Controller, register_model = None, register_decoding = None, indexer_info = None):
        super().__init__(parent, None, parent._logger)

        self._id = next(Base_Chip.newid)

        self._i2c_controller = i2c_controller
        self._address_space = {}
        self._register_model = register_model
        self._register_decoding = register_decoding
        self._chip_name = chip_name
        self._unique_name = chip_name + "_{}".format(self._id)
        self._version = version

        self._enabled = False
        self._toggle_elements = {}
        self._displayed_interfaces = {}
        self._indexer_vars = {}
        self._indexer_array = {}
        self._block_array_display_vars = {}
        self._block_array_decoded_display_vars = {}

        self._enable_readback = True

        self._i2c_controller.register_connection_callback(self._connection_update)

        self._tabs = {}
        self.register_tab(
            "Empty",
            {
                "canvas": False,
                "builder": self.empty_tab_builder
            }
        )

        if indexer_info is not None:
            self._build_indexer_vars(indexer_info)

        for address_space in self._register_model:
            decoding = None
            if address_space in self._register_decoding:
                decoding = self._register_decoding[address_space]
            self._register_address_space(address_space, None, self._register_model[address_space], decoding)

            self._block_array_display_vars[address_space] = {}
            self._block_array_decoded_display_vars[address_space] = {}
            for block in self._register_model[address_space]["Register Blocks"]:
                if "Indexer" in self._register_model[address_space]["Register Blocks"][block]:
                    self._block_array_display_vars[address_space][block] = {}
                    self._block_array_decoded_display_vars[address_space][block] = {}
                    for register in self._register_model[address_space]["Register Blocks"][block]["Registers"]:
                        self._block_array_display_vars[address_space][block][register] = tk.StringVar(name="{}_Display_{}_{}_{}".format(self._unique_name, address_space, block, register))
                    for value in self._register_decoding[address_space]["Register Blocks"][block]:
                        self._block_array_decoded_display_vars[address_space][block][value] = tk.StringVar(name="{}_DecodedDisplay_{}_{}_{}".format(self._unique_name, address_space, block, value))

    @property
    def tabs(self):
        return list(self._tabs.keys())

    @property
    def id(self):
        return self._id

    @property
    def enable_readback(self):
        return self._enable_readback

    @enable_readback.setter
    def enable_readback(self, value: bool):
        self._enable_readback = value

    def _connection_update(self, value):
        for element_name in self._toggle_elements:
            reverse_polarity = self._toggle_elements[element_name][0]
            element = self._toggle_elements[element_name][1]

            if value ^ reverse_polarity:
                element.config(state="normal")
            else:
                element.config(state="disabled")

        for interface in self._displayed_interfaces:
            if value:
                self._displayed_interfaces[interface].enable()
            else:
                self._displayed_interfaces[interface].disable()

    def _register_address_space(self, name: str, address: int, address_space_model, register_decoding):
        if name in self._address_space:
            raise ValueError("An address space with the name '{}' already exists".format(name))

        size = address_space_model["Memory Size"]
        if "Register Bits" in address_space_model:
            bits = address_space_model["Register Bits"]
        else:
            bits = 16
        if "Register Length" in address_space_model:
            length = address_space_model["Register Length"]
        else:
            length = 8
        if "Endianness" in address_space_model:
            endianness = address_space_model["Endianness"]
        else:
            endianness = "little"
        if "Read Type" in address_space_model:
            read_type = address_space_model["Read Type"]
        else:
            read_type = "Normal"
        if "Write Type" in address_space_model:
            write_type = address_space_model["Write Type"]
        else:
            write_type = "Normal"
        decoded_registers = None
        if register_decoding is not None:
            decoded_registers = register_decoding["Register Blocks"]
        self._address_space[name] = Address_Space_Controller(
            parent=self,
            name=name,
            i2c_address=address,
            memory_size=size,
            i2c_controller=self._i2c_controller,
            register_map=address_space_model["Register Blocks"],
            decoded_registers=decoded_registers,
            register_bits=bits,
            register_length=length,
            endianness=endianness,
            read_type=read_type,
            write_type=write_type,
        )

    def _build_indexer_vars(self, indexer_info):
        indexer_variables = indexer_info["vars"]
        variables_min = indexer_info["min"]
        variables_max = indexer_info["max"]

        if len(indexer_variables) != len(variables_min) or len(indexer_variables) != len(variables_max):
            raise RuntimeError("Lengths of control structures for the indexer of {} do not match".format(self._chip_name))

        for idx in range(len(indexer_variables)):
            variable = indexer_variables[idx]
            minimum = variables_min[idx]
            maximum = variables_max[idx]

            if variable == "block" and minimum is None and maximum is None:
                continue

            if minimum is None and maximum is None:
                continue
            value = minimum
            if value is None:
                value=maximum

            self._indexer_vars[variable] = {
                "variable": tk.StringVar(name="{}_Indexer_{}".format(self._unique_name, variable)),
                "min": minimum,
                "max": maximum
            }
            self._indexer_vars[variable]["variable"].set(value)

    def get_indexer(self, name):
        if name not in self._indexer_vars:
            return None, None, None
        return self._indexer_vars[name]['variable'], self._indexer_vars[name]['min'], self._indexer_vars[name]['max']

    def _validate_indexers(self):
        for indexer in self._indexer_vars:
            init_val = self._indexer_vars[indexer]['variable'].get()
            val = init_val

            if val == "":
                val = "0"
            else:
                val = str(int(val))

            if val != init_val:
                self._indexer_vars[indexer]['variable'].set(val)

    def save_config(self, config_file: str):
        info = {
        }

        for address_space_name in self._address_space:
            address_space: Address_Space_Controller = self._address_space[address_space_name]
            size = address_space._memory_size

            conf = [None for idx in range(size)]

            for idx in range(size):
                conf[idx] = int(address_space._display_vars[idx].get(), 0)

            info[address_space_name] = conf

        self.save_pickle_file(config_file, info)

    def load_config(self, config_file: str):
        info = self.load_pickle_file(config_file)

        for address_space_name in self._address_space:
            address_space: Address_Space_Controller = self._address_space[address_space_name]
            size = address_space._memory_size

            length = address_space._register_length

            for idx in range(size):
                address_space._display_vars[idx].set(hex_0fill(info[address_space_name][idx], length))

        self.update_whether_modified()

    def reset_config(self):
        for name in self._address_space:
            self._address_space[name].reset()
        self.update_whether_modified()

    def revert_config(self):
        for name in self._address_space:
            if self._address_space[name].is_modified:
                self._address_space[name].revert()
        self.update_whether_modified()

    def save_pickle_file(self, config_file: str, object):
        save_object = {
            'object': object,
            'chip': self._chip_name,
            'version': self._version,
        }

        with open(config_file, 'wb') as f:
            pickle.dump(save_object, f)

    def load_pickle_file(self, config_file: str):
        loaded_obj = None
        with open(config_file, 'rb') as f:
            loaded_obj = pickle.load(f)

        if loaded_obj['chip'] != self._chip_name:
            self.send_message("Wrong config file type. It was saved for the chip: {}; expected {}".format(loaded_obj['chip'], self._chip_name), "Error")
            return

        # TODO: for the version we should probably implement some sort of semantic versioning
        if loaded_obj['version'] != self._version:
            self.send_message("Wrong config file type. It was saved for a different version of this chip: {}; expected {}".format(loaded_obj['version'], self._version), "Error")
            return

        return loaded_obj['object']

    def get_indexer_array(self, indexer_info):
        indexer_variables = indexer_info["vars"]
        variables_min = indexer_info["min"]
        variables_max = indexer_info["max"]

        indexer_array = {}
        tmp = {}
        for idx in range(len(indexer_variables)):
            variable = indexer_variables[idx]
            if variable == "block":
                if len(indexer_array) == 0:
                    tmp[""] = {
                        "arguments": ["{block}"]
                    }
                else:
                    for tag in indexer_array:
                        tmp[tag] = {
                            "arguments": indexer_array[tag]["arguments"] + ["{block}"]
                        }
            else:
                minimum = variables_min[idx]
                maximum = variables_max[idx]

                if minimum is None and maximum is None:
                    continue

                if minimum is None or maximum is None:
                    if minimum is not None:
                        my_range = [minimum]
                    else:
                        my_range = [maximum]
                elif minimum == 0 and maximum == 1:
                    my_range = [False, True]
                else:
                    my_range = range(minimum, maximum)

                for value in my_range:
                    if len(indexer_array) == 0:
                        tmp["{}".format(value)] = {
                            "arguments": ["{}".format(value)]
                        }
                    else:
                        for tag in indexer_array:
                            if tag == "":
                                index = "{}".format(value)
                            else:
                                index = "{}_{}".format(tag, value)
                            tmp[index] = {
                                "arguments": indexer_array[tag]["arguments"] + [value]
                            }

            indexer_array = tmp
            tmp = {}

        return indexer_array

    def register_tab(self, name, properties):
        if name in self._tabs:
            raise RuntimeError("A tab with the name {} already exists".format(name))

        self._tabs[name] = properties

    def clear_tab(self, name):
        if name in self._tabs:
            self._tabs.__delitem__(name)

    def read_all(self):
        for address_space in self._address_space:
            self.read_all_address_space(address_space)

    def write_all(self, write_check: bool = True):
        success = True
        for address_space in self._address_space:
            if not self.write_all_address_space(address_space, write_check=write_check):
                success = False

        return success

    def update_whether_modified(self):
        pass

    def read_all_address_space(self, address_space_name: str):
        self._logger.info("Reading full address space: {}".format(address_space_name))
        address_space: Address_Space_Controller = self._address_space[address_space_name]
        address_space.read_all()

    def write_all_address_space(self, address_space_name: str, write_check: bool = True):
        self._logger.info("Writing full address space: {}".format(address_space_name))
        address_space: Address_Space_Controller = self._address_space[address_space_name]
        return address_space.write_all(write_check=write_check)

    def read_all_block(self, address_space_name: str, block_name: str, full_array: bool = False):
        self._validate_indexers()
        block_ref, _ = self._gen_block_ref_from_indexers(
            address_space_name=address_space_name,
            block_name=block_name,
            full_array=full_array,
        )

        self.send_message("Reading block {} from address space {} of chip {}".format(block_ref, address_space_name, self._chip_name))
        address_space: Address_Space_Controller = self._address_space[address_space_name]
        address_space.read_block(block_ref)

    def write_all_block(self, address_space_name: str, block_name: str, full_array: bool = False, write_check: bool = True):
        self._validate_indexers()
        block_ref, _ = self._gen_block_ref_from_indexers(
            address_space_name=address_space_name,
            block_name=block_name,
            full_array=full_array,
        )

        self.send_message("Writing block {} from address space {} of chip {}".format(block_ref, address_space_name, self._chip_name))
        address_space: Address_Space_Controller = self._address_space[address_space_name]
        return address_space.write_block(block_ref, write_check=write_check)

    def _gen_block_ref_from_indexers(self, address_space_name: str, block_name: str, full_array: bool):
        block_ref = block_name
        params = {'block': block_name}

        if "Indexer" in self._register_model[address_space_name]["Register Blocks"][block_name] and not full_array:
            indexers = self._register_model[address_space_name]["Register Blocks"][block_name]["Indexer"]["vars"]
            min_vals = self._register_model[address_space_name]["Register Blocks"][block_name]["Indexer"]["min"]
            max_vals = self._register_model[address_space_name]["Register Blocks"][block_name]["Indexer"]["max"]

            block_ref = ""
            params = {}
            for idx in range(len(indexers)):
                indexer = indexers[idx]
                min_val = min_vals[idx]
                max_val = max_vals[idx]

                if block_ref != "":
                    block_ref += ":"

                if indexer == "block" and min_val is None and max_val is None:
                    block_ref += block_name
                    params[indexer] = block_name
                else:
                    val = self._indexer_vars[indexer]['variable'].get()
                    if val == "":
                        val = 0
                    block_ref += "{}".format(val)
                    params[indexer] = int(val)

        return block_ref, params

    def read_register(self, address_space_name: str, block_name: str, register: str, no_message: bool = False):
        self._logger.detailed_trace(f'Base_Chip::read_register("{address_space_name}", "{block_name}", "{register}", {no_message})')
        self._validate_indexers()
        block_ref, _ = self._gen_block_ref_from_indexers(
            address_space_name=address_space_name,
            block_name=block_name,
            full_array=False,
        )
        self._logger.detailed_trace(f'   Got block_ref={block_ref}')

        if not no_message:
            self.send_message("Reading register {} from block {} of address space {} of chip {}".format(register, block_ref, address_space_name, self._chip_name))
        address_space: Address_Space_Controller = self._address_space[address_space_name]
        address_space.read_register(block_ref, register)

    def write_register(self, address_space_name: str, block_name: str, register: str, write_check: bool = True, no_message: bool = False):
        self._validate_indexers()
        block_ref, _ = self._gen_block_ref_from_indexers(
            address_space_name=address_space_name,
            block_name=block_name,
            full_array=False,
        )

        if not no_message:
            self.send_message("Writing register {} from block {} of address space {} of chip {}".format(register, block_ref, address_space_name, self._chip_name))
        address_space: Address_Space_Controller = self._address_space[address_space_name]
        return address_space.write_register(block_ref, register, write_check=write_check)

    def read_decoded_value(self, address_space_name: str, block_name: str, decoded_value_name: str, no_message: bool = False):
        value_info = self._register_decoding[address_space_name]['Register Blocks'][block_name][decoded_value_name]

        for position in value_info['position']:
            register = position[0]
            self.read_register(address_space_name, block_name, register, no_message=no_message)

    def write_decoded_value(self, address_space_name: str, block_name: str, decoded_value_name: str, write_check: bool = True, no_message: bool = False):
        value_info = self._register_decoding[address_space_name]['Register Blocks'][block_name][decoded_value_name]

        for position in value_info['position']:
            register = position[0]
            self.write_register(address_space_name, block_name, register, write_check, no_message=no_message)

    def tab_needs_canvas(self, tab: str):
        return self._tabs[tab]["canvas"]

    def build_tab(self, tab: str, frame: ttk.Frame):
        if "builder" not in self._tabs[tab].keys():
            self.empty_tab_builder(frame)
        else:
            self._tabs[tab]["builder"](frame)

    def empty_tab_builder(self, frame: ttk.Frame):
        self._empty_label = ttk.Label(frame, text="This is an empty placeholder tab")
        self._empty_label.grid(column=100, row=100)

    def get_display_var(self, address_space, block_name, var_name):
        if address_space in self._block_array_display_vars and block_name in self._block_array_display_vars[address_space] and var_name in self._block_array_display_vars[address_space][block_name]:
            return self._block_array_display_vars[address_space][block_name][var_name]
        return self._address_space[address_space].get_display_var(block_name + "/" + var_name)

    def get_indexed_var(self, address_space, block_name, var_name):
        self._logger.detailed_trace(f'Base_Chip::get_indexed_var("{address_space}", "{block_name}", "{var_name}")')
        block_ref, _ = self._gen_block_ref_from_indexers(
            address_space_name=address_space,
            block_name=block_name,
            full_array=False,
        )
        self._logger.detailed_trace(f'   Got block_ref={block_ref}')

        return self._address_space[address_space].get_display_var(block_ref + "/" + var_name)

    def get_decoded_display_var(self, address_space, block_name, var_name):
        if address_space in self._block_array_decoded_display_vars and block_name in self._block_array_decoded_display_vars[address_space] and var_name in self._block_array_decoded_display_vars[address_space][block_name]:
            return self._block_array_decoded_display_vars[address_space][block_name][var_name]
        return self._address_space[address_space].get_decoded_display_var(block_name + "/" + var_name)

    def get_decoded_indexed_var(self, address_space, block_name, var_name):
        block_ref, _ = self._gen_block_ref_from_indexers(
            address_space_name=address_space,
            block_name=block_name,
            full_array=False,
        )

        return self._address_space[address_space].get_decoded_display_var(block_ref + "/" + var_name)

    def build_block_interface(self,
                              element: tk.Tk,
                              title: str,
                              internal_title: str,
                              button_title: str,
                              address_space: str,
                              block: str,
                              col: int,
                              row: int,
                              register_columns: int,
                              read_only: bool = False,
                              ):
        from ..register_block_interface import Register_Block_Interface

        register_length = 8
        if "Register Length" in self._register_model[address_space]:
            register_length = self._register_model[address_space]["Register Length"]

        retVal = Register_Block_Interface(
            self,
            address_space=address_space,
            block_name=block,
            block_title=title,
            button_title=button_title,
            register_model=self._register_model[address_space]["Register Blocks"][block]["Registers"],
            read_only=read_only,
            register_length=register_length,
        )

        retVal.prepare_display(element, col, row, register_columns=register_columns)

        self._displayed_interfaces[internal_title] = retVal

        return retVal

    def build_decoded_block_interface(self,
                                      element: tk.Tk,
                                      title: str,
                                      internal_title: str,
                                      button_title: str,
                                      address_space: str,
                                      block: str,
                                      col: int,
                                      row: int,
                                      value_columns: int,
                                      read_only: bool = False,
                                      use_groups: bool = False,
                                      ):
        from ..register_block_decoded_interface import Register_Block_Decoded_Interface

        retVal = Register_Block_Decoded_Interface(
            self,
            address_space=address_space,
            block_name=block,
            block_title=title,
            button_title=button_title,
            decoding_info=self._register_decoding[address_space]["Register Blocks"][block],
            read_only=read_only,
            use_groups=use_groups,
        )

        retVal.prepare_display(element, col, row, value_columns=value_columns)

        self._displayed_interfaces[internal_title] = retVal

        return retVal

    def build_block_array_controls(self,
                                   control_variables,
                                   element: tk.Tk,
                                   title: str,
                                   internal_title: str,
                                   col: int,
                                   row: int,
                                   ):
        from ..block_array_controller_interface import Block_Array_Controller_Interface

        retVal = Block_Array_Controller_Interface(
            self,
            title=title,
            control_variables=control_variables,
        )

        retVal.prepare_display(element, col, row)

        self._displayed_interfaces[internal_title] = retVal

        return retVal

    def build_block_array_interface(self,
                                    element: tk.Tk,
                                    title: str,
                                    internal_title: str,
                                    button_title: str,
                                    address_space: str,
                                    block: str,
                                    col: int,
                                    row: int,
                                    register_columns: int,
                                    read_only: bool = False,
                                    ):
        from ..register_block_array_interface import Register_Block_Array_Interface

        register_length = 8
        if "Register Length" in self._register_model[address_space]:
            register_length = self._register_model[address_space]["Register Length"]

        retVal = Register_Block_Array_Interface(
            self,
            address_space=address_space,
            block_name=block,
            block_title=title,
            button_title=button_title,
            register_model=self._register_model[address_space]["Register Blocks"][block]["Registers"],
            read_only=read_only,
            register_length=register_length,
        )

        retVal.prepare_display(element, col, row, register_columns=register_columns)

        self._displayed_interfaces[internal_title] = retVal

        return retVal

    def build_decoded_block_array_interface(self,
                                            element: tk.Tk,
                                            title: str,
                                            internal_title: str,
                                            button_title: str,
                                            address_space: str,
                                            block: str,
                                            col: int,
                                            row: int,
                                            value_columns: int,
                                            read_only: bool = False,
                                            use_groups: bool = False,
                                            ):
        from ..register_block_array_decoded_interface import Register_Block_Array_Decoded_Interface

        retVal = Register_Block_Array_Decoded_Interface(
            self,
            address_space=address_space,
            block_name=block,
            block_title=title,
            button_title=button_title,
            decoding_info=self._register_decoding[address_space]["Register Blocks"][block],
            read_only=read_only,
            use_groups=use_groups,
        )

        retVal.prepare_display(element, col, row, value_columns=value_columns)

        self._displayed_interfaces[internal_title] = retVal

        return retVal

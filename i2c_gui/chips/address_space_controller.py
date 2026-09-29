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

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..connection_controller import Connection_Controller
from ..gui_helper import GUI_Helper

from ..functions import hex_0fill

import tkinter as tk
import logging
import time

class Address_Space_Controller(GUI_Helper):
    def __init__(
        self,
        parent: GUI_Helper,
        name, i2c_address,
        memory_size,
        i2c_controller: Connection_Controller,
        register_map,
        decoded_registers,
        register_bits: int = 16,
        register_length: int = 8,
        readback_delay_us: int = 1000,
        endianness: str = 'little',
        read_type: str = 'Normal',
        write_type: str = 'Normal',
    ):
        super().__init__(parent, None, parent._logger)

        self._name = name
        self._i2c_address = i2c_address
        self._i2c_controller = i2c_controller
        self._memory_size = memory_size
        self._blocks = {}
        self._register_map_metadata = register_map
        self._register_bits = register_bits
        self._register_length = register_length
        self._readback_delay_us = readback_delay_us

        if endianness not in ['little', 'big']:
            raise RuntimeError("Unknown endianness type")
        self._endianness = endianness

        if read_type not in ['Normal', 'Repeated Start']:
            raise RuntimeError('Unknown read type')
        self._read_type = read_type

        if write_type not in ['Normal']:  # , 'Repeated Start']:
            raise RuntimeError('Unknown write type')
        self._write_type = write_type

        self._not_read = True

        self._memory = [None for val in range(self._memory_size)]
        self._read_only_map = [True for val in range(self._memory_size)]

        self._display_vars = [tk.StringVar(value = "0", name="{}_{}_Reg{}".format(self._parent._unique_name, self._name, val)) for val in range(self._memory_size)]

        self._register_map = {}
        for block_name in register_map:
            if "Base Address" in register_map[block_name]:
                base_address = register_map[block_name]["Base Address"]
                self._blocks[block_name] = {
                    "Base Address": base_address,
                    "Length": len(register_map[block_name]["Registers"])  # Note: Assuming that all the listed registers in a block are contiguous in the memory space
                }

                if "Write Base Address" in register_map[block_name]:
                    self._blocks[block_name]["Write Base Address"] = register_map[block_name]["Write Base Address"]

                for register in register_map[block_name]["Registers"]:
                    offset = register_map[block_name]["Registers"][register]["offset"]
                    read_only = False
                    if 'read_only' in register_map[block_name]["Registers"][register]:
                        read_only = register_map[block_name]["Registers"][register]['read_only']
                    full_address = base_address + offset
                    self._register_map[block_name + "/" + register] = full_address
                    self._display_vars[full_address].set(hex_0fill(register_map[block_name]["Registers"][register]['default'], self._register_length))
                    self._read_only_map[full_address] = read_only
            elif "Indexer" in register_map[block_name]:
                indexer_info = register_map[block_name]['Indexer']
                min_address, max_address, base_addresses = self._get_indexed_block_address_range(block_name, indexer_info, register_map[block_name]['Registers'])

                if max_address >= min_address:  # Note: even though not frequently used, a block covering the whole array is needed for bulk read/write operations
                    self._blocks[block_name] = {
                        "Base Address": min_address,
                        "Length": max_address - min_address + 1
                    }

                for block_ref in base_addresses:  # Note: it is a block ref and not a block name because this is a block array
                    self._blocks[block_ref] = {
                        "Base Address": base_addresses[block_ref]['base_address'],
                        "Length": len(register_map[block_name]["Registers"])  # Note: Assuming that all the listed registers in a block are contiguous in the memory space
                    }

                for register in register_map[block_name]["Registers"]:
                    offset = register_map[block_name]["Registers"][register]["offset"]
                    for base_name in base_addresses:
                        base_address = base_addresses[base_name]['base_address']
                        full_address = base_address + offset
                        read_only = False
                        if 'read_only' in register_map[block_name]["Registers"][register]:
                            read_only = register_map[block_name]["Registers"][register]['read_only']
                        full_register_name = base_name + "/" + register
                        self._register_map[full_register_name] = full_address
                        self._display_vars[full_address].set(hex_0fill(register_map[block_name]["Registers"][register]['default'], self._register_length))
                        self._read_only_map[full_address] = read_only
            else:
                self._logger.error("An impossible condition occured, there was a memory block defined which does not have a base address and does not have an indexer")

        self._decoded_display_vars = {}
        self._decoded_bit_size = {}
        if decoded_registers is not None:
            for block_name in decoded_registers:
                if block_name not in register_map:
                    self._logger.error("Skipping unknown block in register decoding map: {}".format(block_name))
                    continue
                for value in decoded_registers[block_name]:
                    decoding_info = decoded_registers[block_name][value]
                    value_bits = decoding_info['bits']

                    if "Base Address" in register_map[block_name]:
                        self._build_decoded_value(
                            value=value,
                            block_ref=block_name,
                            value_bits=value_bits,
                            decoding_position_info=decoding_info['position'],
                        )
                    elif "Indexer" in register_map[block_name]:
                        _, _, base_addresses = self._get_indexed_block_address_range(block_name, indexer_info, register_map[block_name]['Registers'])
                        for block_ref in base_addresses:  # Note: it is a block ref and not a block name because this is a block array
                            self._build_decoded_value(
                                value=value,
                                block_ref=block_ref,
                                value_bits=value_bits,
                                decoding_position_info=decoding_info['position'],
                            )
                    else:
                        self._logger.error("An impossible condition occured, there was a memory block defined which does not have a base address and does not have an indexer")

    def _build_decoded_value(self, value: str, block_ref: str, value_bits: int, decoding_position_info: list[tuple]):
        self._decoded_display_vars[block_ref + "/" + value] = tk.StringVar(name="{}_{}_{}_{}".format(self._parent._unique_name, self._name, block_ref, value))
        self._decoded_bit_size[block_ref + "/" + value] = value_bits

        for regInfo in decoding_position_info:
            register = regInfo[0]

            register_var = self._display_vars[self._register_map[block_ref + "/" + register]]
            self._update_decoded_value(block_ref, value, value_bits, regInfo)
            # Note: Save ? these callbacks in case they need to be handled later
            register_var.trace_add('write', lambda var, index, mode, block_ref=block_ref, value=value, value_bits=value_bits, position=regInfo:self._update_decoded_value(block_ref, value, value_bits, position))
            self._decoded_display_vars[block_ref + "/" + value].trace_add('write', lambda var, index, mode, block_ref=block_ref, value=value, value_bits=value_bits, position=regInfo:self._update_register(block_ref, value, value_bits, position))

    def _get_indexed_block_address_range(self, block_name, indexer_info, register_map):
        indexer_function = indexer_info['function']

        registers = {}
        for idx in range(len(indexer_info['vars'])):
            var = indexer_info['vars'][idx]
            min = indexer_info['min'][idx]
            max = indexer_info['max'][idx]

            old_registers = registers
            registers = {}

            if var == "block" and min is None and max is None:
                param = block_name
                if len(old_registers) == 0:
                    registers[param] = {
                        'params': {'block': param},
                    }
                else:
                    for old in old_registers:
                        registers[old + ":" + param] = {}
                        registers[old + ":" + param]['params'] = old_registers[old]['params']
                        registers[old + ":" + param]['params']['block'] = str(param)
            else:
                for val_idx in range(max - min):
                    i = min + val_idx
                    if len(old_registers) == 0:
                        registers[i] = {
                            'params': {var: i},
                        }
                    else:
                        for old in old_registers:
                            registers[old + ":" + str(i)] = {}
                            registers[old + ":" + str(i)]['params'] = (old_registers[old]['params']).copy()
                            registers[old + ":" + str(i)]['params'][var] = i

        min_address = None
        max_address = None
        for key in registers:
            address = indexer_function(**(registers[key]['params']))
            registers[key]['base_address'] = address
            if min_address is None or address < min_address:
                min_address = address
            if max_address is None or address > max_address:
                max_address = address

        max_offset = None
        for register in register_map:
            offset = register_map[register]['offset']
            if max_offset is None or offset > max_offset:
                max_offset = offset

        return min_address, max_address + max_offset, registers

    @property
    def is_modified(self):
        if self._i2c_address is None or self._not_read:
            return "Unknown"

        for idx  in range(self._memory_size):
            value = self._display_vars[idx].get()
            if value == "" or value == "0x":
                value = 0
            else:
                value = int(value, 0)
            if value != self._memory[idx]:
                return True
        return False

    def _update_register(self, block, value, bits, position):
        #self._logger.detailed_trace("Entered Address_Space_Controller._update_register(block={}, value={}, bits={}, position={})".format(block, value, bits, position))
        register_string = "{}/{}[{}]".format(block, position[0], position[1])
        decoded_string = "{}[{}]".format(value, position[2])
        self._logger.detailed_trace("Attempting to update register {} from decoded value {}".format(register_string, decoded_string))
        if hasattr(self, "_updating_from_register"):  # Avoid an infinite loop where the two variables trigger each other
            return

        self._logger.trace("Updating register {} from decoded value {}".format(register_string, decoded_string))

        self._updating_from_decoded_value = decoded_string

        register_min_idx, register_max_idx = self._get_bit_index_min_max(position[1], 8)
        value_min_idx,    value_max_idx    = self._get_bit_index_min_max(position[2], bits)

        register_repr = self._build_bit_repr(self._display_vars[self._register_map[block + "/" + position[0]]], 8)
        value_repr = self._build_bit_repr(self._decoded_display_vars[block + "/" + value], bits)

        register_repr = [i for i in register_repr]
        value_repr = [i for i in value_repr]
        register_repr[register_min_idx:register_max_idx] = value_repr[value_min_idx:value_max_idx]
        register_repr = ''.join(register_repr)

        register_repr = '0b' + register_repr
        self._display_vars[self._register_map[block + "/" + position[0]]].set(hex_0fill(int(register_repr, 0), self._register_length))

        del self._updating_from_decoded_value

    def _update_decoded_value(self, block, value, bits, position):
        #self._logger.detailed_trace("Entered Address_Space_Controller._update_decoded_value(block={}, value={}, bits={}, position={})".format(block, value, bits, position))
        register_string = "{}/{}[{}]".format(block, position[0], position[1])
        decoded_string = "{}[{}]".format(value, position[2])
        self._logger.detailed_trace("Attempting to update decoded value {} from register {}".format(decoded_string, register_string))
        if hasattr(self, "_updating_from_decoded_value"):  # Avoid an infinite loop where the two variables trigger each other
            if self._updating_from_decoded_value == decoded_string:
                return

        self._logger.trace("Updating decoded value {} from register {}".format(decoded_string, register_string))

        self._updating_from_register = True

        register_min_idx, register_max_idx = self._get_bit_index_min_max(position[1], 8)
        value_min_idx,    value_max_idx    = self._get_bit_index_min_max(position[2], bits)

        register_repr = self._build_bit_repr(self._display_vars[self._register_map[block + "/" + position[0]]], 8)
        value_repr = self._build_bit_repr(self._decoded_display_vars[block + "/" + value], bits)

        register_repr = [i for i in register_repr]
        value_repr = [i for i in value_repr]
        value_repr[value_min_idx:value_max_idx] = register_repr[register_min_idx:register_max_idx]
        value_repr = ''.join(value_repr)

        if bits == 1:
            self._decoded_display_vars[block + "/" + value].set(value_repr)
        else:
            value_repr = '0b' + value_repr
            self._decoded_display_vars[block + "/" + value].set(hex_0fill(int(value_repr, 0), bits))

        del self._updating_from_register

    def _build_bit_repr(self, var: tk.Variable, bit_length: int=8):
        binary_string = ''.join(["0" for i in range(bit_length)])
        value = var.get()

        if value != "" and value != "0x":
            binary_string = format(int(value, 0), 'b')
            if len(binary_string) < bit_length:
                prepend = '0'*(bit_length-len(binary_string))
                binary_string = prepend + binary_string

        return binary_string

    def _get_bit_index_min_max(self, index: str, bit_size: int=8):
        bit_idx_limits = index.split('-')

        for idx in range(len(bit_idx_limits)):
            bit_idx_limits[idx] = int(bit_idx_limits[idx])

        if len(bit_idx_limits) == 1:
            max_val = bit_size - bit_idx_limits[0]
            min_val = max_val - 1
        else:
            min_val = bit_size - bit_idx_limits[0] - 1
            max_val = bit_size - bit_idx_limits[1]

        return (min_val, max_val)

    def update_i2c_address(self, address: int):
        if address != self._i2c_address:
            self._i2c_address = address
            self._not_read = True

            if address is not None:
                self._logger.info("Updated address space '{}' to the I2C address {}".format(self._name, hex_0fill(address, 7)))
            else:
                self._logger.info("Reset the I2C address for the address space '{}'".format(self._name))

    def get_memory(self, register_name):
        return self._memory[self._register_map[register_name]]

    def get_display_var(self, register_name):
        return self._display_vars[self._register_map[register_name]]

    def get_decoded_display_var(self, value_name):
        return self._decoded_display_vars[value_name]

    def get_decoded_bit_size(self, value_name):
        return self._decoded_bit_size[value_name]

    def read_all(self):
        if self._i2c_address is None:
            self.send_message("Unable to read address space '{}' because the i2c address is not set".format(self._name), "Error")
            return

        self._logger.info("Reading the full '{}' address space".format(self._name))

        if self.read_memory_block(0, self._memory_size):
            self._not_read = False

    def write_all(self, write_check: bool = True):
        if self._i2c_address is None:
            self.send_message("Unable to write address space '{}' because the i2c address is not set".format(self._name), "Error")
            return False

        for val in self._read_only_map:
            if val:
                self._logger.info("Unable to write the full '{}' address space because there are some read only registers, breaking it into smaller blocks".format(self._name))
                return self.write_memory_block_with_split_for_read_only(0, self._memory_size, write_check)


        self._logger.info("Writing the full '{}' address space".format(self._name))

        return self.write_memory_block(0, self._memory_size, write_check=write_check)

    def _read_memory_address_with_endian(self, address):
        if self._i2c_address is None:
            self.send_message("Unable to read address space '{}' because the i2c address is not set".format(self._name), "Error")
            return

        from math import ceil

        read_bytes = ceil(self._register_length/8)
        tmp = self._i2c_controller.read_device_memory(self._i2c_address, address, read_bytes, self._register_bits, self._register_length, self._read_type)

        if read_bytes == 1:
            return tmp[0]

        value = 0
        if self._endianness == 'little':
            for i in range(len(tmp)):
                value = (value << 8) | tmp[len(tmp) - i - 1]
        else:
            for i in range(len(tmp)):
                value = (value << 8) | tmp[i]

        #TODO: Add a compensation scheme for when the number of bits in a register is not an exact multiple of 8

        return value

    def read_memory_register(self, address):
        if self._i2c_address is None:
            self.send_message("Unable to read address space '{}' because the i2c address is not set".format(self._name), "Error")
            return

        self._logger.info("Reading register at address {} in the address space '{}'".format(address, self._name))

        self._memory[address] = self._read_memory_address_with_endian(address)
        self._display_vars[address].set(hex_0fill(self._memory[address], self._register_length))

        self._parent.update_whether_modified()

    def write_memory_register(self, address, write_check: bool = True, read_address = None):
        if self._i2c_address is None:
            self.send_message("Unable to write address space '{}' because the i2c address is not set".format(self._name), "Error")
            return False

        if self._read_only_map[address]:
            self._logger.info("Unable to write to the register at address {} in the address space '{}' because it is read only".format(address, self._name))
            return False

        self._logger.info("Writing register at address {} in the address space '{}'".format(address, self._name))

        from math import ceil
        write_bytes = ceil(self._register_length/8)
        register_bytes = []

        self._memory[address] = int(self._display_vars[address].get(), 0)
        tmp = self._memory[address]
        for idx in range(write_bytes):
            register_bytes += [tmp & 0xff]
            tmp = tmp >> 8
        if self._endianness == "big":
            register_bytes.reverse()

        self._i2c_controller.write_device_memory(self._i2c_address, address, register_bytes, self._register_bits, self._register_length, self._write_type)

        if write_check:
            #time.sleep(self._readback_delay_us/10E6)  # because sleep accepts seconds

            if read_address is None:
                read_address = address

            tmp = self._read_memory_address_with_endian(read_address)
            if self._memory[address] != tmp:
                self.send_message("Failure to write register at address 0x{:0x} in the {} address space (I2C address 0x{:0x})".format(address, self._name, self._i2c_address),
                                  status="Error"
                )
                self._memory[address] = tmp
                # self._display_vars[address].set(hex_0fill(tmp, self._register_length))

                self._parent.update_whether_modified()

                return False

        self._parent.update_whether_modified()

        return True

    def read_memory_block(self, address, data_size):
        if self._i2c_address is None:
            self.send_message("Unable to read address space '{}' because the i2c address is not set".format(self._name), "Error")
            return False

        from math import ceil

        read_bytes = ceil(self._register_length/8)

        self._logger.info("Reading a block of {} registers ({} bytes each) starting at address {} in the address space '{}'".format(data_size, read_bytes, address, self._name))

        tmp = self._i2c_controller.read_device_memory(self._i2c_address, address, data_size*read_bytes, self._register_bits, self._register_length, self._read_type)
        for i in range(data_size):
            if read_bytes == 1:
                self._memory[address+i] = tmp[i]
            else:
                value = 0
                base_idx = i * read_bytes
                if self._endianness == 'little':
                    for idx in range(read_bytes):
                        value = (value << 8) | tmp[base_idx + read_bytes - 1 - idx]
                else:
                    for idx in range(read_bytes):
                        value = (value << 8) | tmp[base_idx + idx]
                self._memory[address+i] = value
            self._display_vars[address+i].set(hex_0fill(self._memory[address+i], self._register_length))

        self._parent.update_whether_modified()

        return True

    def write_memory_block_with_split_for_read_only(self, address, data_size, write_check: bool = True, read_address = None):
        start_address = None
        ranges = []

        for idx in range(data_size):
            if not self._read_only_map[address + idx] and start_address is None:
                start_address = address + idx
            if self._read_only_map[address + idx] and start_address is not None:
                ranges += [(start_address, address + idx - start_address)]
                start_address = None
        if start_address is not None:
            if read_address is None:
                read_address = address
            ranges += [(start_address, address + idx - start_address + 1, start_address - address + read_address)]

        success = True
        self._logger.info("Found {} ranges without read only registers".format(len(ranges)))
        for range_param in ranges:
            if range_param[1] == 1:
                if not self.write_memory_register(range_param[0], write_check, range_param[2]):
                    success = False
            else:
                if not self.write_memory_block(range_param[0], range_param[1], write_check, range_param[2]):
                    success = False

        return success

    def write_memory_block(self, address, data_size, write_check: bool = True, read_address = None):
        if self._i2c_address is None:
            self.send_message("Unable to write address space '{}' because the i2c address is not set".format(self._name), "Error")
            return False

        has_read_only = False
        for idx in range(data_size):
            if self._read_only_map[address + idx]:
                has_read_only = True
                break
        if has_read_only:
            self._logger.info("The block of {} bytes starting at address {} in the address space '{}' covers one or more registers which are read only, it will be broken down into smaller blocks which do not cover the read only registers".format(data_size, address, self._name))
            self.write_memory_block_with_split_for_read_only(address, data_size, write_check, read_address)
            return False

        self._logger.info("Writing a block of {} bytes starting at address {} in the address space '{}'".format(data_size, address, self._name))

        from math import ceil

        write_bytes = ceil(self._register_length/8)

        for i in range(data_size):
            self._memory[address+i] = int(self._display_vars[address+i].get(), 0)

        if write_bytes == 1:
            tmp = self._memory[address:address+data_size]
        else:
            tmp = [None for i in range(data_size * write_bytes)]
            for idx in range(data_size):
                for i in range(write_bytes):
                    if self._endianness == 'little':
                        tmp[idx*write_bytes + i] = (self._memory[idx] >> (8 * i)) & 0xff
                    else:
                        tmp[idx*write_bytes + i] = (self._memory[idx] >> (8 * (write_bytes - 1 - i))) & 0xff

        self._i2c_controller.write_device_memory(self._i2c_address, address, tmp, self._register_bits, self._register_length, self._write_type)

        if write_check:
            #time.sleep(self._readback_delay_us/10E6)  # because sleep accepts seconds

            if read_address is None:
                read_address = address

            tmp = self._i2c_controller.read_device_memory(self._i2c_address, read_address, data_size*write_bytes, self._register_bits, self._register_length, self._read_type)
            if write_bytes != 1:
                read_tmp = tmp
                tmp = [None for i in range(data_size)]

                for base_idx in range(data_size):
                    value = 0
                    if self._endianness == 'little':
                        for i in range(write_bytes):
                            value = (value << 8) | read_tmp[(base_idx + 1) * write_bytes - 1 - i]
                    else:
                        for i in range(write_bytes):
                            value = (value << 8) | read_tmp[base_idx * write_bytes + i]
                    tmp[base_idx] = value

                    del read_tmp

            failed = []
            for i in range(data_size):
                if self._memory[address+i] != tmp[i]:
                    failed += [address+i]
                    self._memory[address+i] = tmp[i]
                    # self._display_vars[address+i].set(hex_0fill(tmp[i], self._register_length))
            if len(failed) != 0:
                failed = ["0x{:0x}".format(i) for i in failed]
                self.send_message("Failure to write memory block at address 0x{:0x} with length {} in the {} address space (I2C address 0x{:0x}). The following register addresses failed to write: {}".format(address, data_size, self._name, self._i2c_address, ', '.join(failed)),
                                  status="Error"
                )

                self._parent.update_whether_modified()

                return False

        self._parent.update_whether_modified()

        return True

    def read_block(self, block_name):
        if self._i2c_address is None:
            self.send_message("Unable to read address space '{}' because the i2c address is not set".format(self._name), "Error")
            return

        block = self._blocks[block_name]
        self._logger.info("Attempting to read block {}".format(block_name))

        self.read_memory_block(block["Base Address"], block["Length"])

    def write_block(self, block_name, write_check: bool = True):
        if self._i2c_address is None:
            self.send_message("Unable to write address space '{}' because the i2c address is not set".format(self._name), "Error")
            return False

        block = self._blocks[block_name]
        self._logger.info("Attempting to write block {}".format(block_name))

        address = block["Base Address"]
        original_address = address
        if "Write Base Address" in block:
            address = block["Write Base Address"]
            for idx in range(block["Length"]):
                self._display_vars[address+idx].set(self._display_vars[original_address+idx].get())

        return self.write_memory_block(block["Base Address"], block["Length"], write_check, original_address)

    def read_register(self, block_name, register_name):
        self._logger.detailed_trace(f'Address_Space_Controller::read_register("{block_name}", "{register_name}")')
        if self._i2c_address is None:
            self.send_message("Unable to read address space '{}' because the i2c address is not set".format(self._name), "Error")
            return

        self._logger.info("Attempting to read register {} in block {}".format(register_name, block_name))

        self.read_memory_register(self._register_map[block_name + "/" + register_name])

    def write_register(self, block_name, register_name, write_check: bool = True):
        if self._i2c_address is None:
            self.send_message("Unable to write address space '{}' because the i2c address is not set".format(self._name), "Error")
            return False

        self._logger.info("Attempting to write register {} in block {}".format(register_name, block_name))

        address = self._register_map[block_name + "/" + register_name]
        original_address = address
        if "Write Base Address" in self._blocks[block_name]:
            val = self._display_vars[address].get()
            new_base = self._blocks[block_name]["Write Base Address"]
            old_base = self._blocks[block_name]["Base Address"]
            address = address - old_base + new_base
            self._display_vars[address].set(val)

        return self.write_memory_register(address, write_check, original_address)

    def reset(self):
        register_count = len(self._register_map)
        count = 0
        lastUpdateTime = time.time_ns()
        for register_ref in self._register_map:
            thisTime = time.time_ns()
            if thisTime - lastUpdateTime > 0.3 * 10**9:
                lastUpdateTime = thisTime
                self.display_progress("Resetting:", count*100./register_count)
                #self._parent._parent._frame.update_idletasks()
                self._parent._parent._frame.update()

            full_address = self._register_map[register_ref]

            register_info = register_ref.split("/")
            block_ref = register_info[0]
            register_name = register_info[1]
            block_info = block_ref.split(":")
            block_name = block_info[0]

            default_value = self._register_map_metadata[block_name]["Registers"][register_name]['default']
            self._display_vars[full_address].set(hex_0fill(default_value, self._register_length))
            count += 1
        self.clear_progress()

    def revert(self):
        lastUpdateTime = time.time_ns()
        for idx in range(self._memory_size):
            thisTime = time.time_ns()
            if thisTime - lastUpdateTime > 0.3 * 10**9:
                lastUpdateTime = thisTime
                self.display_progress("Reverting:", idx*100./self._memory_size)
                #self._parent._parent._frame.update_idletasks()
                self._parent._parent._frame.update()

            if self._memory[idx] is not None:
                self._display_vars[idx].set(hex_0fill(self._memory[idx], self._register_length))
        self.clear_progress()

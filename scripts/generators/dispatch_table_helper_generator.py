#!/usr/bin/python3 -i

# Copyright 2023 The Khronos Group Inc.
# Copyright 2023 Valve Corporation
# Copyright 2023 LunarG, Inc.
#
# SPDX-License-Identifier: Apache-2.0

import os
from generators.base_generator import BaseGenerator

class DispatchTableHelperOutputGenerator(BaseGenerator):
    """Generate dispatch tables header based on XML element attributes"""
    def __init__(self):
        BaseGenerator.__init__(self)

    def generate(self):
        out = []
        out.append(f'''// *** THIS FILE IS GENERATED - DO NOT EDIT ***
// See {os.path.basename(__file__)} for modifications
// Copyright 2023 The Khronos Group Inc.
// Copyright 2023 Valve Corporation
// Copyright 2023 LunarG, Inc.
//
// SPDX-License-Identifier: Apache-2.0
\n''')
        out.append('// NOLINTBEGIN') # Wrap for clang-tidy to ignore

        out.append('''
#pragma once

#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>
#include <cstring>
#include <string>
#include "vk_layer_dispatch_table.h"
#include "vk_extension_helper.h"
\n''')

        for command in [x for x in self.vk.commands.values() if x.extensions or x.version]:
            if command.name == 'vkEnumerateInstanceVersion':
                continue # TODO - Figure out how this can be automatically detected
            out.extend([f'#ifdef {command.protect}\n'] if command.protect else [])

            prototype = ' '.join(command.cPrototype.split()) # remove duplicate whitespace
            prototype = prototype.replace('\n', '').replace('( ', '(').replace(');', ')').replace(' vk', ' Stub')

            result = '' if command.returnType == 'void' else 'return 0;'
            result = 'return VK_SUCCESS;' if command.returnType == 'VkResult' else result
            result = 'return VK_FALSE;' if command.returnType == 'VkBool32' else result

            out.append(f'static {prototype} {{ {result} }}\n')
            out.extend([f'#endif // {command.protect}\n'] if command.protect else [])
        out.append('\n')

        out.append('const vvl::unordered_map<std::string, small_vector<std::string, 2, size_t>> api_extension_map {\n')
        for command in [x for x in self.vk.commands.values() if x.version and x.device]:
            out.append(f'    {{ "{command.name}", {{ "{command.version.name}" }} }},\n')
        for command in [x for x in self.vk.commands.values() if x.extensions and x.device]:
            extensions = ', '.join(f'"{x.name}"' for x in command.extensions)
            out.append(f'    {{ "{command.name}", {{ {extensions} }} }},\n')
        out.append('};\n')

        out.append('''
// Using the above code-generated map of APINames-to-parent extension names, this function will:
//   o  Determine if the API has an associated extension
//   o  If it does, determine if that extension name is present in the passed-in set of device or instance enabled_ext_names
//   If the APIname has no parent extension, OR its parent extension name is IN one of the sets, return TRUE, else FALSE
static inline bool ApiParentExtensionEnabled(const std::string api_name, const DeviceExtensions *device_extension_info) {
    auto has_ext = api_extension_map.find(api_name);
    // Is this API part of an extension or feature group?
    if (has_ext != api_extension_map.end()) {

        // Was the extension for this API enabled in the CreateDevice call?
        for (const auto& ext : has_ext->second) {
            auto info = device_extension_info->get_info(ext.c_str());
            if (info.state) {
                return device_extension_info->*(info.state) == kEnabledByCreateinfo || device_extension_info->*(info.state) == kEnabledByInteraction;
            }
        }

        // Was the extension for this API enabled in the CreateInstance call?
        auto instance_extension_info = static_cast<const InstanceExtensions*>(device_extension_info);
        for (const auto& ext : has_ext->second) {
            auto inst_info = instance_extension_info->get_info(ext.c_str());
            if (inst_info.state) {
                return instance_extension_info->*(inst_info.state) == kEnabledByCreateinfo || device_extension_info->*(inst_info.state) == kEnabledByInteraction;
            }
        }
        return false;
    }
    return true;
}
''')
        out.append('''
static inline void layer_init_device_dispatch_table(VkDevice device, VkLayerDispatchTable *table, PFN_vkGetDeviceProcAddr gpa) {
    memset(table, 0, sizeof(*table));
    // Device function pointers
    table->GetDeviceProcAddr = gpa;
''')
        for command in [x for x in self.vk.commands.values() if x.device and x.name != 'vkGetDeviceProcAddr']:
            out.extend([f'#ifdef {command.protect}\n'] if command.protect else [])
            out.append(f'    table->{command.name[2:]} = (PFN_{command.name}) gpa(device, "{command.name}");\n')
            if command.version or command.extensions:
                out.append(f'    if (table->{command.name[2:]} == nullptr) {{ table->{command.name[2:]} = (PFN_{command.name})Stub{command.name[2:]}; }}\n')
            out.extend([f'#endif // {command.protect}\n'] if command.protect else [])
        out.append('}\n')

        out.append('''
static inline void layer_init_instance_dispatch_table(VkInstance instance, VkLayerInstanceDispatchTable *table, PFN_vkGetInstanceProcAddr gpa) {
    memset(table, 0, sizeof(*table));
    // Instance function pointers
    table->GetInstanceProcAddr = gpa;
    table->GetPhysicalDeviceProcAddr = (PFN_GetPhysicalDeviceProcAddr) gpa(instance, "vk_layerGetPhysicalDeviceProcAddr");
''')
        ignoreList = [
              'vkCreateInstance',
              'vkCreateDevice',
              'vkGetPhysicalDeviceProcAddr',
              'vkEnumerateInstanceExtensionProperties',
              'vkEnumerateInstanceLayerProperties',
              'vkEnumerateInstanceVersion',
              'vkGetInstanceProcAddr',
        ]
        for command in [x for x in self.vk.commands.values() if x.instance and x.name not in ignoreList]:
            out.extend([f'#ifdef {command.protect}\n'] if command.protect else [])
            out.append(f'    table->{command.name[2:]} = (PFN_{command.name}) gpa(instance, "{command.name}");\n')
            if command.version or command.extensions:
                out.append(f'    if (table->{command.name[2:]} == nullptr) {{ table->{command.name[2:]} = (PFN_{command.name})Stub{command.name[2:]}; }}\n')
            out.extend([f'#endif // {command.protect}\n'] if command.protect else [])
        out.append('}\n')

        out.append('// NOLINTEND') # Wrap for clang-tidy to ignore
        self.write("".join(out))
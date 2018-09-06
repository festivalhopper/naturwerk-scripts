from collections import defaultdict
import os
import re


CONTROLLER_PREFIX = 'controller_'
ACCESS_PREFIX = 'access_'


def read_drupal_7_hook_menu(path_to_module):
    module_name = os.path.basename(path_to_module)
    with open(os.path.join(path_to_module, f'{module_name}.module')) as f:
        item_start_regex = re.compile(r'\s*\$items\[(?P<quote>[\'"])(?P<path>.+?)(?P=quote)\]\s*=\s*array')
        kv_one_line_regex = re.compile(r'\s*(?P<quote>[\'"])(?P<key>.+?)(?P=quote)\s*=>\s*(?P<value>.+?)\s*(?P<comma_or_end>,|\);)')
        kv_one_line_no_comma_regex = re.compile(r'\s*(?P<quote>[\'"])(?P<key>.+?)(?P=quote)\s*=>\s*(?P<value>.+)\s*')
        item_end_regex = re.compile(r'\s*\);')
        hook_menu_end_regex = re.compile(r'\s*return \$items;')
        multi_line_end_regex = re.compile(r'\s*\),?\s*')

        within_hook_menu = False
        current_item_path = None
        one_line_key_value = None
        multi_line_key = None
        multi_line_value = ''

        items = defaultdict(dict)
        for line in f:
            if not within_hook_menu and line.startswith(f'function {module_name}_menu'):
                within_hook_menu = True
            elif within_hook_menu:
                hook_menu_end_match = hook_menu_end_regex.match(line)
                if hook_menu_end_match is not None:
                    within_hook_menu = False
                else:
                    item_start_match = item_start_regex.match(line)
                    if item_start_match is not None:
                        current_item_path = item_start_match.group('path')
                    else:
                        if current_item_path is not None:
                            item_end_match = item_end_regex.match(line)
                            if item_end_match is not None:
                                if one_line_key_value is not None:
                                    key, value = one_line_key_value
                                    items[current_item_path][key] = value
                                    one_line_key_value = None
                                current_item_path = None
                            else:
                                if multi_line_key is not None:
                                    multi_line_end_match = multi_line_end_regex.match(line)
                                    if multi_line_end_match is not None:
                                        items[current_item_path][multi_line_key] = multi_line_value
                                        multi_line_key = None
                                        multi_line_value = ''
                                    else:
                                        multi_line_value += line
                                else:
                                    kv_one_line_match = kv_one_line_regex.match(line)
                                    if kv_one_line_match is not None:
                                        items[current_item_path][kv_one_line_match.group('key')] = kv_one_line_match.group('value')
                                        if kv_one_line_match.group('comma_or_end') == ');':
                                            current_item_path = None
                                    else:
                                        kv_one_line_no_comma_match = kv_one_line_no_comma_regex.match(line)
                                        if kv_one_line_no_comma_match is not None:
                                            if kv_one_line_no_comma_match.group('value') == 'array(':
                                                multi_line_key = kv_one_line_no_comma_match.group('key')
                                            else:
                                                one_line_key_value = (kv_one_line_no_comma_match.group('key'), kv_one_line_no_comma_match.group('value'))

    return module_name, items


def write_drupal_8_files(module_name, items, output_dir):
    permissions = {item['access arguments'].strip() for item in items.values() if 'access callback' not in item}
    with open(os.path.join(output_dir, f'{module_name}.permissions.yml'), 'w') as f:
        for permission in sorted(permissions):
            f.write(f'{permission}:\n')
            f.write("  title: 'TODO'\n")
            f.write('\n')

    with open(os.path.join(output_dir, f'{module_name}.routing.yml'), 'w') as f_routing, open(os.path.join(output_dir, f'{module_name}.controller.inc'), 'w') as f_controller:
        files = {item['file'].strip('\'"') for item in items.values() if 'file' in item}
        write_controller_header_to_file(f_controller, module_name, files)
        for path, item in items.items():
            page_callback = item['page callback'].strip('\'"')
            write_routing_for_item_to_file(f_routing, module_name, path, item, page_callback)
            if page_callback == 'drupal_get_form':
                print(f'Form {path} needs manual work')
                write_controller_for_item_to_file(f_controller, module_name, path, item, page_callback, is_form=True)
            else:
                write_controller_for_item_to_file(f_controller, module_name, path, item, page_callback)
        write_controller_footer_to_file(f_controller)


def write_routing_for_item_to_file(f, module_name, path, item, page_callback):
    f.write(f"{module_name}.{page_callback}:\n")
    path_drupal8 = re.sub(r'%([^/]+)', r'{\1}', path)
    f.write(f"  path: '/{path_drupal8}'\n")
    f.write('  defaults:\n')
    f.write(rf"    _controller: '\naturwerk\{module_name}\{module_name.capitalize()}Controller::{CONTROLLER_PREFIX}{page_callback}'" + '\n')
    f.write(f"    _title: {item['title']}\n")
    f.write('  requirements:\n')

    if 'access callback' in item:
        if item['access callback'] == 'TRUE':
            f.write("    _access: 'TRUE'\n")
        else:
            f.write(
                rf"    _custom_access: '\naturwerk\{module_name}\{module_name.capitalize()}Controller::{ACCESS_PREFIX}{page_callback}'" + '\n')
    elif 'access arguments' in item:
        permission = item['access arguments'].strip().strip('\'"')
        f.write(f"    _permission: '{permission}'\n")
    else:
        raise ValueError(f'Neither access callback nor access arguments found for item {path}')

    f.write('\n')


def write_controller_header_to_file(f, module_name, files):
    f.write('<?php\n')
    f.write('\n')
    f.write('namespace {\n')
    for file in sorted([os.path.splitext(file)[0] for file in files]):
        f.write(f"    module_load_include('inc', '{module_name}', '{file}');\n")
    f.write('}\n')
    f.write('\n')
    f.write(f'namespace naturwerk\{module_name} {{\n')
    f.write(f'    class {module_name.capitalize()}Controller {{\n')


def write_controller_for_item_to_file(f, module_name, path, item, page_callback, is_form=False):
    # custom_access_functions.append((path,
    #                                 page_callback,
    #                                 item['access callback'],
    #                                 (item['access arguments'] if 'access arguments' in item else None)))
    # public function showOrganism($organism) {
    #     return organism_show_organism($organism);
    # }
    f.write(f"        public function {CONTROLLER_PREFIX}{page_callback}() {{\n")
    if is_form:
        f.write('            // TODO form\n')
    else:
        f.write(f"            return {page_callback}();\n")
    f.write('        }\n')
    if 'access callback' in item and item['access callback'] != 'TRUE':
        access_callback = item['access callback'].strip('\'"')
        f.write(f"        public function {ACCESS_PREFIX}{page_callback}() {{\n")
        f.write(f"            return {access_callback}();\n")
        f.write('        }\n')
    f.write('\n')


def write_controller_footer_to_file(f):
    f.write('    }\n')
    f.write('\n')


module_name, items = read_drupal_7_hook_menu(r'C:\Users\Naturwerk\Documents\GitHub\naturvielfalt_drupal_8_composer\web\modules\custom\observation')

# for k, v in items.items():
#     print(k)
#     for kk, vv in v.items():
#         print(f'{kk}={vv}')
#     print()

write_drupal_8_files(module_name, items, '.')

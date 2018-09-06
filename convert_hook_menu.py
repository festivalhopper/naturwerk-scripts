from collections import defaultdict
import os
import re


def convert_hook_menu(path_to_module, output_dir=None):
    if output_dir is None:
        output_dir = path_to_module

    module_name = os.path.basename(path_to_module)
    with open(os.path.join(path_to_module, f'{module_name}.module')) as f:
        # Alternative: multi-line regexes, find function, find items, find info in items
        item_start_regex = re.compile(r'\s*\$items\[(?P<quote>[\'"])(?P<path>.+?)(?P=quote)\]\s*=\s*array')
        # TODO newline, then );
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

        for k, v in items.items():
            print(k)
            for kk, vv in v.items():
                print(f'{kk}={vv}')
            print()


convert_hook_menu(
    r'C:\Users\Naturwerk\Documents\GitHub\naturvielfalt_drupal_8_composer\web\modules\custom\observation',
    '.'
)

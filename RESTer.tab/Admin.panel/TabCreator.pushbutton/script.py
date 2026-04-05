# -*- coding: utf-8 -*-
"""TabCreator - PyRevit pushbutton script.
Collects Revit data, then launches CPython with pywebview for the UI.
"""
import io
import os
import sys
import json
import subprocess

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_script_dir, '..', '..', '..')
_root = os.path.normpath(_root)

sys.path.insert(0, os.path.join(_root, 'app'))
from logger import get_logger
log = get_logger('tab_creator')


def get_revit_version():
    try:
        return str(__revit__.Application.VersionNumber)
    except Exception:
        return None


def _scan_items(items, source_tab, results, depth=0):
    """Recursively scan ribbon items, descending into containers."""
    item_count = 0
    for item in items:
        item_count += 1
        try:
            item_type = type(item).__name__

            # Skip separators
            if 'Separator' in item_type:
                continue

            # Recurse into container items (RowPanel, StackedPanel, etc.)
            try:
                child_items = getattr(item, 'Items', None)
                if child_items is not None:
                    _scan_items(child_items, source_tab, results, depth + 1)
            except Exception:
                pass

            # Skip list buttons (already recursed into children above)
            if 'ListButton' in item_type:
                continue

            # Try every possible way to get a command identifier
            cmd_str = ''
            try:
                cid = getattr(item, 'CommandId', None)
                if cid is not None:
                    cmd_str = str(cid)
            except Exception:
                pass

            if not cmd_str:
                try:
                    iid = getattr(item, 'Id', None)
                    if iid is not None:
                        cmd_str = str(iid)
                except Exception:
                    pass

            if not cmd_str or cmd_str == 'None' or 'RibbonListButton' in cmd_str:
                continue

            # Get display name
            name = ''
            try:
                txt = getattr(item, 'Text', None)
                if txt:
                    name = str(txt)
            except Exception:
                pass
            if not name:
                try:
                    nm = getattr(item, 'Name', None)
                    if nm:
                        name = str(nm)
                except Exception:
                    pass
            if not name:
                name = cmd_str

            results.append({
                'name': name,
                'commandId': cmd_str,
                'sourceTab': source_tab,
                'icon': None,
            })
        except Exception as e:
            log.debug('Skipping item: %s', e)
            continue

    if depth == 0:
        log.debug('Tab %s: scanned %d raw items', source_tab, item_count)
        # Diagnostic: dump item details for Add-Ins tab (to find Kinship)
        # or any tab with items but no commands
        dump_tab = (source_tab == 'Add-Ins') or (item_count > 0 and not any(r.get('sourceTab') == source_tab for r in results))
        if dump_tab:
            for i, item in enumerate(items):
                if i >= 5:
                    break
                try:
                    props = {}
                    for attr in ['CommandId', 'Id', 'Text', 'Name', 'CommandParameter', 'Tag', 'Description', 'ToolTip']:
                        try:
                            val = getattr(item, attr, '---')
                            props[attr] = str(val) if val is not None else 'None'
                        except Exception:
                            props[attr] = 'ERR'
                    log.info('Tab %s item[%d] type=%s props=%s', source_tab, i, type(item).__name__, props)
                except Exception:
                    pass


def get_installed_commands():
    results = []
    try:
        import clr
        clr.AddReference('AdWindows')
        from Autodesk.Windows import ComponentManager

        ribbon = ComponentManager.Ribbon
        if ribbon is None or ribbon.Tabs is None or ribbon.Tabs.Count == 0:
            log.warning('Ribbon not ready or empty - Revit may still be loading')
            return results
        log.info('Ribbon found, tabs: %d', ribbon.Tabs.Count)

        for tab in ribbon.Tabs:
            try:
                source_tab = tab.Title
                log.debug('Scanning tab: %s', source_tab)
            except Exception as e:
                log.error('Error reading tab title: %s', e)
                continue

            for panel in tab.Panels:
                try:
                    panel_source = panel.Source
                    if panel_source is None:
                        continue
                    items = panel_source.Items
                    if items is None:
                        continue
                except Exception as e:
                    log.debug('Skipping panel: %s', e)
                    continue

                _scan_items(items, source_tab, results)

    except Exception as e:
        log.error('Failed to scan ribbon: %s', e)
        import traceback
        log.error(traceback.format_exc())

    log.info('Scan complete: %d commands found', len(results))
    return results


# Collect Revit data while we have access to the API
log.info('Collecting Revit data...')
revit_version = get_revit_version()
commands = get_installed_commands()
log.info('Revit %s, found %d commands', revit_version, len(commands))

# Write to temp file for CPython to read
revit_data = {
    'revit_version': revit_version,
    'commands': commands,
}
data_path = os.path.join(_root, 'app', '_revit_data.json')
with io.open(data_path, 'w', encoding='utf-8') as f:
    json.dump(revit_data, f)
log.info('Revit data written to %s', data_path)

# Launch CPython with tab_creator.py
launcher = os.path.join(_root, 'app', 'tab_creator.py')
log.info('Launching CPython: %s', launcher)
subprocess.Popen(
    'python "{}" & pause'.format(launcher),
    shell=True,
)
log.info('TabCreator launched')

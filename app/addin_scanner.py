# -*- coding: utf-8 -*-
import os
import json
from logger import get_logger

log = get_logger('addin_scanner')

PROTECTED_ADDINS = {'pyRevit.addin'}

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lookup_path = os.path.join(_root, 'lookup', 'addin_lookup.json')
_overrides_path = os.path.join(_root, 'app', 'user_addin_overrides.json')


def load_addin_lookup():
    with open(_lookup_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _load_overrides():
    if os.path.exists(_overrides_path):
        with open(_overrides_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_overrides(overrides):
    with open(_overrides_path, 'w', encoding='utf-8') as f:
        json.dump(overrides, f, indent=2)


def _record_fuzzy_match(tab_name, addin_path):
    log.info('Fuzzy match: %s -> %s', tab_name, addin_path)
    overrides = _load_overrides()
    overrides[tab_name] = addin_path
    _save_overrides(overrides)


def _get_appdata():
    """Get APPDATA path, return None on non-Windows."""
    return os.environ.get('APPDATA')


def get_addins_dirs(revit_version):
    """Return all directories where .addin files may live for a given Revit version."""
    dirs = []
    ver = str(revit_version)

    # 1. User addins: %APPDATA%\Autodesk\Revit\Addins\{version}\
    appdata = _get_appdata()
    if appdata:
        user_dir = os.path.join(appdata, 'Autodesk', 'Revit', 'Addins', ver)
        if os.path.isdir(user_dir):
            dirs.append(user_dir)

    # 2. Machine addins: C:\ProgramData\Autodesk\Revit\Addins\{version}\
    programdata = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
    machine_dir = os.path.join(programdata, 'Autodesk', 'Revit', 'Addins', ver)
    if os.path.isdir(machine_dir):
        dirs.append(machine_dir)

    # 3. Revit install folder: C:\Program Files\Autodesk\Revit 20xx\
    program_files = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    revit_dir = os.path.join(program_files, 'Autodesk', 'Revit ' + ver)
    if os.path.isdir(revit_dir):
        dirs.append(revit_dir)

    log.debug('Addin search dirs for Revit %s: %s', ver, dirs)
    return dirs


def get_addins_dir(revit_version):
    """Return the primary (user) addins dir for backwards compat."""
    appdata = _get_appdata()
    if not appdata:
        return None
    return os.path.join(appdata, 'Autodesk', 'Revit', 'Addins', str(revit_version))


def get_installed_revit_versions():
    versions = set()

    # Check user addins dir
    appdata = _get_appdata()
    if appdata:
        addins_root = os.path.join(appdata, 'Autodesk', 'Revit', 'Addins')
        if os.path.isdir(addins_root):
            for d in os.listdir(addins_root):
                if d.isdigit() and os.path.isdir(os.path.join(addins_root, d)):
                    versions.add(d)

    # Check ProgramData addins dir
    programdata = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
    pd_root = os.path.join(programdata, 'Autodesk', 'Revit', 'Addins')
    if os.path.isdir(pd_root):
        for d in os.listdir(pd_root):
            if d.isdigit() and os.path.isdir(os.path.join(pd_root, d)):
                versions.add(d)

    # Check Program Files for Revit installs
    program_files = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    if os.path.isdir(program_files):
        for d in os.listdir(program_files):
            if d.startswith('Revit ') and d[6:].isdigit():
                versions.add(d[6:])

    result = sorted(versions)
    log.info('Installed Revit versions: %s', result)
    return result


def _find_all_addin_files(search_dirs):
    """Recursively find all .addin and .addin.inactive files across all dirs."""
    addin_files = {}  # filename -> full_path
    for base_dir in search_dirs:
        for dirpath, dirnames, filenames in os.walk(base_dir):
            for f in filenames:
                if f.endswith('.addin') or f.endswith('.addin.inactive'):
                    full_path = os.path.join(dirpath, f)
                    # Keep first found (user dir takes priority since it's listed first)
                    if f not in addin_files:
                        addin_files[f] = full_path
    return addin_files


def _search_addin_contents(tab_name, addin_files):
    """Search inside .addin file contents for the tab name string."""
    tab_lower = tab_name.lower()
    for fname, fpath in addin_files.items():
        if not fname.endswith('.addin'):
            continue
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                contents = f.read().lower()
            if tab_lower in contents:
                log.info('Content match: "%s" found in %s', tab_name, fpath)
                return fname, fpath
        except (IOError, OSError):
            continue
    return None, None


def _fuzzy_find(tab_name, search_dirs):
    """Check overrides, then filename match, then content search across all dirs."""
    overrides = _load_overrides()
    if tab_name in overrides:
        cached_path = overrides[tab_name]
        if os.path.exists(cached_path):
            return os.path.basename(cached_path), cached_path

    addin_files = _find_all_addin_files(search_dirs)

    # Filename match first
    tab_lower = tab_name.lower()
    for fname, fpath in addin_files.items():
        if fname.endswith('.addin') and tab_lower in fname.lower():
            _record_fuzzy_match(tab_name, fpath)
            return fname, fpath

    # Content search
    fname, fpath = _search_addin_contents(tab_name, addin_files)
    if fname:
        _record_fuzzy_match(tab_name, fpath)
        return fname, fpath

    return None, None


def check_addins(required_addins, revit_version):
    """Returns dict: { tabName: 'present' | 'missing' | 'unknown' }"""
    log.info('Checking addins for Revit %s: %s', revit_version, required_addins)
    lookup = load_addin_lookup()
    search_dirs = get_addins_dirs(revit_version)

    if not search_dirs:
        log.warning('No addin directories found for Revit %s', revit_version)
        return {name: 'unknown' for name in required_addins}

    addin_files = _find_all_addin_files(search_dirs)
    active_filenames = {f for f in addin_files.keys() if f.endswith('.addin')}

    results = {}
    for tab_name in required_addins:
        entry = lookup.get(tab_name)
        if entry:
            results[tab_name] = 'present' if entry['file'] in active_filenames else 'missing'
        else:
            fname, fpath = _fuzzy_find(tab_name, search_dirs)
            if fname:
                results[tab_name] = 'present'
            else:
                results[tab_name] = 'unknown'

    log.info('Addin check results: %s', results)
    return results


def apply_hide_rules(hide_rules, revit_version):
    """Rename .addin -> .addin.inactive for each tab in hide_rules across all locations."""
    log.info('Applying hide rules for Revit %s: %s', revit_version, hide_rules)
    lookup = load_addin_lookup()
    search_dirs = get_addins_dirs(revit_version)

    if not search_dirs:
        log.warning('No addin directories found')
        return

    addin_files = _find_all_addin_files(search_dirs)

    for tab_name in hide_rules:
        if tab_name == 'pyRevit':
            log.debug('Skipping protected addin: pyRevit')
            continue

        entry = lookup.get(tab_name)
        if entry and entry['file'] in addin_files:
            fpath = addin_files[entry['file']]
        else:
            fname, fpath = _fuzzy_find(tab_name, search_dirs)

        if not fpath:
            log.warning('No .addin file found for: %s', tab_name)
            continue

        dest = fpath + '.inactive'
        if os.path.exists(fpath) and not fpath.endswith('.inactive'):
            os.rename(fpath, dest)
            log.info('Hidden: %s -> %s.inactive', fpath, fpath)


def restore_all_addins(revit_version):
    """Rename all .addin.inactive -> .addin across all locations (skip pyRevit)."""
    log.info('Restoring all addins for Revit %s', revit_version)
    search_dirs = get_addins_dirs(revit_version)

    for base_dir in search_dirs:
        for dirpath, dirnames, filenames in os.walk(base_dir):
            for f in filenames:
                if f.endswith('.addin.inactive') and f not in {p + '.inactive' for p in PROTECTED_ADDINS}:
                    src = os.path.join(dirpath, f)
                    dest = src.replace('.addin.inactive', '.addin')
                    os.rename(src, dest)
                    log.info('Restored: %s', dest)


def disable_non_required_addins(required_addins, revit_version):
    """Disable all .addin files except required ones and protected ones across all locations."""
    log.info('Disabling non-required addins for Revit %s (keeping: %s)', revit_version, required_addins)
    lookup = load_addin_lookup()
    keep_files = {lookup[a]['file'] for a in required_addins if a in lookup}
    keep_files.update(PROTECTED_ADDINS)
    search_dirs = get_addins_dirs(revit_version)

    for base_dir in search_dirs:
        for dirpath, dirnames, filenames in os.walk(base_dir):
            for f in filenames:
                if f.endswith('.addin') and f not in keep_files:
                    src = os.path.join(dirpath, f)
                    os.rename(src, src + '.inactive')
                    log.info('Disabled: %s', src)

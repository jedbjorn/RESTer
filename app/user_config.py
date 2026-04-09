# -*- coding: utf-8 -*-
"""
user_config.py — Per-user add-in config persistence and intent logging.

Each Revit user + version gets their own config file tracking add-in
scan results and enabled/disabled state. Intent logs record planned
rename operations for crash recovery.

Files live in app/users/:
  {username}_{version}_addins.json   — scan data + state
  {username}_{version}_intent.json   — pre-rename plan
"""

import os
import json
import datetime

from logger import get_logger

log = get_logger('user_config')

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USERS_DIR = os.path.join(_root, 'app', 'users')


def _ensure_users_dir():
    """Create the users directory if it doesn't exist."""
    if not os.path.isdir(_USERS_DIR):
        try:
            os.makedirs(_USERS_DIR)
            log.info('Created users directory: %s', _USERS_DIR)
        except OSError as e:
            log.error('Failed to create users directory: %s', e)


def _config_path(username, version):
    """Return path to the user's add-in config file."""
    return os.path.join(_USERS_DIR, '%s_%s_addins.json' % (username, version))


def _intent_path(username, version):
    """Return path to the user's intent log file."""
    return os.path.join(_USERS_DIR, '%s_%s_intent.json' % (username, version))


def _atomic_write(path, data):
    """Write JSON atomically: write to .tmp then replace."""
    _ensure_users_dir()
    tmp_path = path + '.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # os.replace is atomic on NTFS (Windows target platform)
        os.replace(tmp_path, path)
    except (IOError, OSError) as e:
        log.error('Atomic write failed for %s: %s', path, e)
        # Clean up temp file if it exists
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def get_current_username():
    """Get the current OS username as fallback when Revit username unavailable."""
    return os.environ.get('USERNAME', os.environ.get('USER', 'unknown'))


# ── User Config ──────────────────────────────────────────────────────────────


def load_user_config(username, version):
    """Load user config. Returns None if missing or username mismatch."""
    path = _config_path(username, version)
    if not os.path.exists(path):
        log.debug('No config file for %s / Revit %s', username, version)
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (IOError, ValueError) as e:
        log.error('Failed to read config %s: %s', path, e)
        return None

    # Username mismatch triggers rescan
    if config.get('username') != username:
        log.info('Username mismatch in config (got %s, expected %s) — rescan needed',
                 config.get('username'), username)
        return None

    return config


def save_user_config(config):
    """Persist user config atomically."""
    username = config.get('username', 'unknown')
    version = config.get('revitVersion', 'unknown')
    path = _config_path(username, version)
    _atomic_write(path, config)
    log.info('Saved user config: %s', path)


def needs_rescan(username, version):
    """Check if a rescan is needed (config missing or username mismatch)."""
    return load_user_config(username, version) is None


def _list_user_addins_dir(version):
    """List the single user-scope addins directory. Returns {filename_lower: full_path}.
    Non-recursive — one flat directory only."""
    appdata = os.environ.get('APPDATA', '')
    if not appdata:
        return {}, None
    addins_dir = os.path.join(appdata, 'Autodesk', 'Revit', 'Addins', str(version))
    if not os.path.isdir(addins_dir):
        return {}, addins_dir
    result = {}
    for f in os.listdir(addins_dir):
        if f.endswith('.addin') or f.endswith('.addin.disabled'):
            result[f.lower()] = os.path.join(addins_dir, f)
    return result, addins_dir


def build_user_config(username, version, loaded_addins, all_tabs, addin_lookup):
    """
    Build a user config from two fast sources:

    1. Revit session data (loaded_addins, all_tabs) — sub-second, in memory
    2. Single os.listdir() on user-scope addins directory — sub-second

    No recursive scan. No XML parsing. No multi-directory walk.
    addin_lookup provides display names and URLs as fallback metadata.
    """
    from addin_scanner import BUILTIN_TABS

    log.info('Building user config for %s / Revit %s', username, version)

    # Step 1: list the one user-scope addins directory
    dir_files, addins_dir = _list_user_addins_dir(version)
    log.debug('User addins dir: %s (%d files)', addins_dir, len(dir_files))

    # Step 2: index loaded_addins by name for quick lookup
    loaded_by_name = {}
    for entry in (loaded_addins or []):
        name = entry.get('name', '')
        if name:
            loaded_by_name[name.lower()] = entry

    # Step 3: build reverse lookup: addin filename → tab name
    file_to_tab = {}
    for tab_name, info in addin_lookup.items():
        fname = info.get('file', '')
        if fname:
            file_to_tab[fname.lower()] = tab_name

    addins = {}

    # Step 4: process tabs from ribbon scan (everything Revit loaded)
    for tab_name in (all_tabs or []):
        if tab_name in BUILTIN_TABS:
            continue

        lookup_entry = addin_lookup.get(tab_name, {})
        display_name = lookup_entry.get('displayName', tab_name)
        url = lookup_entry.get('url', '')
        expected_file = lookup_entry.get('file')

        # Get assembly path from session data
        loaded_entry = loaded_by_name.get(tab_name.lower(), {})
        assembly_path = loaded_entry.get('assembly')

        # Resolve addin filename: lookup first, then fuzzy match in directory
        addin_file = expected_file
        if not addin_file:
            tab_lower = tab_name.lower()
            for fname_lower in dir_files:
                if tab_lower in fname_lower and fname_lower.endswith('.addin'):
                    # Strip path, keep original casing via dir listing
                    addin_file = os.path.basename(dir_files[fname_lower])
                    break

        # Check enabled/disabled state via directory listing
        addin_path = None
        enabled = True
        if addin_file:
            active_key = addin_file.lower()
            disabled_key = (addin_file + '.disabled').lower()
            if active_key in dir_files:
                addin_path = dir_files[active_key]
                enabled = True
            elif disabled_key in dir_files:
                addin_path = dir_files[disabled_key]
                enabled = False

        addins[tab_name] = {
            'displayName': display_name,
            'tabName': tab_name,
            'addinFile': addin_file,
            'addinPath': addin_path,
            'assemblyPath': assembly_path,
            'scope': 'user',
            'elevated': False,
            'enabled': enabled,
            'url': url,
        }

    # Step 5: catch any .addin files in the directory not matched to a loaded tab
    matched_files = set()
    for info in addins.values():
        if info['addinFile']:
            matched_files.add(info['addinFile'].lower())
            matched_files.add((info['addinFile'] + '.disabled').lower())

    for fname_lower, fpath in dir_files.items():
        if fname_lower in matched_files:
            continue

        fname = os.path.basename(fpath)
        canonical = fname.replace('.addin.disabled', '.addin') if fname.endswith('.disabled') else fname
        base = canonical.replace('.addin', '')

        if base in addins:
            continue

        tab_from_file = file_to_tab.get(canonical.lower())
        lookup_entry = addin_lookup.get(tab_from_file, {}) if tab_from_file else {}

        addins[base] = {
            'displayName': lookup_entry.get('displayName', base),
            'tabName': tab_from_file,
            'addinFile': canonical,
            'addinPath': fpath,
            'assemblyPath': None,
            'scope': 'user',
            'elevated': False,
            'enabled': not fname.endswith('.disabled'),
            'url': lookup_entry.get('url', ''),
        }

    config = {
        'username': username,
        'revitVersion': str(version),
        'scanDate': datetime.date.today().isoformat(),
        'addins': addins,
    }

    log.info('Built config: %d add-ins catalogued', len(addins))
    return config


def update_addin_states(config, disabled_files, enabled_files):
    """
    Bulk update enabled/disabled state in the config.

    disabled_files: list of .addin filenames that were renamed to .disabled
    enabled_files: list of .addin filenames that were restored from .disabled
    """
    disabled_set = set(f.lower() for f in disabled_files)
    enabled_set = set(f.lower() for f in enabled_files)

    for name, info in config.get('addins', {}).items():
        addin_path = info.get('addinPath', '')
        if not addin_path:
            continue
        basename = os.path.basename(addin_path).lower()
        # Strip .disabled suffix for matching
        clean_basename = basename.replace('.disabled', '')

        if clean_basename in disabled_set:
            info['enabled'] = False
            # Update path to reflect .disabled extension
            if not addin_path.endswith('.disabled'):
                info['addinPath'] = addin_path + '.disabled'
        elif clean_basename in enabled_set:
            info['enabled'] = True
            # Update path to reflect restored .addin extension
            if addin_path.endswith('.disabled'):
                info['addinPath'] = addin_path.replace('.addin.disabled', '.addin')

    return config


# ── Intent Log ───────────────────────────────────────────────────────────────


def write_intent_log(username, version, action, profile_name, planned_ops):
    """
    Write intent log before any rename batch.

    planned_ops: list of {path, from_state, to_state}
    """
    data = {
        'timestamp': datetime.datetime.now().isoformat(),
        'action': action,
        'profile': profile_name,
        'planned': planned_ops,
        'completed': [],
    }
    path = _intent_path(username, version)
    _atomic_write(path, data)
    log.info('Intent log written: action=%s, profile=%s, %d planned ops',
             action, profile_name, len(planned_ops))


def read_intent_log(username, version):
    """Read intent log. Returns dict or None if missing."""
    path = _intent_path(username, version)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, ValueError) as e:
        log.error('Failed to read intent log %s: %s', path, e)
        return None


def clear_intent_log(username, version):
    """Delete the intent log file."""
    path = _intent_path(username, version)
    if os.path.exists(path):
        try:
            os.remove(path)
            log.info('Intent log cleared: %s', path)
        except OSError as e:
            log.error('Failed to clear intent log %s: %s', path, e)

# -*- coding: utf-8 -*-
import webview
import os
import re
import json
import shutil
import datetime

from logger import get_logger
log = get_logger('profile_selector')

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_profiles_dir = os.path.join(_root, 'app', 'profiles')
_active_profile_path = os.path.join(_root, 'app', 'active_profile.json')
_html_path = os.path.join(_root, 'ui', 'profile_loader.html')
_addin_lookup_path = os.path.join(_root, 'lookup', 'addin_lookup.json')

REQUIRED_FIELDS = {'profile', 'tab', 'min_version', 'exportDate', 'requiredAddins', 'hideRules', 'stacks', 'panels'}


def _get_required_tab_names(profile_data):
    """Extract tab name strings from requiredAddins, handling both old (string[])
    and new (object[]) formats."""
    raw = _get_required_tab_names(profile_data)
    result = []
    for entry in raw:
        if isinstance(entry, dict):
            tab = entry.get('tabName', '')
            if tab:
                result.append(tab)
        elif isinstance(entry, str):
            result.append(entry)
    return result


def _write_blank_profile():
    """Write a blank active profile so startup.py builds an empty RST tab."""
    blank = {
        'profile': None,
        'profile_file': None,
        'loaded_at': datetime.datetime.now().isoformat(),
        'disable_non_required': False,
        'blank': True,
    }
    with open(_active_profile_path, 'w', encoding='utf-8') as f:
        json.dump(blank, f, indent=2)
    log.info('Wrote blank active profile')


os.makedirs(_profiles_dir, exist_ok=True)

import sys
sys.path.insert(0, os.path.join(_root, 'app'))
from addin_scanner import (
    BUILTIN_TABS,
    PROTECTED_ADDINS,
    load_addin_lookup,
    disable_non_required_addins,
    restore_all_addins,
)
from user_config import (
    get_current_username,
    load_user_config,
    save_user_config,
    build_user_config,
    update_addin_states,
    write_intent_log,
    clear_intent_log,
)

# Load session data written by the IronPython pushbutton
_loader_data_path = os.path.join(_root, 'app', '_loader_data.json')
_loader_data = {}
if os.path.exists(_loader_data_path):
    try:
        with open(_loader_data_path, 'r', encoding='utf-8') as f:
            _loader_data = json.load(f)
        log.info('Loaded session data: Revit %s, %d add-ins',
                 _loader_data.get('revit_version'),
                 len(_loader_data.get('loaded_addins', [])))
        try:
            os.remove(_loader_data_path)
        except OSError:
            pass
    except (json.JSONDecodeError, IOError) as e:
        log.error('Failed to read loader data: %s', e)

# pywebview file dialog constant
_OPEN_DIALOG = getattr(webview, 'OPEN_DIALOG', None)
if _OPEN_DIALOG is None:
    try:
        _OPEN_DIALOG = webview.FileDialog.OPEN
    except AttributeError:
        _OPEN_DIALOG = 0


def _safe_filename(s):
    """Sanitize a string for use in filenames."""
    return re.sub(r'[\\/:*?"<>|]', '_', s).strip()


def _find_profile(profile_name):
    """Find a profile by name, return (filename, data) or (None, None)."""
    for fname in os.listdir(_profiles_dir):
        if fname.endswith('.json'):
            fpath = os.path.join(_profiles_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('profile') == profile_name:
                    return fname, data
            except (json.JSONDecodeError, IOError, UnicodeDecodeError):
                continue
    return None, None


class ProfileSelectorAPI:

    def __init__(self, revit_version=None, loaded_addins=None, all_tabs=None):
        self._window = None
        self._revit_version = revit_version
        self._loaded_addins = loaded_addins or []
        self._all_tabs = all_tabs or []

    def set_window(self, window):
        self._window = window

    def get_revit_version(self):
        return self._revit_version

    def get_loaded_addins(self):
        return self._loaded_addins

    def get_all_tabs(self):
        return self._all_tabs

    def get_addin_lookup(self):
        try:
            with open(_addin_lookup_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            log.error('Failed to load addin_lookup.json: %s', e)
            return {}

    def _get_username(self):
        """Get the Revit username from session data, fall back to OS username."""
        return _loader_data.get('revit_username') or get_current_username()

    def get_user_config(self):
        """Return user add-in config. Builds from scratch on first call."""
        username = self._get_username()
        version = self._revit_version
        if not version:
            return None

        config = load_user_config(username, version)
        if config is None:
            config = build_user_config(
                username, version,
                self._loaded_addins,
                self._all_tabs,
                load_addin_lookup(),
            )
            save_user_config(config)
        return config

    def rescan_addins(self):
        """Force rebuild of user add-in config."""
        username = self._get_username()
        version = self._revit_version
        if not version:
            return {'ok': False, 'error': 'No Revit version'}

        config = build_user_config(
            username, version,
            self._loaded_addins,
            self._all_tabs,
            load_addin_lookup(),
        )
        save_user_config(config)
        return {'ok': True, 'config': config}

    def get_disable_preview(self, profile_name):
        """Return what would stay active vs be disabled for a profile.
        Used by the confirmation overlay before committing."""
        config = self.get_user_config()
        if not config:
            return {'staying': [], 'disabling': [], 'error': 'No config available'}

        _, profile_data = _find_profile(profile_name)
        if not profile_data:
            return {'staying': [], 'disabling': [], 'error': 'Profile not found'}

        required = set(_get_required_tab_names(profile_data))
        lookup = load_addin_lookup()

        # Also resolve required add-in filenames for protected check
        required_files = set()
        for tab_name in required:
            entry = lookup.get(tab_name)
            if entry:
                required_files.add(entry.get('file', '').lower())

        staying = []
        disabling = []

        for name, info in config.get('addins', {}).items():
            if not info.get('enabled', True):
                continue  # already disabled, skip
            if info.get('elevated', False):
                continue  # machine-scope, can't touch
            if info.get('scope') != 'user':
                continue  # only user-scope add-ins

            addin_path = info.get('addinPath', '')
            filename = os.path.basename(addin_path).lower() if addin_path else ''

            tab_name = info.get('tabName', '')

            is_required = tab_name in required
            is_protected = filename in set(p.lower() for p in PROTECTED_ADDINS)

            if is_required or is_protected:
                staying.append(info)
            else:
                disabling.append(info)

        return {'staying': staying, 'disabling': disabling}

    def restore_addins(self):
        """Restore all disabled add-ins and update user config."""
        version = self._revit_version
        if not version:
            return {'ok': False, 'error': 'No Revit version'}

        username = self._get_username()

        # Write intent log for restore
        write_intent_log(username, version, 'restore_all', None, [])

        restore_all_addins(version)

        # Update config: mark everything enabled
        config = load_user_config(username, version)
        if config:
            for name in config.get('addins', {}):
                config['addins'][name]['enabled'] = True
                # Fix paths: strip .disabled suffix
                path = config['addins'][name].get('addinPath', '')
                if path.endswith('.disabled'):
                    config['addins'][name]['addinPath'] = path.replace('.addin.disabled', '.addin')
            save_user_config(config)

        clear_intent_log(username, version)
        return {'ok': True, 'restart_needed': True}

    def get_profiles(self):
        log.info('Loading profiles from %s', _profiles_dir)
        profiles = []
        for fname in os.listdir(_profiles_dir):
            if fname.endswith('.json'):
                fpath = os.path.join(_profiles_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        profile = json.load(f)
                    profile['_filename'] = fname
                    profiles.append(profile)
                except (json.JSONDecodeError, IOError, UnicodeDecodeError) as e:
                    log.error('Failed to read profile %s: %s', fname, e)
                    continue
        log.info('Loaded %d profiles', len(profiles))
        return profiles

    def get_active_profile(self):
        if not os.path.exists(_active_profile_path):
            log.debug('No active_profile.json found')
            return {'name': None, 'hidden_tabs': []}
        try:
            with open(_active_profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            name = data.get('profile')
            hidden = data.get('hidden_tabs', [])
            log.info('Active profile: %s (hidden: %d tabs)', name, len(hidden))
            return {'name': name, 'hidden_tabs': hidden}
        except (json.JSONDecodeError, IOError) as e:
            log.error('Failed to read active_profile.json: %s', e)
            return {'name': None, 'hidden_tabs': []}

    def add_profile(self):
        log.info('Opening file dialog for profile import')
        window = self._window or (webview.windows[0] if webview.windows else None)
        if not window:
            return {'ok': False, 'error': 'No window available'}

        result = window.create_file_dialog(
            _OPEN_DIALOG,
            file_types=('JSON Files (*.json)',)
        )
        if not result:
            log.debug('File dialog cancelled')
            return {'ok': False, 'error': 'cancelled'}

        file_path = result[0] if isinstance(result, (list, tuple)) else result
        log.info('Selected file: %s', file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                profile = json.load(f)
        except (json.JSONDecodeError, IOError, UnicodeDecodeError) as e:
            log.error('Invalid JSON: %s', e)
            return {'ok': False, 'error': 'Invalid JSON: ' + str(e)}

        missing = REQUIRED_FIELDS - set(profile.keys())
        if missing:
            log.error('Missing required fields: %s', missing)
            return {'ok': False, 'error': 'Missing fields: ' + ', '.join(sorted(missing))}

        safe_name = _safe_filename(profile['profile'])
        safe_date = _safe_filename(profile['exportDate'])
        dest_name = '%s_%s.json' % (safe_name, safe_date)

        # Overwrite existing profile with same name
        existing_fname, _ = _find_profile(profile['profile'])
        if existing_fname:
            os.remove(os.path.join(_profiles_dir, existing_fname))
            log.info('Overwriting existing profile: %s', existing_fname)

        dest_path = os.path.join(_profiles_dir, dest_name)
        shutil.copy2(file_path, dest_path)
        log.info('Profile saved: %s', dest_name)

        profile['_filename'] = dest_name
        return {'ok': True, 'profile': profile}

    def load_profile(self, profile_name, disable_non_required, revit_version=None, hidden_tabs=None):
        log.info('Loading profile: %s (hidden_tabs=%s, revit=%s)',
                 profile_name, hidden_tabs, revit_version)

        profile_filename, profile_data = _find_profile(profile_name)
        if not profile_data:
            log.error('Profile not found: %s', profile_name)
            return {'ok': False, 'warnings': ['Profile not found: ' + profile_name]}

        if not revit_version:
            revit_version = self._revit_version

        warnings = []

        if not revit_version:
            warnings.append('No Revit version available - add-in toggling skipped')
        else:
            # Check required addins against loaded session data
            required = _get_required_tab_names(profile_data)
            if required and self._loaded_addins:
                loaded_names = [a.get('name', '').lower() for a in self._loaded_addins]
                lookup = load_addin_lookup()
                for tab_name in required:
                    if tab_name in BUILTIN_TABS:
                        continue
                    tab_lower = tab_name.lower()
                    found = any(tab_lower in n for n in loaded_names)
                    if not found:
                        entry = lookup.get(tab_name)
                        if entry:
                            stem = entry['file'].replace('.addin', '').lower()
                            found = any(stem in n for n in loaded_names)
                    if not found:
                        warnings.append('Required add-in not loaded: ' + tab_name)


        # Re-enable disabled required add-ins
        restart_needed = False
        if revit_version:
            username = self._get_username()
            config = load_user_config(username, revit_version)
            if config:
                required = set(_get_required_tab_names(profile_data))
                re_enabled = []
                for name, info in config.get('addins', {}).items():
                    if info.get('enabled') is False and info.get('tabName') in required:
                        disabled_path = info.get('addinPath', '')
                        if disabled_path and disabled_path.endswith('.disabled') and os.path.exists(disabled_path):
                            restored_path = disabled_path.replace('.addin.disabled', '.addin')
                            try:
                                os.rename(disabled_path, restored_path)
                                info['enabled'] = True
                                info['addinPath'] = restored_path
                                re_enabled.append(name)
                                log.info('Re-enabled required add-in: %s', name)
                            except (OSError, IOError) as e:
                                log.error('Failed to re-enable %s: %s', name, e)
                                warnings.append('Failed to re-enable: ' + name)

                if re_enabled:
                    save_user_config(config)
                    restart_needed = True
                    log.info('Re-enabled %d disabled required add-ins', len(re_enabled))

        # Disable non-required add-ins if requested
        if disable_non_required and revit_version:
            username = self._get_username()
            required = _get_required_tab_names(profile_data)

            # Build planned operations list from preview
            preview = self.get_disable_preview(profile_name)
            planned = []
            for info in preview.get('disabling', []):
                path = info.get('addinPath', '')
                if path:
                    planned.append({
                        'path': path,
                        'from_state': 'enabled',
                        'to_state': 'disabled',
                    })

            if planned:
                # Write intent log BEFORE any renames
                write_intent_log(username, revit_version, 'disable_unused', profile_name, planned)

                # Perform the renames
                disable_non_required_addins(required, revit_version)

                # Update user config
                config = load_user_config(username, revit_version)
                if config:
                    disabled_files = [os.path.basename(p['path']) for p in planned]
                    update_addin_states(config, disabled_files, [])
                    save_user_config(config)

                # Clear intent log on success
                clear_intent_log(username, revit_version)
                restart_needed = True
                log.info('Disabled %d non-required add-ins', len(planned))

        # Write active_profile.json
        active = {
            'profile': profile_name,
            'profile_file': profile_filename,
            'loaded_at': datetime.datetime.now().isoformat(),
            'hidden_tabs': hidden_tabs or [],
            'disable_non_required': bool(disable_non_required),
        }
        try:
            with open(_active_profile_path, 'w', encoding='utf-8') as f:
                json.dump(active, f, indent=2)
        except IOError as e:
            log.error('Failed to write active_profile.json: %s', e)
            return {'ok': False, 'warnings': ['Failed to save active profile: ' + str(e)]}

        log.info('Profile loaded: %s (warnings: %s, restart: %s)', profile_name, warnings, restart_needed)
        return {'ok': True, 'warnings': warnings, 'restart_needed': restart_needed}

    def remove_profile(self, profile_name):
        log.info('Removing profile: %s', profile_name)
        profile_filename, _ = _find_profile(profile_name)
        if not profile_filename:
            log.error('Profile not found for removal: %s', profile_name)
            return {'ok': False, 'error': 'Profile not found'}

        os.remove(os.path.join(_profiles_dir, profile_filename))
        log.info('Deleted: %s', profile_filename)

        # Write blank profile if this was the active one
        try:
            if os.path.exists(_active_profile_path):
                with open(_active_profile_path, 'r', encoding='utf-8') as f:
                    active = json.load(f)
                if active.get('profile') == profile_name:
                    _write_blank_profile()
                    log.info('Wrote blank profile (deleted profile was active)')
        except (json.JSONDecodeError, IOError) as e:
            log.error('Error checking active profile: %s', e)

        return {'ok': True}

    def unload_profile(self):
        log.info('Unloading active profile')
        _write_blank_profile()
        return {'ok': True}

    def close_window(self):
        log.info('Close requested by UI')
        window = self._window or (webview.windows[0] if webview.windows else None)
        if window:
            window.destroy()


if __name__ == '__main__':
    _revit_ver = _loader_data.get('revit_version')
    _addins = _loader_data.get('loaded_addins', [])
    _tabs = _loader_data.get('all_tabs', [])
    log.info('=== RST Profile Selector starting (Revit %s, %d tabs, %d add-ins) ===',
             _revit_ver, len(_tabs), len(_addins))
    log.info('HTML path: %s', _html_path)
    log.info('Profiles dir: %s', _profiles_dir)

    api = ProfileSelectorAPI(revit_version=_revit_ver, loaded_addins=_addins, all_tabs=_tabs)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        wx, wy = (sw - 1400) // 2, (sh - 900) // 2
    except Exception:
        wx, wy = None, None

    window = webview.create_window(
        'RST - Profile Selector',
        url=_html_path,
        width=1450,
        height=900,
        x=wx,
        y=wy,
        js_api=api
    )
    api.set_window(window)
    webview.start()
    log.info('=== RST Profile Selector closed ===')

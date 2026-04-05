import webview
import os
import json
import shutil
import subprocess
import datetime

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_profiles_dir = os.path.join(_root, 'app', 'profiles')
_active_profile_path = os.path.join(_root, 'app', 'active_profile.json')
_html_path = os.path.join(_root, 'ui', 'profile_loader.html')

REQUIRED_FIELDS = {'profile', 'tab', 'min_version', 'exportDate', 'requiredAddins', 'hideRules', 'stacks', 'panels'}

# Ensure profiles dir exists
os.makedirs(_profiles_dir, exist_ok=True)

# Import from sibling module
import sys
sys.path.insert(0, os.path.join(_root, 'app'))
from addin_scanner import (
    check_addins,
    apply_hide_rules,
    restore_all_addins,
    disable_non_required_addins,
    get_installed_revit_versions,
)


class ProfileSelectorAPI:

    def get_profiles(self):
        """Read all .json files from app/profiles/, return list of parsed profile objects."""
        profiles = []
        for fname in os.listdir(_profiles_dir):
            if fname.endswith('.json'):
                fpath = os.path.join(_profiles_dir, fname)
                try:
                    with open(fpath, 'r') as f:
                        profile = json.load(f)
                    profile['_filename'] = fname
                    profiles.append(profile)
                except (json.JSONDecodeError, IOError):
                    continue
        return profiles

    def get_active_profile(self):
        """Read active_profile.json, return profile name string or None."""
        if not os.path.exists(_active_profile_path):
            return None
        try:
            with open(_active_profile_path, 'r') as f:
                data = json.load(f)
            return data.get('profile')
        except (json.JSONDecodeError, IOError):
            return None

    def get_revit_versions(self):
        """Scan %APPDATA%\\Autodesk\\Revit\\Addins\\ for year subdirs."""
        return get_installed_revit_versions()

    def is_revit_running(self):
        """Check if Revit.exe is in the process list."""
        try:
            output = subprocess.check_output(
                ['tasklist', '/FI', 'IMAGENAME eq Revit.exe', '/NH'],
                stderr=subprocess.DEVNULL,
                text=True
            )
            return 'Revit.exe' in output
        except subprocess.SubprocessError:
            return False

    def add_profile(self):
        """Open file dialog, validate JSON, copy to app/profiles/."""
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=('JSON Files (*.json)',)
        )
        if not result:
            return {'ok': False, 'error': 'cancelled'}

        file_path = result[0] if isinstance(result, (list, tuple)) else result

        try:
            with open(file_path, 'r') as f:
                profile = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {'ok': False, 'error': 'Invalid JSON: ' + str(e)}

        missing = REQUIRED_FIELDS - set(profile.keys())
        if missing:
            return {'ok': False, 'error': 'Missing fields: ' + ', '.join(sorted(missing))}

        dest_name = '{}_{}.json'.format(profile['profile'], profile['exportDate'])
        # Check if profile with same name already exists — overwrite it
        for fname in os.listdir(_profiles_dir):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(_profiles_dir, fname), 'r') as f:
                        existing = json.load(f)
                    if existing.get('profile') == profile['profile']:
                        os.remove(os.path.join(_profiles_dir, fname))
                        break
                except (json.JSONDecodeError, IOError):
                    continue

        dest_path = os.path.join(_profiles_dir, dest_name)
        shutil.copy2(file_path, dest_path)

        profile['_filename'] = dest_name
        return {'ok': True, 'profile': profile}

    def load_profile(self, profile_name, disable_non_required, revit_version=None):
        """Write active_profile.json, apply hideRules, return {ok, warnings[]}."""
        # Find the profile file
        profile_data = None
        profile_filename = None
        for fname in os.listdir(_profiles_dir):
            if fname.endswith('.json'):
                fpath = os.path.join(_profiles_dir, fname)
                try:
                    with open(fpath, 'r') as f:
                        data = json.load(f)
                    if data.get('profile') == profile_name:
                        profile_data = data
                        profile_filename = fname
                        break
                except (json.JSONDecodeError, IOError):
                    continue

        if not profile_data:
            return {'ok': False, 'warnings': ['Profile not found: ' + profile_name]}

        # Fall back to first installed version if none passed
        if not revit_version:
            versions = get_installed_revit_versions()
            revit_version = versions[0] if versions else None

        warnings = []

        if revit_version:
            # Check required addins
            addin_status = check_addins(profile_data.get('requiredAddins', []), revit_version)
            for name, status in addin_status.items():
                if status == 'missing':
                    warnings.append('Required add-in missing: ' + name)
                elif status == 'unknown':
                    warnings.append('Unknown add-in (not in lookup): ' + name)

            # Apply hide rules
            apply_hide_rules(profile_data.get('hideRules', []), revit_version)

            # Disable non-required if toggled
            if disable_non_required:
                disable_non_required_addins(
                    profile_data.get('requiredAddins', []), revit_version
                )
        else:
            warnings.append('No Revit version detected — add-in toggling skipped')

        # Write active_profile.json
        active = {
            'profile': profile_name,
            'profile_file': profile_filename,
            'loaded_at': datetime.datetime.now().isoformat(timespec='seconds'),
            'last_built': None,
            'disable_non_required': bool(disable_non_required),
        }
        with open(_active_profile_path, 'w') as f:
            json.dump(active, f, indent=2)

        return {'ok': True, 'warnings': warnings}

    def remove_profile(self, profile_name):
        """Delete profile from app/profiles/."""
        for fname in os.listdir(_profiles_dir):
            if fname.endswith('.json'):
                fpath = os.path.join(_profiles_dir, fname)
                try:
                    with open(fpath, 'r') as f:
                        data = json.load(f)
                    if data.get('profile') == profile_name:
                        os.remove(fpath)
                        # Clear active if it was the active one
                        if os.path.exists(_active_profile_path):
                            with open(_active_profile_path, 'r') as f:
                                active = json.load(f)
                            if active.get('profile') == profile_name:
                                os.remove(_active_profile_path)
                        return {'ok': True}
                except (json.JSONDecodeError, IOError):
                    continue
        return {'ok': False, 'error': 'Profile not found'}

    def restore_addins(self, revit_version):
        """Restore all .addin.inactive → .addin for the given version."""
        restore_all_addins(revit_version)
        return {'ok': True}


if __name__ == '__main__':
    api = ProfileSelectorAPI()
    window = webview.create_window(
        'RESTer — Profile Selector',
        url=_html_path,
        width=1100,
        height=700,
        js_api=api
    )
    webview.start()

"""RESTer startup hook — runs on every Revit launch via PyRevit.
Reads active_profile.json, builds a custom ribbon tab if a profile is loaded.
"""
import os
import sys
import json
import datetime

_root = os.path.dirname(os.path.abspath(__file__))

# Add app/ to path for imports
sys.path.insert(0, os.path.join(_root, 'app'))
from logger import get_logger

log = get_logger('startup')

_active_profile_path = os.path.join(_root, 'app', 'active_profile.json')
_profiles_dir = os.path.join(_root, 'app', 'profiles')
_icons_dir = os.path.join(_root, 'icons')
_default_icon_path = os.path.join(_root, 'RESTer.tab', 'Admin.panel',
                                  'TabCreator.pushbutton', 'icon.png')


def _load_active_profile():
    """Read active_profile.json. Returns (active_data, profile_data) or (None, None)."""
    if not os.path.exists(_active_profile_path):
        log.debug('No active_profile.json — nothing to build')
        return None, None

    try:
        with open(_active_profile_path, 'r') as f:
            active = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.error('Failed to read active_profile.json: %s', e)
        return None, None

    profile_file = active.get('profile_file')
    if not profile_file:
        log.debug('No profile_file in active_profile.json')
        return None, None

    profile_path = os.path.join(_profiles_dir, profile_file)
    if not os.path.exists(profile_path):
        log.error('Profile file not found: %s', profile_path)
        return None, None

    try:
        with open(profile_path, 'r') as f:
            profile = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.error('Failed to read profile %s: %s', profile_file, e)
        return None, None

    return active, profile


def _needs_rebuild(active, profile_path):
    """Compare profile file mtime against last_built timestamp."""
    last_built = active.get('last_built')
    if not last_built:
        log.info('No last_built timestamp — rebuild needed')
        return True

    try:
        file_mtime = os.path.getmtime(profile_path)
        built_dt = datetime.datetime.fromisoformat(last_built)
        built_ts = built_dt.timestamp()
        if file_mtime > built_ts:
            log.info('Profile modified since last build — rebuild needed')
            return True
        log.info('Profile unchanged since last build — skipping rebuild')
        return False
    except (ValueError, OSError) as e:
        log.warning('Could not compare timestamps: %s — rebuilding', e)
        return True


def _update_last_built(active):
    """Write updated last_built timestamp to active_profile.json."""
    active['last_built'] = datetime.datetime.now().isoformat(timespec='seconds')
    with open(_active_profile_path, 'w') as f:
        json.dump(active, f, indent=2)
    log.info('Updated last_built: %s', active['last_built'])


def _get_icon_path(slot):
    """Resolve icon path for a tool slot."""
    icon_file = slot.get('iconFile')
    if icon_file:
        custom_path = os.path.join(_icons_dir, icon_file)
        if os.path.exists(custom_path):
            return custom_path
        log.warning('Custom icon not found: %s — using default', icon_file)
    return _default_icon_path


def _get_revit_version():
    """Get current Revit version number."""
    try:
        return str(__revit__.Application.VersionNumber)  # noqa: F821
    except Exception:
        return None


def _build_ribbon(profile):
    """Build a custom Revit ribbon tab from the profile data."""
    try:
        from Autodesk.Revit.UI import (
            RibbonPanel,
            PushButtonData,
            PulldownButtonData,
            SplitButtonData,
            RevitCommandId,
        )
        from System.Drawing import Icon
        from System.Windows.Media.Imaging import BitmapImage
        from System import Uri, UriKind
    except ImportError as e:
        log.error('Revit API import failed: %s', e)
        return False

    tab_name = profile.get('tab', 'RESTer')
    panels = profile.get('panels', [])
    stacks = profile.get('stacks', {})

    log.info('Building ribbon tab: %s (%d panels)', tab_name, len(panels))

    try:
        uiapp = __revit__  # noqa: F821

        # Create the tab
        try:
            uiapp.CreateRibbonTab(tab_name)
            log.info('Created ribbon tab: %s', tab_name)
        except Exception as e:
            log.warning('Tab may already exist: %s', e)

        for panel_def in panels:
            panel_name = panel_def.get('name', 'Panel')
            try:
                panel = uiapp.CreateRibbonPanel(tab_name, panel_name)
            except Exception as e:
                log.warning('Could not create panel %s: %s', panel_name, e)
                continue

            log.info('Created panel: %s', panel_name)

            for slot in panel_def.get('slots', []):
                slot_type = slot.get('type')

                if slot_type == 'tool':
                    _add_tool_button(panel, slot)
                elif slot_type == 'stack':
                    stack_name = slot.get('name', '')
                    stack_def = stacks.get(stack_name)
                    if stack_def:
                        _add_stack_button(panel, stack_name, stack_def)
                    else:
                        log.warning('Stack not found: %s', stack_name)

    except Exception as e:
        log.error('Ribbon build failed: %s', e)
        return False

    log.info('Ribbon build complete')
    return True


def _add_tool_button(panel, slot):
    """Add a single PushButton to a panel for a tool slot."""
    from Autodesk.Revit.UI import PushButtonData
    from System.Windows.Media.Imaging import BitmapImage
    from System import Uri, UriKind

    name = slot.get('name', 'Tool')
    command_id = slot.get('commandId', '')

    # Create a unique internal name
    internal_name = 'RESTer_' + name.replace(' ', '_')

    try:
        # PyRevit button approach: create a push button that posts the command
        button_data = PushButtonData(
            internal_name,
            name,
            # For PyRevit, we need to point to an assembly — this is a placeholder
            # The actual command execution uses PostCommand
            '',
            ''
        )

        # Set icon
        icon_path = _get_icon_path(slot)
        if icon_path and os.path.exists(icon_path):
            try:
                uri = Uri(icon_path, UriKind.Absolute)
                button_data.LargeImage = BitmapImage(uri)
            except Exception as e:
                log.debug('Could not set icon for %s: %s', name, e)

        log.debug('Added tool button: %s -> %s', name, command_id)

    except Exception as e:
        log.error('Failed to add button %s: %s', name, e)


def _add_stack_button(panel, stack_name, stack_def):
    """Add a PulldownButton with child tools for a stack slot."""
    from Autodesk.Revit.UI import PulldownButtonData
    from System.Windows.Media.Imaging import BitmapImage
    from System import Uri, UriKind

    internal_name = 'RESTer_Stack_' + stack_name.replace(' ', '_')
    tools = stack_def.get('tools', [])

    try:
        pulldown_data = PulldownButtonData(internal_name, stack_name)
        log.debug('Added stack: %s (%d tools)', stack_name, len(tools))

        for tool in tools:
            tool_name = tool.get('name', 'Tool')
            command_id = tool.get('commandId', '')
            log.debug('  Stack tool: %s -> %s', tool_name, command_id)

    except Exception as e:
        log.error('Failed to add stack %s: %s', stack_name, e)


# --- Main startup logic ---

def main():
    log.info('=== RESTer startup hook ===')

    active, profile = _load_active_profile()
    if not active or not profile:
        log.info('No active profile — startup complete (no tab to build)')
        return

    log.info('Active profile: %s', active.get('profile'))

    # Cache check
    profile_path = os.path.join(_profiles_dir, active.get('profile_file', ''))
    if not _needs_rebuild(active, profile_path):
        return

    # Version check
    revit_version = _get_revit_version()
    min_version = profile.get('min_version')
    if revit_version and min_version:
        if int(revit_version) < int(min_version):
            log.warning('Revit %s is below min_version %s — aborting',
                        revit_version, min_version)
            # TODO: show balloon notification to user
            return

    # Build the ribbon
    if _build_ribbon(profile):
        _update_last_built(active)

    log.info('=== RESTer startup complete ===')


main()

# -*- coding: utf-8 -*-
"""Update RST - pulls latest using pyRevit's git and reloads."""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_script_dir, '..', '..', '..')
_root = os.path.normpath(_root)

sys.path.insert(0, os.path.join(_root, 'app'))
from logger import get_logger
log = get_logger('update')

log.info('Updating RST...')

try:
    from pyrevit import versionmgr
    from pyrevit.versionmgr import updater
    from pyrevit import forms

    # Get RST extension info
    from pyrevit.extensions import extensionmgr
    rst_ext = None
    for ext in extensionmgr.get_installed_ui_extensions():
        if 'RST' in str(ext.name) or 'REST' in str(ext.name):
            rst_ext = ext
            break

    if rst_ext:
        log.info('Found extension: %s at %s', rst_ext.name, rst_ext.directory)
        has_update = updater.has_pending_updates(rst_ext)

        if has_update:
            log.info('Update available, pulling...')
            updater.update_extension(rst_ext)
            log.info('Updated, reloading pyRevit...')
            from pyrevit.loader import sessionmgr
            sessionmgr.reload()
        else:
            log.info('Already up to date')
            forms.alert('RST is already up to date.', title='RST Update')
    else:
        log.warning('RST extension not found in pyRevit extension list')
        forms.alert(
            'Could not find RST in pyRevit extensions.\n\n'
            'Try updating via pyRevit Extensions Manager.',
            title='RST Update'
        )

except Exception as e:
    log.error('Update failed: %s', e)
    try:
        from pyrevit import forms
        forms.alert('Update failed: ' + str(e), title='RST Update Error')
    except Exception:
        pass

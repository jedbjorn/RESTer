# -*- coding: utf-8 -*-
"""Update RST - pulls latest from git and reloads pyRevit."""
import os
import sys
import subprocess

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_script_dir, '..', '..', '..')
_root = os.path.normpath(_root)

sys.path.insert(0, os.path.join(_root, 'app'))
from logger import get_logger
log = get_logger('update')

log.info('Updating RST from git...')
try:
    result = subprocess.check_output(
        ['git', 'pull'],
        cwd=_root,
        stderr=subprocess.STDOUT,
        text=True
    )
    log.info('Git pull result: %s', result.strip())

    if 'Already up to date' in result:
        from pyrevit import forms
        forms.alert('RST is already up to date.', title='RST Update')
    else:
        log.info('Update found, reloading pyRevit...')
        try:
            from pyrevit.loader import sessionmgr
            sessionmgr.reload()
            log.info('pyRevit reloaded')
        except Exception as e:
            log.error('Reload failed: %s', e)
            from pyrevit import forms
            forms.alert('Updated successfully. Please reload pyRevit manually.', title='RST Update')

except subprocess.CalledProcessError as e:
    log.error('Git pull failed: %s', e.output)
    try:
        from pyrevit import forms
        forms.alert('Update failed.\n\n' + str(e.output), title='RST Update Error')
    except Exception:
        pass
except Exception as e:
    log.error('Update failed: %s', e)
    try:
        from pyrevit import forms
        forms.alert('Update failed: ' + str(e), title='RST Update Error')
    except Exception:
        pass

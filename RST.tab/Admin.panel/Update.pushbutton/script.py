# -*- coding: utf-8 -*-
"""Update RST - pulls latest and reloads pyRevit."""
import os
import sys
import subprocess

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_script_dir, '..', '..', '..')
_root = os.path.normpath(_root)

sys.path.insert(0, os.path.join(_root, 'app'))
from logger import get_logger
log = get_logger('update')

from pyrevit import forms

log.info('Updating RST from %s', _root)

# Try pyRevit's git first, then system git
pulled = False
result_msg = ''

try:
    from pyrevit.coreutils import git
    repo = git.get_repo(_root)
    if repo:
        log.info('Using pyRevit git')
        head_before = str(repo.last_commit_hash)
        repo.fetch('origin')
        repo.merge('origin/main')
        head_after = str(repo.last_commit_hash)
        if head_before == head_after:
            result_msg = 'already_up_to_date'
        else:
            result_msg = 'updated'
        pulled = True
except Exception as e:
    log.warning('pyRevit git failed: %s', e)

if not pulled:
    # Try system git
    git_paths = [
        'git',
        r'C:\Program Files\Git\cmd\git.exe',
        r'C:\Program Files\Git\bin\git.exe',
        r'C:\Program Files (x86)\Git\cmd\git.exe',
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Git', 'cmd', 'git.exe'),
    ]
    for git_cmd in git_paths:
        try:
            out = subprocess.check_output(
                [git_cmd, 'pull'],
                cwd=_root,
                stderr=subprocess.STDOUT
            )
            out_str = out.decode('utf-8', errors='replace').strip()
            log.info('Git pull: %s', out_str)
            if 'Already up' in out_str:
                result_msg = 'already_up_to_date'
            else:
                result_msg = 'updated'
            pulled = True
            break
        except Exception:
            continue

if not pulled:
    forms.alert(
        'Could not update RST.\n\n'
        'Install Git for Windows from git-scm.com,\n'
        'or update via pyRevit Extensions Manager.',
        title='RST Update'
    )
elif result_msg == 'already_up_to_date':
    forms.alert('RST is already up to date.', title='RST Update')
else:
    log.info('Update found, reloading pyRevit...')
    try:
        from pyrevit.loader import sessionmgr
        sessionmgr.reload()
    except Exception as e:
        log.error('Reload failed: %s', e)
        forms.alert('Updated. Please reload pyRevit manually.', title='RST Update')

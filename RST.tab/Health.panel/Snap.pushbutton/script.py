# -*- coding: utf-8 -*-
"""Snap — Launch the Health viewer.

Gathers live Revit context (version, build, active model info, warnings) and
writes it to health_scan_context.json for the viewer's Scan button to pick up.
Does NOT run the health scan itself — that's a manual action from the viewer."""
__title__ = 'Snap'
import os
import sys
import json
import subprocess

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.normpath(os.path.join(_script_dir, '..', '..', '..'))

sys.path.insert(0, os.path.join(_root, 'app'))
from logger import get_logger
log = get_logger('health_snap_btn')

CREATE_NO_WINDOW = 0x08000000

# ── Gather Revit context ────────────────────────────────────────────────────
ctx = {
    'revit_version': '',
    'revit_build': '',
    'revit_username': '',
    'model_name': '',
    'model_path': '',
    'model_size_mb': '',
    'warnings_count': '',
}

try:
    app = __revit__.Application  # noqa: F821
    try: ctx['revit_version'] = str(app.VersionNumber)
    except Exception: pass
    try: ctx['revit_build'] = str(app.VersionBuild)
    except Exception: pass
    try: ctx['revit_username'] = str(app.Username)
    except Exception: pass
except Exception as e:
    log.debug('Could not read Application: %s', e)

try:
    uidoc = __revit__.ActiveUIDocument  # noqa: F821
    if uidoc:
        doc = uidoc.Document
        if doc and not doc.IsFamilyDocument:
            try: ctx['model_name'] = str(doc.Title) if doc.Title else ''
            except Exception: pass
            try: ctx['model_path'] = str(doc.PathName) if doc.PathName else ''
            except Exception: pass
            if ctx['model_path']:
                try:
                    import clr
                    clr.AddReference('mscorlib')
                    from System.IO import FileInfo
                    fi = FileInfo(ctx['model_path'])
                    if fi.Exists:
                        ctx['model_size_mb'] = str(round(fi.Length / (1024.0 * 1024.0), 1))
                except Exception as e:
                    log.debug('FileInfo size read failed for %s: %s', ctx['model_path'], e)
            # ACC / cloud fallback: doc.PathName is a cloud URL, not a real
            # filesystem path. Cache files in CollaborationCache are named by
            # GUID, not title — so match by GUID when the API gives it to us,
            # else fall back to the newest .rvt mtime in the cache tree.
            if not ctx['model_size_mb']:
                try:
                    guid_tokens = set()
                    try:
                        cmp = doc.GetCloudModelPath()
                        if cmp is not None and not cmp.Empty:
                            for getter in ('GetModelGUID', 'GetProjectGUID'):
                                try:
                                    g = getattr(cmp, getter)()
                                    if g is not None:
                                        guid_tokens.add(str(g).lower())
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    local_appdata = os.environ.get('LOCALAPPDATA', '')
                    cache_root = os.path.join(local_appdata, 'Autodesk', 'Revit') if local_appdata else ''
                    best_by_guid = None
                    newest_rvt = None

                    if cache_root and os.path.isdir(cache_root):
                        for ver_entry in os.listdir(cache_root):
                            cc = os.path.join(cache_root, ver_entry, 'CollaborationCache')
                            if not os.path.isdir(cc):
                                continue
                            for walk_root, _dirs, files in os.walk(cc):
                                path_lower = walk_root.lower()
                                path_has_guid = any(g in path_lower for g in guid_tokens) if guid_tokens else False
                                for f in files:
                                    if not f.lower().endswith('.rvt'):
                                        continue
                                    full = os.path.join(walk_root, f)
                                    try:
                                        st = os.stat(full)
                                    except OSError:
                                        continue
                                    entry = (st.st_mtime, full, st.st_size)
                                    if newest_rvt is None or st.st_mtime > newest_rvt[0]:
                                        newest_rvt = entry
                                    name_lower = f.lower()
                                    if guid_tokens and (path_has_guid or any(g in name_lower for g in guid_tokens)):
                                        if best_by_guid is None or st.st_mtime > best_by_guid[0]:
                                            best_by_guid = entry

                    pick = best_by_guid or newest_rvt
                    if pick:
                        _mt, _fp, _sz = pick
                        ctx['model_size_mb'] = str(round(_sz / (1024.0 * 1024.0), 1))
                        log.info('Resolved ACC model cache (%s): %s (%s MB)',
                                 'GUID match' if best_by_guid else 'newest .rvt',
                                 _fp, ctx['model_size_mb'])
                except Exception as e:
                    log.debug('CollaborationCache fallback failed: %s', e)
            try:
                ctx['warnings_count'] = str(len(list(doc.GetWarnings())))
            except Exception:
                pass
except Exception as e:
    log.debug('Could not read active document: %s', e)

# ── Write context file for the viewer's Scan button ─────────────────────────
ctx_path = os.path.join(_root, 'data', 'health_scan_context.json')
try:
    data_dir = os.path.dirname(ctx_path)
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    with open(ctx_path, 'w') as f:
        json.dump(ctx, f)
    log.info('Wrote health scan context (model=%s)', ctx['model_name'] or '-')
except Exception as e:
    log.warning('Failed to write health scan context: %s', e)

# ── Launch viewer ───────────────────────────────────────────────────────────
launcher = os.path.join(_root, 'app', 'health_viewer.py')
log.info('Launching Health viewer: %s', launcher)
subprocess.Popen(['py', '-3.12', launcher], creationflags=CREATE_NO_WINDOW)
log.info('Health viewer launched')

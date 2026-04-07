# RST — Connections Map

> Keep this file up to date as files are added, renamed, or rewired.

---

## Overview

RST is a two-part Revit toolbar profile system built on PyRevit.

| Component | Role | Runtime |
|-----------|------|---------|
| **TabCreator** (`profile_manager.html`) | Admin builds/edits toolbar profiles | CPython 3.12 + pywebview, launched from Revit via pushbutton |
| **ProfileSelector** (`profile_loader.html`) | User loads a profile and toggles add-ins | CPython 3.12 + pywebview, launched from Revit or standalone `.bat` |
| **startup.py** | Reads active profile, builds ribbon, activates MinifyUI | IronPython, runs on every Revit launch / pyRevit reload |

---

## Logging

All backend activity is logged to `rst.log` at the extension root. Shared logger via `app/logger.py` — modules call `get_logger('module_name')`. Log truncates at 512KB and starts fresh. Includes timestamps, severity, module, and message.

---

## Install Path

```
%APPDATA%\pyRevit\Extensions\RST.extension\
```

Install via pyRevit Extension Manager using `https://github.com/jedbjorn/RST`. pyRevit clones the repo and appends `.extension` to the folder name automatically.

---

## Repository Structure

```
RST/                                        ← repo root & install root
├── .gitignore
├── CONNECTIONS.md                          ← this file
├── README.md
├── extension.json                          ← PyRevit extension manifest
├── startup.py                              ← PyRevit startup hook
├── launch_profile_loader.bat               ← Standalone launcher for ProfileSelector
│
├── RST.tab/                                ← PyRevit ribbon tab
│   ├── bundle.yaml                         ← Panel layout order
│   ├── Profiler.panel/
│   │   └── TabCreator.pushbutton/
│   │       ├── script.py                   ← Scans ribbon + loaded addins, writes _revit_data.json, launches tab_creator.py
│   │       └── icon.png
│   ├── Loader.panel/
│   │   └── ProfileLoader.pushbutton/
│   │       ├── script.py                   ← Writes _loader_data.json, launches profile_selector.py, reloads pyRevit on change
│   │       └── icon.png
│   ├── Minify.panel/
│   │   └── MinifyUI.pushbutton/
│   │       ├── script.py                   ← Toggles pyRevit MinifyUI
│   │       └── icon.png
│   ├── Update.panel/
│   │   └── Update.pushbutton/
│   │       ├── script.py                   ← Git pull / zip download + animated reload
│   │       └── icon.png
│   └── Reload.panel/
│       └── Reload.pushbutton/
│           ├── script.py                   ← Triggers pyRevit reload
│           └── icon.png
│
├── app/
│   ├── logger.py                           ← Shared logger → rst.log (512KB cap)
│   ├── reload_ui.py                        ← WPF animated reload message (IronPython)
│   ├── tab_creator.py                      ← TabCreator pywebview backend (TabCreatorAPI)
│   ├── profile_selector.py                 ← ProfileSelector pywebview backend (ProfileSelectorAPI)
│   ├── addin_scanner.py                    ← Addin suppression and restore (filesystem ops)
│   ├── active_profile.json                 ← Written by ProfileSelector, read by startup.py (gitignored)
│   ├── _revit_data.json                    ← Temp: Revit session data for TabCreator (gitignored)
│   ├── _loader_data.json                   ← Temp: Revit session data for ProfileSelector (gitignored)
│   └── profiles/                           ← Profile JSON files
│       └── (*.json)
│
├── icons/
│   ├── RESTer_default.png                  ← Default ribbon button icon (32x32)
│   ├── RESTer_default_16.png               ← 16x16 variant for stack items
│   ├── branding.png                        ← Branding panel logo (replaceable)
│   ├── icon_creator.png                    ← Profiler button icon
│   ├── icon_loader.png                     ← Loader button icon
│   ├── icon_minify.png                     ← Minify button icon
│   ├── icon_reload.png                     ← Reload button icon
│   └── icon_update.png                     ← Update button icon
│
├── ui/
│   ├── profile_manager.html                ← TabCreator UI
│   └── profile_loader.html                 ← ProfileSelector UI
│
├── lookup/
│   ├── addin_lookup.json                   ← Single source: tab name → .addin file mapping
│   └── config.json                         ← Protected addins + exempt paths (user-editable)
│
└── spec/
    ├── HANDOFF.md                          ← Original build spec
    └── spec                                ← Additional spec
```

---

## Data Flow

### IronPython → CPython (session data handoff)

Both pushbutton scripts collect live Revit session data and pass it to CPython via temp JSON files:

| Pushbutton | Writes | Contains | Read by |
|------------|--------|----------|---------|
| TabCreator `script.py` | `app/_revit_data.json` | `revit_version`, `commands` (1400+), `loaded_addins` | `tab_creator.py` |
| ProfileLoader `script.py` | `app/_loader_data.json` | `revit_version`, `loaded_addins` | `profile_selector.py` |

Temp files are deleted after reading. The `loaded_addins` array comes from `__revit__.Application.LoadedApplications` — each entry has `name`, `addinId`, and `assembly` path.

### UI → Python Backend (pywebview JS bridge)

**profile_manager.html** → `TabCreatorAPI`:

| JS Call | Purpose |
|---------|---------|
| `get_revit_version()` | Active Revit version from session |
| `get_installed_commands()` | All ribbon commands from AdWindows scan |
| `get_loaded_addins()` | Add-ins loaded in current Revit session |
| `get_addin_lookup()` | Read `lookup/addin_lookup.json` |
| `get_profiles()` | List saved profile names |
| `save_export(json_str)` | Save to `app/profiles/` + Desktop copy |
| `pick_icon(tool_name)` | File dialog → copy PNG to `icons/` |
| `pick_branding_logo()` | File dialog → resize to 48x48 → `icons/branding.png` |
| `load_profile_into_editor(name)` | Load profile for editing (copies if active) |
| `open_profiles_folder()` | Open `app/profiles/` in Explorer |

**profile_loader.html** → `ProfileSelectorAPI`:

| JS Call | Purpose |
|---------|---------|
| `get_revit_version()` | Active Revit version from session |
| `get_loaded_addins()` | Add-ins loaded in current Revit session |
| `get_addin_lookup()` | Read `lookup/addin_lookup.json` |
| `get_profiles()` | Read all profiles from `app/profiles/` |
| `get_active_profile()` | Read `app/active_profile.json` |
| `add_profile()` | File dialog → validate → copy to `app/profiles/` |
| `load_profile(name, disable, version)` | Write `active_profile.json`, apply hide rules |
| `remove_profile(name)` | Delete from `app/profiles/` |
| `unload_profile()` | Write blank `active_profile.json` |
| `restore_addins()` | Rename `.addin.inactive` → `.addin` |

### Python → External Systems

| Python File | Reads | Writes | External |
|-------------|-------|--------|----------|
| `startup.py` | `active_profile.json`, `profiles/*.json`, `icons/` | — | Revit ribbon (AdWindows), MinifyUI (pyRevit config) |
| `TabCreator script.py` | Revit ribbon (AdWindows), `LoadedApplications` | `_revit_data.json` | Launches `tab_creator.py` |
| `ProfileLoader script.py` | `active_profile.json`, `LoadedApplications` | `_loader_data.json` | Launches `profile_selector.py` |
| `tab_creator.py` | `_revit_data.json`, `profiles/`, `addin_lookup.json` | `profiles/`, `icons/`, Desktop copy | pywebview |
| `profile_selector.py` | `_loader_data.json`, `profiles/`, `active_profile.json`, `addin_lookup.json` | `active_profile.json`, `profiles/` | pywebview |
| `addin_scanner.py` | `addin_lookup.json`, `config.json`, `%APPDATA%\...\Addins\` | `.addin` ↔ `.addin.inactive` | Filesystem |
| `reload_ui.py` | — | — | WPF window + pyRevit `sessionmgr.reload()` |
| `logger.py` | — | `rst.log` | — |

---

## Startup Sequence

On every Revit launch or pyRevit reload, `startup.py` runs:

1. Read `active_profile.json` → load the referenced profile JSON
2. Build the custom ribbon tab via AdWindows (`_build_ribbon`)
   - Remove any existing `REST_*` tabs
   - Create branding panel (logo + GitHub link)
   - Create tool panels with colored backgrounds (rounded corners via DrawingBrush)
   - Tools: large buttons with PostCommand handlers
   - Stacks: vertical RibbonRowPanel with up to 3 small buttons
3. Schedule admin panel styling on Idling event (waits for pyRevit to finish)
4. On first Idle: style RST admin panels with grey backgrounds, then activate MinifyUI if a profile is loaded

---

## Add-in Detection

**Detection** uses live Revit session data (`LoadedApplications`), not filesystem scanning. Each UI checks required add-ins against the loaded list with substring matching on names and lookup file stems. Status is "Loaded" or "Not Loaded".

**Suppression** (hide rules, disable non-required) still uses filesystem operations — renaming `.addin` ↔ `.addin.inactive` in `%APPDATA%\Autodesk\Revit\Addins\{version}\`.

---

## Configuration

### `lookup/addin_lookup.json`
Single source of truth for tab name → `.addin` file mapping. Read by both UIs and the Python backend. User-editable — see README for format.

### `lookup/config.json`
Protected add-ins and exempt paths. User-editable, preserved across updates.

```json
{
  "protected_addins": ["pyRevit.addin", "Kinship.addin", "Dynamo.addin", "DynamoForRevit.addin"],
  "exempt_paths": ["%APPDATA%\\Dynamo"]
}
```

- **protected_addins** — never renamed/disabled
- **exempt_paths** — entire directories skipped during suppress/restore (supports env vars)

---

## Key Decisions

| Decision | Detail |
|----------|--------|
| Install method | pyRevit Extension Manager (git URL) — appends `.extension` automatically |
| IronPython ↔ CPython | Session data passed via temp JSON files, cleaned up after read |
| Addin detection | Live session (`LoadedApplications`), not filesystem scanning |
| Addin suppression | Filesystem rename (`.addin` ↔ `.addin.inactive`), user AppData only |
| Profile re-export | Overwrites existing file (matched by profile name) |
| Ribbon rebuild | Always rebuild on startup — no mtime cache |
| Stacks | Vertical RibbonRowPanel (max 3 small buttons), not dropdown |
| MinifyUI | Auto-activated after profile load via startup.py Idling hook |
| Reload UI | WPF ToolWindow with animated dots, auto-dismissed by reload |
| Protected addins | Configurable via `lookup/config.json` |
| Icon naming | `{toolName}.png`, appends `(1)` on collision |
| Launcher | `.bat` for alpha, `.exe` via PyInstaller planned |

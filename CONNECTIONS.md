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
│   ├── panel_colors.json                   ← Persistent swatch colors (gitignored)
│   ├── custom_tools.json                   ← Custom URL tools (gitignored)
│   ├── profiles/                           ← Profile JSON files
│   │   └── (*.json)
│   └── users/                              ← Per-user add-in configs (gitignored, preserved across updates)
│       ├── {username}_{version}_addins.json
│       └── {username}_{version}_intent.json
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
| `restore_addins()` | Rename `.addin.disabled` → `.addin` |

### Python → External Systems

| Python File | Reads | Writes | External |
|-------------|-------|--------|----------|
| `startup.py` | `active_profile.json`, `profiles/*.json`, `icons/` | — | Revit ribbon (AdWindows), MinifyUI (pyRevit config) |
| `TabCreator script.py` | Revit ribbon (AdWindows), `LoadedApplications` | `_revit_data.json` | Launches `tab_creator.py` |
| `ProfileLoader script.py` | `active_profile.json`, `LoadedApplications` | `_loader_data.json` | Launches `profile_selector.py` |
| `tab_creator.py` | `_revit_data.json`, `profiles/`, `addin_lookup.json` | `profiles/`, `icons/`, Desktop copy | pywebview |
| `profile_selector.py` | `_loader_data.json`, `profiles/`, `active_profile.json`, `addin_lookup.json` | `active_profile.json`, `profiles/` | pywebview |
| `addin_scanner.py` | `addin_lookup.json`, `config.json`, `%APPDATA%\...\Addins\` | `.addin` ↔ `.addin.disabled` | Filesystem |
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

## Add-in Detection & Management

### Three-Source Scan

On first run per user/version (or when username doesn't match existing config), RST performs a combined scan:

| Source | What it gives us | Speed |
|--------|-----------------|-------|
| **AdWindows ribbon scan** (`ComponentManager.Ribbon.Tabs`) | Tab names, command IDs, button names, panel locations | Sub-second (in-memory) |
| **`__revit__.Application.LoadedApplications`** | DLL paths for every loaded add-in, class/assembly names | Sub-second (in-memory) |
| **Filesystem `.addin` scan** (`%APPDATA%\...\Addins\{version}\`) | `.addin` manifest paths, cross-referenced with DLL paths from above | 2-3 seconds (disk I/O + XML parsing) |

Total scan time: ~2-5 seconds. Only scans user-scope `%APPDATA%` directory — never touches `%ProgramData%` or `%ProgramFiles%`.

### User Config

Each Revit user + version gets their own config file. Both Profiler and Loader read from the same file.

```
app/users/
  {username}_{version}_addins.json    ← scan data + enabled/disabled state
  {username}_{version}_intent.json    ← pre-rename plan (cleared after reconciliation)
```

**Config rebuild triggers:**
- File doesn't exist (first run)
- Username from `__revit__.Application.Username` doesn't match config
- Manual rescan (button in Loader)

**Example config:**

```json
{
  "username": "jbjornson",
  "revitVersion": "2025",
  "scanDate": "2026-04-09",
  "addins": {
    "DiRootsOne": {
      "displayName": "DiRootsOne",
      "tabName": "DiRootsOne",
      "addinPath": "C:\\Users\\jbjornson\\AppData\\...\\DiRoots.One.addin",
      "assemblyPath": "C:\\Program Files\\DiRoots\\...\\DiRootsOne.dll",
      "scope": "user",
      "elevated": false,
      "enabled": true,
      "url": "https://diroots.com"
    }
  }
}
```

### Add-in Disable / Enable

**Convention:** matches DiRoots Add-in Manager — `.addin` → `.addin.disabled` / `.addin.disabled` → `.addin`. Users familiar with DiRoots can manually restore if needed.

**Scope rules — what RST will touch:**
- User-scope add-ins in `%APPDATA%` only — never `%ProgramData%` or `%ProgramFiles%`
- Never pyRevit or RST itself
- Never Dynamo or any Dynamo dependencies
- Never add-ins with no ribbon tab (silent/background add-ins)
- Never add-ins in `config.json` protected list
- Add-ins requiring admin elevation are skipped silently

**Three states at profile load time:**

| State | UI indicator | Action |
|-------|-------------|--------|
| Loaded + enabled | Green "Loaded" | Nothing needed |
| Present + disabled | Yellow "Disabled" | Re-enable on load, prompt restart |
| Not installed | Red "Not Installed" | Show download URL / HTML checklist |

### Disable Flow (Profile Loader)

Toggle: "Disable add-ins not used by this profile" (default OFF).

1. User selects profile, enables toggle
2. Dependency check — are all required add-ins present?
3. If missing → dependency overlay (download URLs / Continue Anyway / Open as HTML checklist)
4. If all present → confirmation UI shows:
   - **Staying active:** required add-ins + always-exempt add-ins
   - **Will be disabled:** everything else in user-scope
5. User confirms
6. **Intent log written** (`{username}_{version}_intent.json`) — full plan before any renames
7. RST renames unused `.addin` → `.addin.disabled`
8. Config updated: `enabled: false` for each disabled add-in
9. "Please restart Revit for changes to apply" — user confirms
10. Into loading overlay → profile loads → pyRevit reload

**"Restore All Add-ins" button:**
1. Renames all `.addin.disabled` → `.addin` in user-scope directory
2. Config updated: `enabled: true` for all
3. "Please restart Revit for changes to apply"

### Intent Log & Crash Recovery

Before any rename batch, the full plan is written to the intent log:

```json
{
  "timestamp": "2026-04-09T14:30:00",
  "action": "disable_unused",
  "profile": "Architecture_2025",
  "planned": [
    { "path": "C:\\Users\\...\\Enscape.addin", "from": "enabled", "to": "disabled" },
    { "path": "C:\\Users\\...\\Lumion.addin", "from": "enabled", "to": "disabled" }
  ],
  "completed": []
}
```

On next startup.py run:
1. Check if intent log exists for this user/version
2. Compare `planned` actions vs actual file states on disk
3. If mismatch → reconcile (finish the renames to match intended state)
4. If reconciliation requires restart → inform user
5. Clear intent log once state is consistent

### Dependency Check at Profile Load

When loading a profile with missing add-ins, a dependency overlay appears before the loading UI:

- Lists each missing add-in with name + download URL (from `addin_lookup.json`)
- **Cancel** — return to profile selection
- **Continue Anyway** — skip and load profile despite missing dependencies
- **Open as HTML** — downloads a styled HTML checklist with checkboxes and clickable download links, then proceeds to load the profile

---

## Configuration

### `lookup/addin_lookup.json`
Seed file for add-in metadata — display names, `.addin` filenames, and download URLs. Read by both UIs. User-specific scan data in `app/users/` overrides this for detection; this file provides URLs and display name fallbacks for add-ins not yet scanned.

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
| Addin detection | Three-source scan: AdWindows ribbon + LoadedApplications + user-scope .addin files |
| Addin config | Per-user, per-version: `app/users/{username}_{version}_addins.json` — rebuilt on username mismatch |
| Addin disable | Filesystem rename `.addin` ↔ `.addin.disabled` (DiRoots convention), user AppData only |
| Addin exemptions | pyRevit, RST, Dynamo + deps, no-ribbon-tab add-ins, protected list, elevated-scope |
| Crash recovery | Intent log written before renames, reconciled on next startup |
| Profile re-export | Overwrites existing file (matched by profile name) |
| Ribbon rebuild | Always rebuild on startup — no mtime cache |
| Stacks | Vertical RibbonRowPanel (max 3 small buttons), not dropdown |
| MinifyUI | Auto-activated after profile load via startup.py Idling hook |
| Reload UI | WPF ToolWindow with animated dots, auto-dismissed by reload |
| Protected addins | Configurable via `lookup/config.json` |
| Icon naming | `{toolName}.png`, appends `(1)` on collision |
| Launcher | `.bat` for alpha, `.exe` via PyInstaller planned |

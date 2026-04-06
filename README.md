# RST

Custom Revit ribbon toolbar profile system built on PyRevit. Admins build toolbar profiles with curated tools from any installed add-in. Users load profiles to get a clean, purpose-built ribbon — no digging through tabs.

---

## What It Does

- **Record** every tool on every ribbon tab in Revit (1500+ commands)
- **Build** custom panels with tools from any source — Architecture, DiRootsOne, Kinship, pyRevit, etc.
- **Color** each panel with a custom color that carries through to the Revit ribbon
- **Export** profiles as JSON files for easy sharing
- **Load** profiles and rebuild the ribbon — live inside Revit or externally
- **Hide** ribbon tabs you don't need without disabling add-ins
- **Protect** pyRevit and Kinship from ever being disabled

---

## Install

### 1. Dependencies

- [pyRevit](https://github.com/pyrevitlabs/pyRevit) 4.8+
- [Python 3.12](https://www.python.org/downloads/) — **check "Add Python to PATH" during install** (3.14 is too new)
- pywebview:
  ```powershell
  python -m pip install pywebview
  ```

Verify: `python --version` in PowerShell should show `Python 3.12.x`.

### 2. Add Extension

1. Open Revit
2. pyRevit tab → Extensions → Add Extension
3. Paste this URL:
   ```
   https://github.com/jedbjorn/RST
   ```
4. Reload pyRevit

You should see an **RST** tab in the Revit ribbon with three buttons.

---

## Toolbar Buttons

### Tab Creator
Build and edit toolbar profiles. Opens a full editor UI where you:
- Click **Detect** to scan all installed tools across every ribbon tab
- Search and filter tools by name or source tab
- Create panels, assign colors, drag to reorder
- Add tools to panels via checkbox — short names in panels, full source in browser
- Create tool stacks (grouped dropdowns)
- Export profiles to the extension folder + a copy to your Desktop

### Profile Loader
Switch between profiles without leaving Revit. Opens the Profile Selector UI where you:
- Browse saved profiles with tab preview
- Load a profile — pyRevit auto-reloads and the new ribbon appears immediately
- Add profiles received from your admin via file picker
- Unload or delete profiles
- Restore all disabled add-ins
- Toggle "disable non-required add-ins" per profile

### Hide Tabs
Clean up your ribbon by hiding tabs you don't need:
- **"Hide tabs with tools on RST"** — one-click hides all tabs that have tools in your profile (since they're now on RST)
- Individual tab checkboxes for fine control
- RST tab is always protected — can't be hidden
- Instant — no restart required

---

## Workflow

### Admin
1. Open Revit → RST tab → **Tab Creator**
2. Click **Detect** to scan all available tools
3. Create panels, pick colors, add tools
4. **Export Config** → saves profile JSON + Desktop copy
5. Send the Desktop copy to users

### User
1. Open Revit → RST tab → **Profile Loader**
2. **Add Profile** → select the JSON from admin
3. Select profile → **Load Profile**
4. pyRevit reloads → custom ribbon appears
5. Optionally click **Hide Tabs** to clean up unused tabs

### External Use
The Profile Loader also works outside Revit via `launch_profile_loader.bat` in the extension folder. Add-in disable/enable changes only take effect on Revit restart.

---

## Profile JSON

Profiles are self-contained JSON files with this structure:

```json
{
  "profile": "Design_2025",
  "tab": "Design",
  "min_version": "2024",
  "exportDate": "2025-04-05",
  "requiredAddins": ["DiRootsOne", "Architecture"],
  "hideRules": [],
  "stacks": {},
  "panels": [
    {
      "name": "Core Tools",
      "color": "#4f8ef7",
      "slots": [
        { "type": "tool", "baseName": "Wall", "name": "Wall (Architecture > Build)", "commandId": "ID_OBJECTS_WALL", "sourceTab": "Architecture" },
        { "type": "tool", "baseName": "Door", "name": "Door (Architecture > Build)", "commandId": "ID_OBJECTS_DOOR", "sourceTab": "Architecture" }
      ]
    }
  ]
}
```

---

## Known Limitations

- **pyRevit script-based tools** (e.g. pyRevit Selection tools) can be detected and placed but may not execute via PostCommand — they use pyRevit's internal execution engine
- **Some OOTB Revit tools** with dropdown/list button CommandIds (e.g. `ID_OBJECTS_WALL_RibbonListButton`) are filtered out automatically
- **Add-in disable/enable** only modifies files in user AppData — ProgramData and Program Files are read-only
- **ApplicationInitialized** event not accessible from pyRevit startup scripts — ribbon builds immediately on startup (may miss late-loading add-ins in rare cases)

---

## Protected Add-ins

These are never disabled or hidden:
- **pyRevit** — RST is built on it
- **Kinship** — protected by default

---

## Tech Stack

- **pyRevit** — extension framework, ribbon buttons, startup hooks
- **IronPython** — Revit-side scripts (tab scanning, ribbon building, tab hiding)
- **CPython 3.12** — UI windows via pywebview
- **AdWindows.dll** — Revit ribbon manipulation (scan tools, build panels, set colors, hide tabs)
- **pywebview** — HTML-based UI windows

---

## Links

- [CONNECTIONS.md](CONNECTIONS.md) — file map, API reference, data flow
- Author: [Designs/OS](https://github.com/jedbjorn)

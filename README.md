# RST

Custom Revit ribbon toolbar profile system built on PyRevit. Admins build toolbar profiles with curated tools from any installed add-in. Users load profiles to get a clean, purpose-built ribbon — no digging through tabs.

---

## What It Does

- **Record** every tool on every ribbon tab in Revit (1500+ commands)
- **Build** custom panels with tools from any source — Architecture, DiRootsOne, Kinship, pyRevit, etc.
- **Custom URL Tools** — add company links, wikis, or any URL as clickable toolbar buttons
- **Branding** — company logo on every profile tab, customizable per install
- **Color** each panel with a custom color and adjustable opacity (10–100%)
- **Export** profiles as JSON files for easy sharing
- **Load** profiles and rebuild the ribbon — live inside Revit or externally
- **One-click update** — pulls latest from GitHub, no git required
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

You should see an **RST** tab in the Revit ribbon with five buttons.

---

## RST Tab Buttons

### Profiler
Build and edit toolbar profiles. Opens a full editor UI where you:
- Click **Detect** to scan all installed tools across every ribbon tab
- Search and filter tools by name or source tab
- Create panels, assign colors with adjustable opacity, drag to reorder
- Add tools to panels via checkbox — short names in panels, full source in browser
- Create tool stacks (grouped dropdowns)
- **Add URL tools** — custom buttons that open any URL (company wikis, standards, project sites)
- **Add Logo** — upload a company logo (48x48) that appears on every profile tab
- Export profiles to the extension folder + a copy to your Desktop
- Auto-closes 4 seconds after successful export

### Loader
Switch between profiles without leaving Revit. Opens the Profile Selector UI where you:
- Browse saved profiles with tab preview
- Load a profile — success overlay confirms, auto-closes after 4 seconds
- Add profiles received from your admin via file picker
- Unload or delete profiles (warns if deleting the loaded profile)
- Restore all disabled add-ins
- Toggle "disable non-required add-ins" per profile

### Minify
Triggers pyRevit's built-in MinifyUI to hide unused ribbon tabs and declutter the interface. One click to toggle.

### Update
One-click update for the extension:
- Tries pyRevit git, then system git, then downloads zip from GitHub (no git required)
- Stages the update, reloads pyRevit to release file locks, then applies
- Preserves user data (profiles, active profile, branding logo, log)
- Shows actual error details if something fails

### Reload
Triggers a pyRevit reload to apply profile changes and refresh the ribbon. Equivalent to pyRevit tab → About → Reload but accessible from the RST tab.

---

## Custom URL Tools

Add company-specific URL links directly to your toolbar:

1. In the Profiler, click **+ Add URL** at the bottom of the tool list
2. Enter a name and URL
3. The tool appears in the list tagged "Custom" with a 🔗 icon
4. Add it to any panel like a regular tool
5. In Revit, clicking the button opens the URL in the default browser

Custom tools can be edited (✎) or deleted (✕) at any time. They survive the Detect scan and round-trip through export/import.

Filter the tool list to "Custom" to see only your URL tools.

---

## Branding

Every profile tab includes a branding panel (leftmost) with a logo that links to the RST GitHub page.

- **Default:** RST logo ships with the extension
- **Custom:** Click **Add Logo** in the Profiler header to upload your company logo (48x48 recommended)
- The logo replaces `icons/branding.png` — persists across sessions and profile switches
- Clicking the logo in Revit opens [github.com/jedbjorn/RST](https://github.com/jedbjorn/RST)

---

## Workflow

### Admin
1. Open Revit → RST tab → **Profiler**
2. Click **Detect** to scan all available tools
3. Create panels, pick colors, set opacity, add tools
4. Optionally add custom URL tools and a company logo
5. **Export Config** → saves profile JSON + Desktop copy
6. Send the Desktop copy to users

### User
1. Open Revit → RST tab → **Loader**
2. **Add Profile** → select the JSON from admin
3. Select profile → **Load Profile**
4. Click **Reload** on the RST tab → custom ribbon appears
5. Use **Minify** to hide unused tabs

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
  "panelOpacity": 80,
  "requiredAddins": ["DiRootsOne", "Architecture"],
  "hideRules": [],
  "stacks": {},
  "panels": [
    {
      "name": "Core Tools",
      "color": "#4f8ef7",
      "slots": [
        { "type": "tool", "baseName": "Wall", "name": "Wall (Architecture > Build)", "commandId": "ID_OBJECTS_WALL", "sourceTab": "Architecture" },
        { "type": "tool", "baseName": "Wiki", "name": "Wiki", "commandId": "URL:https://company.wiki", "sourceTab": "Custom" }
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
- **UIState persistence** — Revit saves ribbon state to UIState.dat on session close, which can interfere with hot-swapping tabs between sessions

---

## Protected Add-ins

These are never disabled or hidden:
- **pyRevit** — RST is built on it
- **Kinship** — protected by default

---

## Tech Stack

- **pyRevit** — extension framework, ribbon buttons, startup hooks
- **IronPython** — Revit-side scripts (tab scanning, ribbon building)
- **CPython 3.12** — UI windows via pywebview
- **AdWindows.dll** — Revit ribbon manipulation (scan tools, build panels, set colors)
- **pywebview** — HTML-based UI windows

---

## Links

- [CONNECTIONS.md](CONNECTIONS.md) — file map, API reference, data flow
- Author: [Designs/OS](https://github.com/jedbjorn)

<img src="images/kinben-logo.png" width="220" alt="Kinben Innovation">

# HEX File Rename Utility

**Renames KinSense sensor `.hex` recordings to match the label on the board that recorded them. It previews every change first and applies the whole batch as one transaction that can be rolled back.**

![Status](https://img.shields.io/badge/status-production-47A9DF?style=flat-square)
![Version](https://img.shields.io/badge/version-1.0.0-0A74A0?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-47A9DF?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-0A74A0?style=flat-square)
![Qt](https://img.shields.io/badge/GUI-PySide6%20(Qt%206)-47A9DF?style=flat-square)
![License](https://img.shields.io/badge/license-GPL--3.0-0A74A0?style=flat-square)

![Preview of a 24-inch CMFL dataset](docs/images/04-preview-unnamed-files.png)

## Download

Get **`RenameUtility.exe`** from the [latest release](https://github.com/Kinben-Electronics-Team/Rename_utility/releases/latest). It is one file with no installer, and it does not need Python or Qt. The release page also lists a SHA-256 checksum.

📖 **[User manual](docs/USER_MANUAL.md)**: a step-by-step walkthrough on a real 24-inch CMFL dataset, with screenshots, error messages and fixes.

## What it does

Data is copied off the hub into one folder per sensor board, named after the board's physical label. The file names inside come from the IDs stored on the board. Those IDs can be wrong: `HID255SID255` on a board that was never configured, or a stale hub ID on a board that was moved. The tool makes the file names match the folder label:

```text
By_Label\CMFLB4S2\HID255SID255_0000.hex   →   By_Label\CMFLB4S2\HID04SID02_0000.hex
By_Label\CMFLB4S2\HID255SID255_0001.hex   →   By_Label\CMFLB4S2\HID04SID02_0001.hex
By_Label\CMFLB1S2\HID04SID02_0000.hex     →   By_Label\CMFLB1S2\HID01SID02_0000.hex
```

| Folder pattern | Becomes |
|---|---|
| `MFLB<hub>S<slot>` | `HID<hub>SID<slot>_0000.hex`, `_0001.hex`, … |
| `CMFLB<hub>S<slot>` | same |
| `EGPB<hub>S<slot>` | same |

- Only the immediate subfolders of the selected root are scanned. Other folders and loose files (`INLB0000.hex`, `ODO_0002.hex`) are left alone.
- Files are numbered from `0000` in natural sort order, so recording order is kept.

## Safety

| Guarantee | How |
|---|---|
| Nothing changes without review | **Generate Preview** lists every rename, and **Proceed & Rename** asks for confirmation. |
| All or nothing | Every file moves to a temporary name first, then to its final name. A failure or **Cancel** rolls back every completed step. |
| No overwrites | Duplicate targets and existing target names are refused before anything moves. |
| No stale previews | Names, sizes and modification times are checked again just before renaming. |
| Re-runs are harmless | Files that already have the right name are not touched. |

## Build from source

Requires Python 3.10+ on Windows.

```powershell
git clone https://github.com/Kinben-Electronics-Team/Rename_utility.git
cd Rename_utility

# Run from source
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python rename_utility.py

# Run the tests and build dist\RenameUtility.exe (+ .sha256)
powershell -ExecutionPolicy Bypass -File build.ps1
```

`build.ps1` refuses to build if the tests fail. The PyInstaller spec leaves out Qt modules the app does not use, which keeps the EXE near 38 MB.

## Releasing

1. Bump `__version__` in `rename_utility.py`, the numbers in `version_info.txt`, and the version badge above. Add an entry to [`CHANGELOG.md`](CHANGELOG.md).
2. Commit, then tag and push: `git tag v1.0.1 && git push origin v1.0.1`.
3. The [Release workflow](.github/workflows/release.yml) runs the tests, builds the EXE on a Windows runner and publishes it with its checksum to a GitHub Release.

To regenerate the manual screenshots, see [`tools/capture_screenshots.py`](tools/capture_screenshots.py). It drives the built EXE over UI Automation against a **scratch copy** of a dataset.

## Repository layout

```text
Rename_utility/
├── rename_utility.py          # the app: Qt-free planning/transaction core + PySide6 GUI
├── tests/                     # pytest suite for the core (no GUI needed)
├── RenameUtility.spec         # PyInstaller one-file build
├── version_info.txt           # Windows version resource embedded in the EXE
├── build.ps1                  # local build: venv → tests → EXE → SHA-256
├── requirements.txt           # runtime deps (qtpy, PySide6)
├── requirements-dev.txt       # + pytest, pyinstaller
├── docs/USER_MANUAL.md        # user manual with screenshots in docs/images/
├── tools/capture_screenshots.py
├── images/                    # Kinben logo and app icon
└── .github/workflows/         # CI (tests on every push/PR) and tag-driven release
```

## Credits

Written by **Hardik Khatri**, Kinben Innovation Pvt. Ltd. Licensed under the [GNU GPL v3.0](LICENSE).

---
<p align="center"><i>Kinben Innovation — Operational & Integrity Excellence.</i></p>

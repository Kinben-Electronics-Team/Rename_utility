# Changelog

All notable changes to the HEX File Rename Utility. Versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-29

First release.

### Added
- Renames the `.hex` files in every immediate `MFLB<hub>S<slot>`, `CMFLB<hub>S<slot>` and `EGPB<hub>S<slot>` subfolder to `HID<hub>SID<slot>_0000.hex`, `_0001.hex`, …, so the names match the board label.
- Preview of every rename before anything changes on disk.
- All-or-nothing transaction with full rollback on error or **Cancel**, collision checks, and rejection of stale previews.
- Kinben icon and version number in the window title and EXE properties.
- [User manual](docs/USER_MANUAL.md) with screenshots from a real 24-inch CMFL dataset.
- Tests for the rename core, `build.ps1`, and CI/release workflows that build the EXE on tag push.

### Removed
- Manual mode (rename one folder from a typed first target name). Renaming by folder label covers the real use case.

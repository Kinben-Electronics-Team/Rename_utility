# RenameUtility Run Guide

## Start

1. Double-click `RenameUtility.exe` on Windows 10 or Windows 11.
2. No Python or Qt installation is required.
3. If Windows SmartScreen appears, select **More info** and **Run anyway** only if you trust this copy.

## Manual mode

1. Leave **Automatic mode** unchecked.
2. Select the folder containing the `.hex` files.
3. Enter the first target name, such as `HID04SID02_0000.hex`.
4. Select **Generate Preview** and review every mapping.
5. Select **Proceed & Rename**, then confirm.

Manual mode scans only `.hex` files directly inside the selected folder. The ending number controls the starting value and padding.

## Automatic mode

Automatic mode recognizes immediate subfolders named:

- `MFLB<number>S<number>`
- `CMFLB<number>S<number>`
- `EGPB<number>S<number>`

For example, files in `EGPB2S1` become:

```text
HID02SID01_0000.hex
HID02SID01_0001.hex
HID02SID01_0002.hex
...
```

To use it:

1. Check **Automatic mode: immediate MFLB/CMFLB/EGPB subfolders**.
2. Select the root folder containing those subfolders. For the tested Surat dataset, select the `HUB` folder.
3. Select **Generate Preview**.
4. Review the preview and status warnings.
5. Select **Proceed & Rename**, then confirm.

Each eligible subfolder is numbered independently from `0000`. Empty or unrelated subfolders are skipped with a warning.

## Safety

- Preview does not change files.
- Files are renamed only after explicit confirmation.
- Existing-target and duplicate-target collisions are rejected.
- Changes after preview invalidate the preview.
- Failed or cancelled operations are rolled back where possible.
- Already-correct filenames remain unchanged.

Keep a backup of important datasets before bulk renaming.

## Troubleshooting

- **No manual files:** Confirm `.hex` files are directly inside the selected folder.
- **Skipped automatic folder:** Confirm its name exactly follows an accepted pattern and contains `.hex` files.
- **Preview out of date:** Generate the preview again.
- **Collision error:** Resolve the conflicting file or choose another manual starting name.

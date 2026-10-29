r"""Regenerate the user-manual screenshots in docs/images/.

Drives a built RenameUtility.exe through the whole workflow over UI Automation
and captures each step with PrintWindow, so other windows on top don't matter.

    pip install pywinauto pillow
    python tools/capture_screenshots.py dist/RenameUtility.exe <By_Label root> docs/images

WARNING: this really renames the files under <By_Label root>. Point it at a
scratch copy of a dataset (the manual used By_Label_24inch_CMFL.zip
extracted to C:\ILI_Data), never at the only copy of field data.
"""
import ctypes, ctypes.wintypes as wt, subprocess, sys, time
from pathlib import Path
from PIL import Image
from pywinauto import Desktop

exe, data_root, out = map(Path, sys.argv[1:4])
out.mkdir(parents=True, exist_ok=True)
user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
ctypes.windll.shcore.SetProcessDpiAwareness(2)
desk = Desktop(backend="uia")
TITLE_PREFIX = "HEX File Rename Utility"


def bounds(hwnd):
    r = wt.RECT()
    dwm.DwmGetWindowAttribute(wt.HWND(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r))
    return r.left, r.top, r.right, r.bottom


def render(hwnd):
    """Render a window via PrintWindow so other windows on top don't matter."""
    left, top, right, bottom = bounds(hwnd)
    wr = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(wr))
    w, h = wr.right - wr.left, wr.bottom - wr.top
    gdi = ctypes.windll.gdi32
    hdc = user32.GetWindowDC(hwnd); mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, h); gdi.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)
    buf = ctypes.create_string_buffer(w * h * 4)
    bi = (ctypes.c_uint32 * 10)(40, w, -h, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    gdi.GetDIBits(mdc, bmp, 0, h, buf, bi, 0)
    gdi.DeleteObject(bmp); gdi.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    img = Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)
    return img.crop((left - wr.left, top - wr.top, right - wr.left, bottom - wr.top)), (left, top)


def shot(name, hwnd, overlay=None):
    time.sleep(0.8)
    img, (x0, y0) = render(hwnd)
    if overlay is not None:
        dimg, (dx, dy) = render(overlay)
        img.paste(dimg, (dx - x0, dy - y0))
    img.save(out / name)
    print("saved", name)


def ctl(win, title, ctype):
    return win.child_window(title=title, control_type=ctype)


def set_text(edit, text):
    for _ in range(10):
        edit.iface_value.SetValue(text)
        time.sleep(0.4)
        if edit.get_value() == text:
            return
    raise RuntimeError(f"could not set text: {edit.get_value()!r}")


def dialog(title):
    d = win.child_window(title=title, control_type="Window")
    d.wait("visible", timeout=30)
    return d


subprocess.Popen([str(exe)])
win = desk.window(title_re=TITLE_PREFIX + ".*", control_type="Window")
win.wait("visible", timeout=60)
hwnd = win.handle
user32.MoveWindow(hwnd, 200, 120, 1100, 760, True)
time.sleep(3)

folder = win.child_window(control_type="Edit", found_index=0)
preview = ctl(win, "Generate Preview", "Button")
proceed = win.child_window(title_re="Proceed.*Rename", control_type="Button")

shot("01-main-window.png", hwnd)

# --- error: root folder with no eligible subfolders ---------------------------
set_text(folder, str(data_root / "CMFLB4S3"))
preview.click()
err = dialog("Validation error")
shot("02-no-eligible-folders.png", hwnd, err.wrapper_object().handle)
ctl(err, "OK", "Button").click()

# --- preview the real dataset -------------------------------------------------
set_text(folder, str(data_root))
preview.click()
time.sleep(1)
shot("03-preview.png", hwnd)
table = win.child_window(control_type="Table")
# Scroll so the first never-named files (CMFLB4S2, row 41 of 107) are in view.
# Qt exposes no ScrollPattern, so select row 1 and post arrow keys instead.
table.descendants(control_type="DataItem")[0].select()
for vk, count in ((0x28, 46), (0x26, 6)):  # VK_DOWN, VK_UP
    for _ in range(count):
        user32.PostMessageW(hwnd, 0x100, vk, 0)
        user32.PostMessageW(hwnd, 0x101, vk, 0)
shot("04-preview-unnamed-files.png", hwnd)

# --- rename -------------------------------------------------------------------
proceed.click()
conf = dialog("Confirm rename")
shot("05-confirm-rename.png", hwnd, conf.wrapper_object().handle)
ctl(conf, "Yes", "Button").click()
done = dialog("Rename complete")
shot("06-rename-complete.png", hwnd, done.wrapper_object().handle)
ctl(done, "OK", "Button").click()

# --- re-run: every name is already correct ------------------------------------
preview.click()
time.sleep(1)
shot("07-rerun-preview.png", hwnd)
win.close()

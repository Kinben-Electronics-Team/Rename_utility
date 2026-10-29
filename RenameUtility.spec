# PyInstaller spec for the single-file Windows build.
# Build with:  pyinstaller --noconfirm RenameUtility.spec   (or run build.ps1)

# The app only uses QtCore/QtGui/QtWidgets. These pieces get pulled in by
# qtpy probing and by optional Qt plugins, and add ~20 MB to the EXE.
UNUSED_QT = (
    "QtDataVisualization", "QtNetwork", "QtOpenGL", "QtPdf", "QtQml",
    "QtQuick", "QtSvg", "QtVirtualKeyboard", "opengl32sw",
    "qtvirtualkeyboardplugin", "qpdf", "qsvg", "networkinformation", "tls",
)

a = Analysis(
    ["rename_utility.py"],
    datas=[("images/app-icon.ico", "images")],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2"]
    + [f"PySide6.{name}" for name in UNUSED_QT if name.startswith("Qt")],
)
a.binaries = [b for b in a.binaries
              if not any(name.lower() in b[0].lower() for name in UNUSED_QT)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="RenameUtility",
    console=False,
    icon="images/app-icon.ico",
    version="version_info.txt",
    upx=False,
)

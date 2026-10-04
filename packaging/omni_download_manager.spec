# PyInstaller spec - build from the project root with:
#     pip install pyinstaller
#     pyinstaller packaging/omni_download_manager.spec
# Built and verified with PyInstaller on Windows.
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    datas=[(str(root / "omni_download_manager" / "resources"), "omni_download_manager/resources")],
    excludes=["tkinter", "unittest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Omni Download Manager",
    console=False,
    icon=str(root / "omni_download_manager" / "resources" / "app.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Omni Download Manager")

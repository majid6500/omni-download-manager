# PyInstaller spec - build from the project root with:
#     pip install pyinstaller
#     pyinstaller packaging/omni_download_manager.spec
# Built and verified with PyInstaller on Windows.
from pathlib import Path
import sys

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from omni_download_manager.constants import VERSION

version_parts = tuple(int(part) for part in VERSION.split("."))
file_version = (*version_parts, 0)
version_resource = VSVersionInfo(
    ffi=FixedFileInfo(filevers=file_version, prodvers=file_version),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Omni Download Manager"),
                        StringStruct("FileDescription", "Omni Download Manager"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "Omni Download Manager"),
                        StringStruct("OriginalFilename", "Omni Download Manager.exe"),
                        StringStruct("ProductName", "Omni Download Manager"),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

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
    version=version_resource,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Omni Download Manager")

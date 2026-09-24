# PyInstaller spec for Research Studio V4.7 (Windows)
from PyInstaller.utils.hooks import collect_submodules
hiddenimports = collect_submodules('openpyxl')
a = Analysis(['main.py'], pathex=[], binaries=[], datas=[('templates', 'templates')], hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='ResearchStudio', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False)

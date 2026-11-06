# -*- mode: python ; coding: utf-8 -*-
#
# 一次构建两个可执行程序，输出到同一个目录：
#   dist/QQMusicDecryptor/QQMusicDecryptor.exe       图形界面版（无控制台）
#   dist/QQMusicDecryptor/QQMusicDecryptor-Admin.exe 管理员可见版（控制台 + UAC 提权）
#   dist/QQMusicDecryptor/config.ini                 两者共用的配置文件
#
# 构建命令：
#   python build_exe.py
# 或：
#   pyinstaller build.spec

import os

# SPECPATH 由 PyInstaller 注入（spec 文件所在目录）
try:
    project_root = os.path.abspath(SPECPATH)
except NameError:
    project_root = os.getcwd()

src_dir = os.path.join(project_root, 'src')

block_cipher = None

datas = [
    (os.path.join(src_dir, 'hook_qq_music.js'), '.'),
]

hiddenimports = [
    'app_paths',
    'output_layout',
    'metadata_utils',
    'qqmusic_api_client',
    'supplement_album_metadata',
    'frida',
    'mutagen',
    'mutagen.flac',
    'mutagen.oggvorbis',
    'mutagen.id3',
    'mutagen.mp3',
    'requests',
]

excludes = [
    'tkinter.test',
    'unittest',
    'http.server',
    'pydoc',
]

# ── 图形界面版（GUI）────────────────────────────────────────
gui = Analysis(
    [os.path.join(src_dir, 'gui', 'main_gui.py')],
    pathex=[src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    cipher=block_cipher,
)

gui_pyz = PYZ(gui.pure, cipher=block_cipher)

gui_exe = EXE(
    gui_pyz,
    gui.scripts,
    [],
    exclude_binaries=True,
    name='QQMusicDecryptor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['_frida.pyd'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ── 管理员可见版（控制台 + 运行时 UAC 提权）──────────────────
admin = Analysis(
    [os.path.join(src_dir, 'admin_launcher.py')],
    pathex=[src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    cipher=block_cipher,
)

admin_pyz = PYZ(admin.pure, cipher=block_cipher)

admin_exe = EXE(
    admin_pyz,
    admin.scripts,
    [],
    exclude_binaries=True,
    name='QQMusicDecryptor-Admin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['_frida.pyd'],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 是否在清单中强制要求管理员权限。
    # 这里设为 False，程序启动后自行通过 UAC 请求提权，
    # 这样 --info 等诊断命令可以在普通权限下运行。
    uac_admin=False,
)

coll = COLLECT(
    gui_exe,
    gui.binaries,
    gui.datas,
    admin_exe,
    admin.binaries,
    admin.datas,
    strip=False,
    upx=True,
    upx_exclude=['_frida.pyd'],
    name='QQMusicDecryptor',
)

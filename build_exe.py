#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键构建 QQ音乐解密工具的两个可执行程序。

产物：
    dist/QQMusicDecryptor/QQMusicDecryptor.exe        图形界面版
    dist/QQMusicDecryptor/QQMusicDecryptor-Admin.exe  管理员可见版
    dist/QQMusicDecryptor/config.ini                  共用配置
    dist/QQMusicDecryptor-windows-x64.zip             压缩包

用法：
    python build_exe.py
"""

import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_NAME = "QQMusicDecryptor"
DIST_DIR = os.path.join(ROOT, "dist", DIST_NAME)
ZIP_PATH = os.path.join(ROOT, "dist", DIST_NAME + "-windows-x64.zip")
CONFIG_SRC = os.path.join(ROOT, "config.ini")


def build():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[错误] 未安装 PyInstaller，请先执行: pip install pyinstaller")
        return False

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "build.spec"]
    print("[构建] " + " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    return True


def copy_config():
    if not os.path.isfile(CONFIG_SRC):
        print(f"[警告] 未找到 config.ini: {CONFIG_SRC}")
        return
    shutil.copy2(CONFIG_SRC, os.path.join(DIST_DIR, "config.ini"))
    print(f"[配置] 已复制 config.ini -> {os.path.join(DIST_DIR, 'config.ini')}")


def write_guide():
    guide = """QQ音乐解密工具 - 可执行版使用说明
============================================================

本目录中的两个程序：

1. QQMusicDecryptor.exe
   - 图形界面版，双击启动，无控制台窗口。
   - 启动后从本目录的 config.ini 读取输入/输出目录。

2. QQMusicDecryptor-Admin.exe
   - 管理员可见版，双击启动。
   - 启动时会弹出 UAC（用户账户控制）提示，请选择“是”。
   - 获得管理员权限后，会显示本目录 config.ini 中解析到的
     输入目录和输出目录，然后开始批量解密。
   - 控制台窗口会保留，运行结束后按回车键退出。

配置文件 config.ini
------------------------------------------------------------
两个程序都读取本目录（exe 同级）的 config.ini。
重点关注 [PATHS] 段：

    [PATHS]
    input_dir = D:\\Music\\QQMusic\\Download
    output_dir = D:\\Music\\QQMusic\\Decrypted

- input_dir  ：加密文件（.mflac / .mgg）所在目录
- output_dir ：解密后文件（.flac / .ogg）输出目录

修改后保存即可，下次启动生效。
如果 config.ini 不存在，程序会使用内置默认路径。

输出整理方式
------------------------------------------------------------
config.ini 的 [OUTPUT] 段控制解密后的文件夹结构：

    [OUTPUT]
    folder_mode = album

可选值：

  album  按专辑分文件夹（推荐）
         同一张专辑即使散落在多个「歌手文件夹」里，也会合并到一个
         专辑文件夹；文件名按音轨号排序（01 歌名.flac）；歌词同步
         改名，并修正 [ti]/[ar]/[al] 标签。

  artist 按歌手分文件夹
         每首歌取第一主歌手作为文件夹名，文件夹内的歌曲按歌名排序。

  flat   不分文件夹
         所有歌曲直接放在输出目录，文件名使用「歌手 - 歌名」。

图形界面里的「输出整理」下拉框可以直接选择，选择后自动保存。
管理员版也可以在命令行指定：

    QQMusicDecryptor-Admin.exe --layout album
    QQMusicDecryptor-Admin.exe --layout artist
    QQMusicDecryptor-Admin.exe --layout flat

整理已有输出目录
------------------------------------------------------------
如果之前已经解密过、但文件夹很乱，不需要重新解密，可以直接整理：

    QQMusicDecryptor-Admin.exe --reorganize --layout album
    QQMusicDecryptor-Admin.exe --reorganize --layout album --dry-run

--dry-run 只显示将要移动到哪里，不会修改任何文件。
也可以打开图形界面，点击「整理已有文件」按钮。

使用前准备
------------------------------------------------------------
1. QQ 音乐客户端正在运行，并已登录 VIP 账号。
2. 本工具已内置 Frida，无需另外下载 frida-server。

命令行自检
------------------------------------------------------------
如果不确定程序实际读取的路径，可以这样检查：

    QQMusicDecryptor-Admin.exe --info

它会显示：
    - 程序根目录（exe 所在目录）
    - 实际使用的 config.ini 路径
    - 从 config.ini 解析出的输入/输出目录
    - 日志文件、解密脚本位置
并且不会执行解密，也不需要管理员权限。

日志
------------------------------------------------------------
日志保存在本目录的 logs\\ 下：
    logs\\decrypt.log   解密日志
    logs\\gui.log       图形界面日志
    logs\\stats.json    统计信息
"""
    path = os.path.join(DIST_DIR, "使用说明.txt")
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(guide)
    print(f"[文档] 已生成 {path}")


def make_zip():
    print(f"[打包] {ZIP_PATH}")
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(DIST_DIR):
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, os.path.dirname(DIST_DIR))
                zf.write(full, rel)
    print(f"[完成] {ZIP_PATH}")


def main():
    if not build():
        return 1
    copy_config()
    write_guide()
    make_zip()

    exe_gui = os.path.join(DIST_DIR, "QQMusicDecryptor.exe")
    exe_admin = os.path.join(DIST_DIR, "QQMusicDecryptor-Admin.exe")
    print()
    print("=" * 60)
    print("  构建完成")
    print("=" * 60)
    for path in (exe_gui, exe_admin, os.path.join(DIST_DIR, "config.ini"), ZIP_PATH):
        state = "OK" if os.path.isfile(path) else "缺失"
        print(f"  [{state}] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

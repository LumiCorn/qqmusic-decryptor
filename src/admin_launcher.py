#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2026 FountainChan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
QQ音乐解密工具 - 管理员可见版

特点：
    * 可见的控制台窗口，实时显示解密日志
    * 启动时通过 UAC 请求管理员权限（Frida 注入需要）
    * 从程序根目录（exe 同级）的 config.ini 读取 input_dir / output_dir
    * 运行结束后暂停，窗口不会一闪而过

用法：
    直接双击 exe 即可；也支持命令行参数：
        QQMusicDecryptor-Admin.exe --info
        QQMusicDecryptor-Admin.exe --config D:\\path\\config.ini
"""

import argparse
import ctypes
import os
import subprocess
import sys

# 保证从任意工作目录启动时都能找到同目录的 app_paths / main_cli
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_paths import enable_utf8_console, get_app_root, get_log_path  # noqa: E402


def is_admin():
    """当前进程是否具有管理员权限"""
    if sys.platform != "win32":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def setup_console():
    """设置控制台标题与 UTF-8 输出，避免中文乱码"""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("QQ音乐解密工具 - 管理员版")
        except Exception:
            pass
    enable_utf8_console()


def pause(message="按回车键退出...", no_pause=False):
    """暂停窗口，方便查看输出（输入被重定向/关闭时自动跳过）"""
    if no_pause:
        return
    try:
        input(message)
    except (EOFError, KeyboardInterrupt):
        pass


def relaunch_as_admin():
    """
    以管理员身份重新启动当前程序。

    返回 True 表示已成功启动提权后的进程（当前进程应退出），
    False 表示用户取消或启动失败。
    """
    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        exe = sys.executable
        script = os.path.abspath(__file__)
        params = subprocess.list2cmdline([script] + sys.argv[1:])

    print("正在请求管理员权限（如弹出 UAC 提示，请选择“是”）...")
    sys.stdout.flush()

    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.ShellExecuteW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_int,
        ]
        shell32.ShellExecuteW.restype = ctypes.c_void_p
        result = shell32.ShellExecuteW(
            None,
            "runas",
            exe,
            params,
            get_app_root(),
            1,  # SW_SHOWNORMAL
        )
    except Exception as exc:
        print(f"请求管理员权限失败: {exc}")
        return False

    if not result or int(result) <= 32:
        print("未获得管理员权限（可能取消了 UAC 提示）。")
        return False

    return True


def qqmusic_running():
    """检测 QQMusic.exe 是否正在运行（检测失败时不阻塞流程）"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq QQMusic.exe", "/FO", "CSV"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        return "QQMusic.exe" in (result.stdout or "")
    except Exception:
        return True


def build_parser():
    parser = argparse.ArgumentParser(
        description="QQ音乐批量解密工具 - 管理员可见版（读取程序根目录的 config.ini）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  QQMusicDecryptor-Admin.exe                 # 请求管理员权限并按 config.ini 解密
  QQMusicDecryptor-Admin.exe --info          # 只查看 config.ini 解析结果
  QQMusicDecryptor-Admin.exe -i D:\\in -o D:\\out
  QQMusicDecryptor-Admin.exe --no-pause      # 结束后不等待回车
        """,
    )
    parser.add_argument("-c", "--config", help="配置文件路径（默认: exe 同级 config.ini）")
    parser.add_argument("-i", "--input", help="输入目录（覆盖 config.ini）")
    parser.add_argument("-o", "--output", help="输出目录（覆盖 config.ini）")
    parser.add_argument("-r", "--retries", type=int, help="失败重试次数（覆盖 config.ini）")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已存在的文件")
    parser.add_argument("--flat", action="store_true", help="不保留目录结构（等价于 --layout flat）")
    parser.add_argument(
        "--layout",
        choices=["album", "artist", "flat"],
        help="解密后整理方式：album=按专辑，artist=按歌手，flat=不分文件夹",
    )
    parser.add_argument("--reorganize", action="store_true", help="只整理已有输出目录，不执行解密")
    parser.add_argument("--dry-run", action="store_true", help="配合 --reorganize，仅预览整理结果")
    parser.add_argument("--info", action="store_true", help="仅显示配置与目录，不执行解密")
    parser.add_argument("--no-admin", action="store_true", help="不请求管理员权限（仅用于调试）")
    parser.add_argument("--no-pause", action="store_true", help="结束后不等待回车")
    return parser


def build_decryptor(args):
    """创建并应用配置的解密器（供 --info / --reorganize / 正常解密共用）"""
    from main_cli import QQMusicDecryptorCLI, apply_config_to_decryptor

    decryptor = QQMusicDecryptorCLI(config_path=args.config)
    apply_config_to_decryptor(
        decryptor,
        input_dir=args.input,
        output_dir=args.output,
        retries=args.retries,
        no_skip=args.no_skip,
        flat=args.flat,
    )

    # 命令行 --layout 优先于 config.ini
    if args.layout:
        from output_layout import normalize_folder_mode

        decryptor.folder_mode = normalize_folder_mode(args.layout)
    elif args.flat:
        decryptor.folder_mode = "flat"

    return decryptor


def print_config(decryptor):
    """显示最终解析到的配置与目录"""
    from app_paths import resource_path
    from output_layout import folder_mode_label

    hook_path = resource_path("hook_qq_music.js")
    print("=" * 64)
    print("  QQ音乐批量解密工具 - 管理员版")
    print("=" * 64)
    print(f"  管理员权限 : {'已获得' if is_admin() else '未获得'}")
    print(f"  程序根目录 : {get_app_root()}")
    print(f"  配置文件   : {decryptor.config_path}")
    print(f"  配置状态   : {'已加载' if decryptor.config_loaded else '未找到，使用内置默认值'}")
    print(f"  输入目录   : {decryptor.input_dir}")
    print(f"  输入状态   : {'存在' if os.path.isdir(decryptor.input_dir) else '不存在'}")
    print(f"  输出目录   : {decryptor.output_dir}")
    print(f"  输出整理   : {folder_mode_label(decryptor.folder_mode)}")
    print(f"  日志文件   : {decryptor.log_file_path or get_log_path(decryptor.config)}")
    print(f"  解密脚本   : {hook_path}  ({'存在' if os.path.isfile(hook_path) else '缺失'})")
    print(f"  保留结构   : {decryptor.preserve_structure}")
    print(f"  跳过已存在 : {decryptor.skip_existing}")
    print(f"  最大重试   : {decryptor.max_retries}")
    print("=" * 64)


def main():
    setup_console()
    parser = build_parser()
    args = parser.parse_args()

    # --info 是自检模式，不请求管理员权限，也不修改任何文件
    if args.info:
        decryptor = build_decryptor(args)
        print_config(decryptor)
        pause(no_pause=args.no_pause)
        return 0

    # 请求管理员权限（UAC）
    if not args.no_admin and not is_admin():
        if relaunch_as_admin():
            # 提权后的进程已经启动，当前进程退出
            return 0
        pause("按回车键退出...", args.no_pause)
        return 1

    decryptor = build_decryptor(args)
    print_config(decryptor)

    # --reorganize：只整理已有输出目录，不需要 QQ Music 或输入目录
    if args.reorganize:
        from output_layout import folder_mode_label, reorganize_output, summary_text

        if not os.path.isdir(decryptor.output_dir):
            print()
            print(f"[错误] 输出目录不存在: {decryptor.output_dir}")
            print(f"       请检查 config.ini 中的 [PATHS] output_dir 是否正确：")
            print(f"       {decryptor.config_path}")
            print()
            pause(no_pause=args.no_pause)
            return 1

        decryptor.setup_logging()
        decryptor.log("=" * 60, "INFO")
        decryptor.log("QQ Music 解密工具 - 整理已有输出目录", "INFO")
        decryptor.log("=" * 60, "INFO")
        decryptor.log(f"输出目录: {decryptor.output_dir}", "INFO")
        decryptor.log(f"整理方式: {folder_mode_label(decryptor.folder_mode)}", "INFO")

        print()
        print("开始整理已有输出目录" + ("（预览模式，不移动文件）" if args.dry_run else "") + "...")
        print()

        try:
            stats = reorganize_output(
                decryptor.output_dir,
                decryptor.folder_mode,
                logger=lambda message: decryptor.log(message, "INFO"),
                dry_run=args.dry_run,
            )
            decryptor.log(summary_text(stats), "INFO")
            exit_code = 0 if stats.get("failed", 0) == 0 else 1
        except Exception as exc:
            decryptor.log(f"整理输出目录失败: {exc}", "ERROR")
            exit_code = 1
        finally:
            if decryptor.log_file:
                decryptor.log_file.close()

        print()
        print("=" * 64)
        print(f"  程序结束，退出代码: {exit_code}")
        print(f"  详细日志: {decryptor.log_file_path}")
        print("=" * 64)
        pause(no_pause=args.no_pause)
        return exit_code

    # 输入目录校验：给出明确的排查提示，而不是直接抛异常
    if not os.path.isdir(decryptor.input_dir):
        print()
        print(f"[错误] 输入目录不存在: {decryptor.input_dir}")
        print(f"       请检查 config.ini 中的 [PATHS] input_dir 是否正确：")
        print(f"       {decryptor.config_path}")
        print()
        pause(no_pause=args.no_pause)
        return 1

    # 输出目录不存在时自动创建
    try:
        os.makedirs(decryptor.output_dir, exist_ok=True)
    except Exception as exc:
        print()
        print(f"[错误] 无法创建输出目录: {decryptor.output_dir}")
        print(f"       原因: {exc}")
        pause(no_pause=args.no_pause)
        return 1

    if not qqmusic_running():
        print()
        print("[错误] 未检测到 QQMusic.exe 进程。")
        print("       请先启动 QQ 音乐并登录 VIP 账号，然后重新运行本程序。")
        print()
        pause(no_pause=args.no_pause)
        return 1

    decryptor.setup_logging()
    decryptor.log("=" * 60, "INFO")
    decryptor.log("QQ Music 批量解密工具 - 管理员版", "INFO")
    decryptor.log("=" * 60, "INFO")
    decryptor.log(f"配置文件: {decryptor.config_path} "
                  f"({'已加载' if decryptor.config_loaded else '未找到，使用默认值'})", "INFO")
    decryptor.log(f"输入目录: {decryptor.input_dir}", "INFO")
    decryptor.log(f"输出目录: {decryptor.output_dir}", "INFO")
    from output_layout import folder_mode_label
    decryptor.log(f"输出整理: {folder_mode_label(decryptor.folder_mode)}", "INFO")
    decryptor.log("=" * 60, "INFO")

    print()
    print("按 Ctrl+C 可中断。开始解密...")
    print()

    exit_code = 1
    try:
        success = decryptor.decrypt_all()
        exit_code = 0 if success else 1
    except KeyboardInterrupt:
        decryptor.log("\n用户中断", "WARNING")
        exit_code = 130
    except Exception as exc:
        decryptor.log(f"\n未预期的错误: {exc}", "ERROR")
        import traceback
        decryptor.log(traceback.format_exc(), "ERROR")
        exit_code = 1
    finally:
        decryptor.disconnect()
        if decryptor.log_file:
            decryptor.log_file.close()

    print()
    print("=" * 64)
    print(f"  程序结束，退出代码: {exit_code}")
    print(f"  详细日志: {decryptor.log_file_path}")
    print("=" * 64)
    pause(no_pause=args.no_pause)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

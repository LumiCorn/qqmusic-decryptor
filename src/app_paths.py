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
统一的路径与配置解析工具

背景（修复的 bug）：
    之前的代码在多个入口中只用相对路径 ``config.ini`` 或硬编码的
    ``G:\\QQMusic\\...`` 默认值，导致：
      1. 命令行（main_cli.py）在不带 ``--config`` 时完全不读取根目录的
         config.ini，永远使用硬编码的 G 盘路径；
      2. PyInstaller 打包后 ``__file__`` 指向临时解包目录，exe 找不到
         与它同级的 config.ini；
      3. 程序从其他工作目录启动时，相对路径 ``config.ini`` / ``logs/``
         会被解析到错误的位置。

    本模块统一规定：
      * 程序根目录 = 打包后 exe 所在目录；开发模式 = 项目根目录。
      * 根目录下的 config.ini 是唯一默认配置文件。
      * 配置中的相对路径一律相对于程序根目录解析，而不是当前工作目录。
"""

import configparser
import os
import sys

# 配置文件名称（放在程序根目录 / exe 同级目录）
CONFIG_FILENAME = "config.ini"

# 可选的环境变量，便于测试或指定其他配置文件
ENV_CONFIG = "QQMUSIC_DECRYPT_CONFIG"

# 内置默认配置：仅当根目录没有 config.ini 时使用
_DEFAULT_SECTIONS = {
    "PATHS": {
        "input_dir": r"G:\QQMusic\Download",
        "output_dir": r"G:\QQMusic\Decrypted",
    },
    "LOGGING": {
        "log_level": "INFO",
        "log_file": "logs/decrypt.log",
        "save_stats": "true",
    },
    "OPTIONS": {
        "preserve_structure": "true",
        "skip_existing": "true",
        "max_retries": "3",
        "retry_delay": "2",
        "verify_metadata": "true",
        "delete_source": "true",
        "delete_empty_dirs": "true",
        "delete_lyrics": "true",
        "metadata_processing_mode": "batch",
        "skip_metadata_during_decrypt": "true",
    },
    "OUTPUT": {
        "folder_mode": "album",
    },
    "NOTIFICATIONS": {
        "show_completion": "true",
        "show_summary": "true",
    },
}


def is_frozen():
    """是否运行在 PyInstaller 打包后的环境中"""
    return bool(getattr(sys, "frozen", False))


def enable_utf8_console():
    """让 Windows 控制台以 UTF-8 显示中文，避免日志乱码"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def get_app_root():
    """
    程序根目录。

    * 打包后：exe 所在目录（config.ini 应放在这里）
    * 开发模式：项目根目录（src 的上一级）
    """
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    # 本文件位于 <项目根>/src/app_paths.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_bundle_dir():
    """
    打包资源目录。

    PyInstaller 会把 datas 解包到 ``sys._MEIPASS``；开发模式下就是 src 目录。
    用于定位 hook_qq_music.js 这类随程序分发的资源文件。
    """
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """
    查找随程序分发的资源文件（例如 hook_qq_music.js）。

    依次尝试：打包资源目录 → 程序根目录 → 源码目录。
    找不到时返回第一个候选路径，调用方可据此给出准确错误信息。
    """
    candidates = [
        os.path.join(get_bundle_dir(), name),
        os.path.join(get_app_root(), name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), name),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(candidates[0])


def get_config_path(explicit=None):
    """
    解析 config.ini 的绝对路径。

    优先级：
        1. 调用方显式传入的路径（命令行 --config）
        2. 环境变量 QQMUSIC_DECRYPT_CONFIG
        3. 程序根目录 / config.ini（打包后即 exe 同级目录）
        4. 当前工作目录 / config.ini（兼容从项目根目录运行源码的场景）

    返回第一个存在的候选路径；都不存在时返回根目录下的默认路径，
    便于调用方统一提示“配置文件不存在”。
    """
    candidates = []

    if explicit:
        explicit = os.path.expandvars(os.path.expanduser(str(explicit).strip().strip('"')))
        candidates.append(os.path.abspath(explicit))
        if not os.path.isabs(explicit):
            candidates.append(os.path.abspath(os.path.join(get_app_root(), explicit)))

    env_path = os.environ.get(ENV_CONFIG)
    if env_path:
        candidates.append(os.path.abspath(os.path.expandvars(os.path.expanduser(env_path))))

    candidates.append(os.path.join(get_app_root(), CONFIG_FILENAME))
    candidates.append(os.path.join(os.getcwd(), CONFIG_FILENAME))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    # 没有任何文件时：显式路径优先，否则回落到程序根目录下的 config.ini
    return os.path.abspath(candidates[0])


def create_default_config():
    """创建带内置默认值的 ConfigParser（关闭插值，避免路径中的 % 报错）"""
    config = configparser.ConfigParser(interpolation=None, strict=False)
    for section, values in _DEFAULT_SECTIONS.items():
        config[section] = dict(values)
    return config


def load_config(config_path=None):
    """
    加载配置文件。

    Returns:
        (config, resolved_path, loaded)
        config: ConfigParser（始终包含默认值）
        resolved_path: 实际解析到的 config.ini 绝对路径
        loaded: 是否真的读取到了文件
    """
    path = get_config_path(config_path)
    config = create_default_config()
    loaded = False

    if os.path.isfile(path):
        try:
            # utf-8-sig 兼容记事本另存为 UTF-8 BOM 的情况
            loaded = bool(config.read(path, encoding="utf-8-sig"))
        except (OSError, configparser.Error) as exc:
            print(f"[配置] 读取配置文件失败: {path} ({exc})，使用默认配置")

    return config, path, loaded


def resolve_path(value, base_dir=None):
    """
    把配置/命令行中的路径规范化为绝对路径。

    * 去掉首尾空白和成对引号
    * 展开 %VAR% / ~
    * 相对路径相对于 base_dir 解析（默认程序根目录，而非当前工作目录）
    """
    if value is None:
        return ""

    value = str(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()

    value = os.path.expandvars(os.path.expanduser(value))
    if not value:
        return ""

    if not os.path.isabs(value):
        value = os.path.join(base_dir or get_app_root(), value)

    return os.path.normpath(value)


def get_log_path(config):
    """解析日志文件路径；相对路径相对于程序根目录"""
    try:
        log_value = config.get("LOGGING", "log_file", fallback="logs/decrypt.log")
    except (configparser.Error, AttributeError):
        log_value = "logs/decrypt.log"
    return resolve_path(log_value or "logs/decrypt.log", get_app_root())


def get_logs_dir():
    """程序根目录下的 logs 目录"""
    return os.path.join(get_app_root(), "logs")


def save_paths_to_config(config_path, input_dir, output_dir):
    """
    把 GUI 中选择的路径写回 config.ini。

    采用逐行替换而不是 configparser 整体重写，尽量保留用户原有的
    注释和配置项顺序。文件不存在时创建一份带默认值的新配置。
    """
    path = os.path.abspath(config_path)
    input_dir = str(input_dir)
    output_dir = str(output_dir)

    if not os.path.isfile(path):
        config = create_default_config()
        config["PATHS"]["input_dir"] = input_dir
        config["PATHS"]["output_dir"] = output_dir
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            config.write(f)
        return path

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()

    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")

    section = None
    seen = {"input_dir": False, "output_dir": False}
    pats_header_index = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            if section.upper() == "PATHS":
                pats_header_index = index
            continue

        if section == "PATHS" and "=" in line and not stripped.startswith(("#", ";")):
            key, _, rest = line.partition("=")
            key_name = key.strip().lower()
            if key_name in seen:
                # 保留原有的缩进 / 键名写法，只替换等号右侧的值
                lines[index] = f"{key.rstrip()} = {input_dir if key_name == 'input_dir' else output_dir}"
                seen[key_name] = True

    if not all(seen.values()):
        if pats_header_index is None:
            # 没有 [PATHS] 段：追加到文件末尾
            if lines and lines[-1].strip() == "":
                lines.pop()
            lines.extend(["", "[PATHS]"])
            pats_header_index = len(lines) - 1
        insert_at = pats_header_index + 1
        if not seen["input_dir"]:
            lines.insert(insert_at, f"input_dir = {input_dir}")
            insert_at += 1
        if not seen["output_dir"]:
            lines.insert(insert_at, f"output_dir = {output_dir}")

    content = newline.join(lines)
    if not content.endswith(newline):
        content += newline

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    return path


def save_setting_to_config(config_path, section, key, value):
    """
    把单个配置项写回 config.ini，尽量保留用户原有的注释和顺序。

    如果文件或段落不存在，会自动创建。
    """
    path = os.path.abspath(config_path)
    section = str(section).strip()
    key = str(key).strip()
    value = str(value)

    if not os.path.isfile(path):
        config = create_default_config()
        if section not in config:
            config[section] = {}
        config[section][key] = value
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            config.write(f)
        return path

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        text = f.read()

    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")

    current_section = None
    section_header_index = None
    found = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip()
            if current_section.lower() == section.lower() and section_header_index is None:
                section_header_index = index
            continue

        if (
            current_section is not None
            and current_section.lower() == section.lower()
            and "=" in line
            and not stripped.startswith(("#", ";"))
        ):
            existing_key = line.split("=", 1)[0].strip()
            if existing_key.lower() == key.lower():
                lines[index] = f"{line.split('=', 1)[0].rstrip()} = {value}"
                found = True
                break

    if not found:
        if section_header_index is None:
            if lines and lines[-1].strip() == "":
                lines.pop()
            lines.extend(["", f"[{section}]"])
            section_header_index = len(lines) - 1
        lines.insert(section_header_index + 1, f"{key} = {value}")

    content = newline.join(lines)
    if not content.endswith(newline):
        content += newline

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    return path


def describe_config(config_path=None):
    """返回便于在界面/控制台展示的配置摘要（不读取路径之外的文件）"""
    config, path, loaded = load_config(config_path)
    input_dir = resolve_path(config.get("PATHS", "input_dir", fallback=""), get_app_root())
    output_dir = resolve_path(config.get("PATHS", "output_dir", fallback=""), get_app_root())
    return {
        "config": config,
        "config_path": path,
        "loaded": loaded,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "log_path": get_log_path(config),
    }

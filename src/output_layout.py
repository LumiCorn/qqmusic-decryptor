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
解密后输出目录整理工具

支持三种整理方式（folder_mode）：

    album  —— 按专辑分文件夹
              把同一张专辑散落在不同「歌手文件夹」中的曲目合并到一个专辑文件夹，
              文件名按音轨号排序（01 歌名.flac），歌词同步改名并更新 [ti]/[ar]/[al]。

    artist —— 按主歌手分文件夹
              每首歌取第一主歌手作为文件夹名，文件夹内的歌曲按歌名排序。

    flat   —— 不分文件夹
              所有歌曲直接放在输出目录根目录，文件名使用「歌手 - 歌名」。

另外保留 ``mirror`` 作为内部兼容值：不做整理（维持解密时保留的目录结构）。
"""

import os
import re
import shutil
from dataclasses import dataclass
from typing import Optional

try:
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
except ImportError:  # pragma: no cover - mutagen 是项目必需依赖
    FLAC = None
    OggVorbis = None

AUDIO_EXTENSIONS = (".flac", ".ogg")

FOLDER_MODE_ALBUM = "album"
FOLDER_MODE_ARTIST = "artist"
FOLDER_MODE_FLAT = "flat"
FOLDER_MODE_MIRROR = "mirror"

FOLDER_MODES = (
    FOLDER_MODE_ALBUM,
    FOLDER_MODE_ARTIST,
    FOLDER_MODE_FLAT,
    FOLDER_MODE_MIRROR,
)

FOLDER_MODE_LABELS = {
    FOLDER_MODE_ALBUM: "按专辑分文件夹",
    FOLDER_MODE_ARTIST: "按歌手分文件夹",
    FOLDER_MODE_FLAT: "不分文件夹",
    FOLDER_MODE_MIRROR: "保持原目录结构",
}

# GUI 中展示的选项（推荐项放在最前）
FOLDER_MODE_CHOICES = [
    ("按专辑分文件夹（推荐）", FOLDER_MODE_ALBUM),
    ("按歌手分文件夹", FOLDER_MODE_ARTIST),
    ("不分文件夹（全部放在输出目录）", FOLDER_MODE_FLAT),
]

# Windows 文件名非法字符
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", "CLOCK$",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# 文件名开头的音轨号（兼容 "01 歌名" / "1. 歌名"，不处理 "1-800-..." 这类歌名）
_TRACK_PREFIX_RE = re.compile(r"^\s*(\d{1,2})[\.\s]\s*")
# QQ 音乐下载文件名常见的后缀
_HIRES_SUFFIX_RE = re.compile(r"_hires$", re.IGNORECASE)


@dataclass
class AudioInfo:
    """整理输出时需要的音频标签"""

    title: str = ""
    artist: str = ""
    album: str = ""
    albumartist: str = ""
    track: Optional[int] = None
    disc: Optional[int] = None


def normalize_folder_mode(value):
    """把配置/命令行里的整理方式规范化为合法值，非法值回退到 album"""
    if not value:
        return FOLDER_MODE_ALBUM
    value = str(value).strip().lower()
    aliases = {
        "专辑": FOLDER_MODE_ALBUM,
        "album": FOLDER_MODE_ALBUM,
        "歌手": FOLDER_MODE_ARTIST,
        "artist": FOLDER_MODE_ARTIST,
        "平铺": FOLDER_MODE_FLAT,
        "flat": FOLDER_MODE_FLAT,
        "none": FOLDER_MODE_FLAT,
        "mirror": FOLDER_MODE_MIRROR,
        "preserve": FOLDER_MODE_MIRROR,
    }
    return aliases.get(value, FOLDER_MODE_ALBUM)


def folder_mode_label(mode):
    """返回整理方式的中文名称"""
    return FOLDER_MODE_LABELS.get(normalize_folder_mode(mode), FOLDER_MODE_LABELS[FOLDER_MODE_ALBUM])


def _first_tag(audio, key):
    """读取音频标签的第一个值"""
    try:
        value = audio.get(key)
    except Exception:
        return ""
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            text = str(item).strip()
            if text:
                return text
        return ""
    return str(value).strip()


def _join_tags(audio, key):
    """读取可能包含多个值的标签（如 ARTIST），用 / 连接"""
    try:
        value = audio.get(key)
    except Exception:
        return ""
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "/".join(parts)
    return str(value).strip()


def _parse_number(value):
    """从 '2' / '2/12' / ['2'] 之类的标签值中解析整数"""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    match = re.match(r"\s*(\d+)", str(value))
    return int(match.group(1)) if match else None


def read_audio_info(file_path):
    """读取音频的标题/歌手/专辑/音轨号；读取失败时返回空 AudioInfo"""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".flac" and FLAC is not None:
            audio = FLAC(file_path)
        elif ext == ".ogg" and OggVorbis is not None:
            audio = OggVorbis(file_path)
        else:
            return AudioInfo()

        return AudioInfo(
            title=_first_tag(audio, "TITLE"),
            artist=_join_tags(audio, "ARTIST"),
            album=_first_tag(audio, "ALBUM"),
            albumartist=_first_tag(audio, "ALBUMARTIST"),
            track=_parse_number(audio.get("TRACKNUMBER")),
            disc=_parse_number(audio.get("DISCNUMBER")),
        )
    except Exception:
        return AudioInfo()


def split_artists(value):
    """
    拆分多歌手标签。

    QQ 音乐常见写法是 "Daniel Caesar/Sampha"（斜杠分隔），
    另外兼容分号、顿号和竖线。不拆分 " & "，避免误伤
    "Simon & Garfunkel" 这类组合名。
    """
    if not value:
        return []
    text = re.sub(r"\s+(?:feat\.?|ft\.?)\s+.*$", "", str(value), flags=re.IGNORECASE)
    parts = re.split(r"\s*[/;、|]\s*", text)
    return [part.strip() for part in parts if part.strip()]


def primary_artist(value):
    """取第一主歌手（如 "Daniel Caesar/Sampha" -> "Daniel Caesar"）"""
    parts = split_artists(value)
    return parts[0] if parts else ""


def artist_display(value):
    """把多歌手显示为 "A, B"（用于平铺模式文件名和歌词 [ar:]）"""
    parts = split_artists(value)
    if not parts:
        return ""
    # 去重但保持顺序
    unique = list(dict.fromkeys(parts))
    return ", ".join(unique)


def sanitize_component(name, fallback="未知", max_length=100):
    """清理 Windows 文件名/文件夹名中的非法字符"""
    text = str(name or "").strip()
    text = _ILLEGAL_FILENAME_CHARS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")

    if not text:
        text = fallback

    # Windows 保留设备名（CON、NUL、COM1 等）
    stem = text.split(".")[0].strip().upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        text = "_" + text

    if len(text) > max_length:
        text = text[:max_length].rstrip(" .")

    return text or fallback


def track_number_from_filename(file_name):
    """从文件名开头提取音轨号；没有则返回 None"""
    stem = os.path.splitext(os.path.basename(file_name))[0]
    match = _TRACK_PREFIX_RE.match(stem)
    return int(match.group(1)) if match else None


def clean_title_from_filename(file_name):
    """去掉文件名开头的音轨号和 _hires 后缀，作为标题标签缺失时的回退"""
    stem = os.path.splitext(os.path.basename(file_name))[0]
    stem = _TRACK_PREFIX_RE.sub("", stem)
    stem = _HIRES_SUFFIX_RE.sub("", stem)
    return stem.strip() or "未知曲目"


def build_output_path(output_root, info, mode, source_path):
    """
    计算整理后的目标路径（不创建目录、不处理重名）。

    Args:
        output_root: 输出根目录
        info: AudioInfo
        mode: album / artist / flat
        source_path: 原始文件路径（用于扩展名和标签缺失时回退）
    """
    mode = normalize_folder_mode(mode)
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in AUDIO_EXTENSIONS:
        ext = ".flac"

    title = (info.title or "").strip() or clean_title_from_filename(source_path)
    album = (info.album or "").strip() or "未知专辑"
    artist = (info.artist or "").strip()
    album_artist = (info.albumartist or "").strip()
    primary = primary_artist(album_artist or artist) or "未知歌手"

    folder = ""
    file_stem = title

    if mode == FOLDER_MODE_ALBUM:
        folder = sanitize_component(album, fallback="未知专辑")

        track = info.track
        if track is None:
            track = track_number_from_filename(source_path)

        if track is not None:
            if info.disc and info.disc > 1:
                prefix = f"{info.disc}-{track:02d}"
            else:
                prefix = f"{track:02d}"
            file_stem = f"{prefix} {title}"

    elif mode == FOLDER_MODE_ARTIST:
        folder = sanitize_component(primary, fallback="未知歌手")
        file_stem = title

    elif mode == FOLDER_MODE_FLAT:
        display_artist = artist_display(artist)
        file_stem = f"{display_artist} - {title}" if display_artist else title

    else:  # mirror / 未知模式：不做整理
        return os.path.abspath(source_path)

    file_stem = sanitize_component(file_stem, fallback="未知曲目", max_length=150)

    if folder:
        return os.path.join(os.path.abspath(output_root), folder, file_stem + ext)
    return os.path.join(os.path.abspath(output_root), file_stem + ext)


def _normalized_path(path):
    return os.path.normcase(os.path.abspath(path))


def _unique_destination(path, reserved):
    """目标已存在（或已被本次整理占用）时，追加 (2)、(3)…"""
    if not os.path.exists(path) and _normalized_path(path) not in reserved:
        return path

    stem, ext = os.path.splitext(path)
    index = 2
    while True:
        candidate = f"{stem} ({index}){ext}"
        if not os.path.exists(candidate) and _normalized_path(candidate) not in reserved:
            return candidate
        index += 1


def collect_audio_files(root_dir):
    """递归收集输出目录中的音频文件（跳过隐藏目录和 logs）"""
    files = []
    for current, dirs, names in os.walk(root_dir):
        dirs[:] = [
            directory for directory in dirs
            if not directory.startswith(".") and directory.lower() not in ("logs", "_internal")
        ]
        for name in names:
            if name.lower().endswith(AUDIO_EXTENSIONS):
                files.append(os.path.join(current, name))
    return files


def find_lyric_file(audio_path):
    """查找与音频同名的 .lrc 文件（大小写不敏感）"""
    stem = os.path.splitext(audio_path)[0]
    for ext in (".lrc", ".LRC", ".Lrc"):
        candidate = stem + ext
        if os.path.isfile(candidate):
            return candidate

    directory = os.path.dirname(audio_path)
    target = os.path.basename(stem).lower() + ".lrc"
    try:
        for name in os.listdir(directory):
            if name.lower() == target:
                return os.path.join(directory, name)
    except OSError:
        pass
    return None


def _read_text_auto(file_path):
    """读取歌词文本，兼容 UTF-8 / UTF-8 BOM / GB18030"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return f.read(), "utf-8"


def update_lyric_metadata(lrc_path, info):
    """
    更新 LRC 的 [ti:] / [ar:] / [al:] 标签，使其与音频标签一致。

    部分播放器直接读取歌词文件里的这些字段；QQ 音乐下载的歌词里
    [al:] 有时是错误的歌曲名，这里统一修正。
    """
    try:
        text, encoding = _read_text_auto(lrc_path)
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.replace("\r\n", "\n").split("\n")

        desired = {
            "ti": (info.title or "").strip(),
            "ar": artist_display(info.artist),
            "al": (info.album or "").strip(),
        }
        seen = set()

        for index, line in enumerate(lines):
            match = re.match(r"^\s*\[(ti|ar|al):(.*)\]\s*$", line, re.IGNORECASE)
            if not match:
                continue
            key = match.group(1).lower()
            seen.add(key)
            if desired.get(key):
                lines[index] = f"[{key}:{desired[key]}]"

        missing = [key for key in ("ti", "ar", "al") if key not in seen and desired.get(key)]
        if missing:
            lines[0:0] = [f"[{key}:{desired[key]}]" for key in missing]

        new_text = newline.join(lines)
        if not new_text.endswith(newline):
            new_text += newline

        if new_text == text:
            return False

        # 保持原文件的 BOM 状态：utf-8-sig 表示原文件带 BOM
        out_encoding = "utf-8-sig" if encoding == "utf-8-sig" else "utf-8"
        with open(lrc_path, "w", encoding=out_encoding, newline="") as f:
            f.write(new_text)
        return True
    except Exception:
        return False


def move_lyric_file(source_audio, destination_audio, info=None):
    """
    把歌词移动到新音频旁边，文件名与音频一致，并更新歌词内嵌元数据。

    Returns:
        bool: 是否找到并处理了歌词
    """
    source_lrc = find_lyric_file(source_audio)
    if not source_lrc:
        return False

    destination_lrc = os.path.splitext(destination_audio)[0] + ".lrc"

    if _normalized_path(source_lrc) != _normalized_path(destination_lrc):
        os.makedirs(os.path.dirname(destination_lrc), exist_ok=True)
        if os.path.exists(destination_lrc):
            os.remove(destination_lrc)
        shutil.move(source_lrc, destination_lrc)

    if info is not None:
        update_lyric_metadata(destination_lrc, info)

    return True


def _copy_album_cover(source_audio, destination_audio):
    """专辑模式下，把源目录的 cover.jpg 复制一份到目标专辑文件夹"""
    source_dir = os.path.dirname(source_audio)
    destination_dir = os.path.dirname(destination_audio)
    if _normalized_path(source_dir) == _normalized_path(destination_dir):
        return

    source_cover = os.path.join(source_dir, "cover.jpg")
    destination_cover = os.path.join(destination_dir, "cover.jpg")
    if os.path.isfile(source_cover) and not os.path.isfile(destination_cover):
        try:
            os.makedirs(destination_dir, exist_ok=True)
            shutil.copy2(source_cover, destination_cover)
        except OSError:
            pass


def _cleanup_empty_dirs(root_dir):
    """
    删除整理后残留的空目录，以及只剩 cover.jpg 的旧专辑文件夹。

    不会删除仍包含音频、歌词或其他用户文件的目录。
    """
    removed = 0
    root_abs = os.path.abspath(root_dir)

    for current, dirs, names in os.walk(root_abs, topdown=False):
        if os.path.abspath(current) == root_abs:
            continue

        names = os.listdir(current)
        has_audio = any(name.lower().endswith(AUDIO_EXTENSIONS) for name in names)
        has_children = any(os.path.isdir(os.path.join(current, name)) for name in names)

        # 旧的分片专辑目录在音频移走后通常只剩 cover.jpg；它已经被复制到
        # 新的专辑目录，这里可以安全删除。
        if not has_audio and not has_children:
            cover = os.path.join(current, "cover.jpg")
            if os.path.isfile(cover):
                try:
                    os.remove(cover)
                except OSError:
                    pass
                names = os.listdir(current)

        if not names:
            try:
                os.rmdir(current)
                removed += 1
            except OSError:
                pass

    return removed


def reorganize_output(output_root, mode, logger=None, dry_run=False, move_lyrics=True):
    """
    按指定方式整理输出目录中的音频、歌词和封面。

    Args:
        output_root: 输出根目录
        mode: album / artist / flat
        logger: 日志函数（接收一个字符串），默认 print
        dry_run: 只打印将要执行的操作，不移动文件
        move_lyrics: 是否同步移动/重命名歌词

    Returns:
        dict: 统计信息
    """
    log = logger or print
    mode = normalize_folder_mode(mode)
    root_dir = os.path.abspath(output_root)

    stats = {
        "mode": mode,
        "mode_label": folder_mode_label(mode),
        "total": 0,
        "moved": 0,
        "kept": 0,
        "lyrics": 0,
        "dirs_removed": 0,
        "failed": 0,
        "dry_run": dry_run,
    }

    if mode == FOLDER_MODE_MIRROR:
        log("整理方式为「保持原目录结构」，跳过整理。")
        return stats

    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"输出目录不存在: {root_dir}")

    audio_files = collect_audio_files(root_dir)
    stats["total"] = len(audio_files)

    if not audio_files:
        log(f"输出目录中没有音频文件: {root_dir}")
        return stats

    reserved = set()

    for source in sorted(audio_files):
        try:
            info = read_audio_info(source)
            destination = build_output_path(root_dir, info, mode, source)
            source_key = _normalized_path(source)
            destination_key = _normalized_path(destination)

            # 已经在目标位置的文件夹里（重复运行整理时）直接跳过，
            # 不能因为“目标已存在”就给它加 (2) 后缀。
            if destination_key == source_key:
                reserved.add(destination_key)
                stats["kept"] += 1
                # 即使不移动，也顺手修正歌词内的 [ti]/[ar]/[al]
                if move_lyrics and info is not None:
                    move_lyric_file(source, destination, info)
                continue

            destination = _unique_destination(destination, reserved)
            reserved.add(_normalized_path(destination))

            if dry_run:
                log(
                    "[预览] "
                    + os.path.relpath(source, root_dir)
                    + "  ->  "
                    + os.path.relpath(destination, root_dir)
                )
                stats["moved"] += 1
                continue

            os.makedirs(os.path.dirname(destination), exist_ok=True)
            if mode == FOLDER_MODE_ALBUM:
                _copy_album_cover(source, destination)

            shutil.move(source, destination)
            stats["moved"] += 1

            if move_lyrics and move_lyric_file(source, destination, info):
                stats["lyrics"] += 1

            log(
                "[整理] "
                + os.path.relpath(source, root_dir)
                + "  ->  "
                + os.path.relpath(destination, root_dir)
            )
        except Exception as exc:
            stats["failed"] += 1
            log(f"[失败] {source}: {exc}")

    if not dry_run:
        stats["dirs_removed"] = _cleanup_empty_dirs(root_dir)

    return stats


def summary_text(stats):
    """把整理统计转换成一行中文摘要"""
    prefix = "[预览] " if stats.get("dry_run") else ""
    return (
        f"{prefix}整理方式: {stats.get('mode_label', '')}；"
        f"音频 {stats.get('total', 0)} 个，移动 {stats.get('moved', 0)} 个，"
        f"已在目标位置 {stats.get('kept', 0)} 个，"
        f"处理歌词 {stats.get('lyrics', 0)} 个，"
        f"清理空目录 {stats.get('dirs_removed', 0)} 个，"
        f"失败 {stats.get('failed', 0)} 个"
    )

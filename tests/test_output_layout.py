#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""输出整理（按专辑 / 按歌手 / 不分文件夹）的回归测试

运行：
    python -m unittest discover -s tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import output_layout as layout  # noqa: E402
from output_layout import AudioInfo, build_output_path, sanitize_component  # noqa: E402


class TestLayoutHelpers(unittest.TestCase):
    def test_sanitize_illegal_chars(self):
        cleaned = sanitize_component('A/B:C*D?"E<F>G|H')
        for char in '<>:"/\\|?*':
            self.assertNotIn(char, cleaned)
        self.assertTrue(cleaned)

    def test_sanitize_reserved_windows_name(self):
        self.assertTrue(sanitize_component("CON").upper().startswith("_CON"))

    def test_primary_artist(self):
        self.assertEqual(layout.primary_artist("Daniel Caesar/Sampha"), "Daniel Caesar")
        self.assertEqual(layout.primary_artist("The Weeknd; Justice"), "The Weeknd")
        self.assertEqual(layout.artist_display("Daniel Caesar/Sampha"), "Daniel Caesar, Sampha")

    def test_build_output_path_album(self):
        info = AudioInfo(title="Song", artist="A/B", album="Album", track=5)
        path = build_output_path(r"D:\Out", info, "album", r"D:\In\05 Song.mflac")
        self.assertEqual(path, os.path.join(r"D:\Out", "Album", "05 Song.flac"))

    def test_build_output_path_artist(self):
        info = AudioInfo(title="Song", artist="A/B", album="Album", track=5)
        path = build_output_path(r"D:\Out", info, "artist", r"D:\In\05 Song.flac")
        self.assertEqual(path, os.path.join(r"D:\Out", "A", "Song.flac"))

    def test_build_output_path_flat(self):
        info = AudioInfo(title="Song", artist="A/B", album="Album", track=5)
        path = build_output_path(r"D:\Out", info, "flat", r"D:\In\05 Song.flac")
        self.assertEqual(path, os.path.join(r"D:\Out", "A, B - Song.flac"))

    def test_album_without_tags_uses_filename(self):
        path = build_output_path(r"D:\Out", AudioInfo(), "album", r"D:\In\03 Naked.mflac")
        self.assertEqual(path, os.path.join(r"D:\Out", "未知专辑", "03 Naked.flac"))


class TestReorganize(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self._make_file(
            "Artist A", "Album", "01 One.flac",
            AudioInfo(title="One", artist="Artist A", album="Album", track=1),
        )
        self._make_file(
            "Artist A", "Album", "02 Two.flac",
            AudioInfo(title="Two", artist="Artist A", album="Album", track=2),
        )
        self._make_file(
            "Artist B", "Album", "03 Three.flac",
            AudioInfo(title="Three", artist="Artist B", album="Album", track=3),
        )

        # 让 reorganize_output 在不解析真实 FLAC 的情况下读取测试标签
        self.infos = {
            "one": AudioInfo(title="One", artist="Artist A", album="Album", track=1),
            "two": AudioInfo(title="Two", artist="Artist A", album="Album", track=2),
            "three": AudioInfo(title="Three", artist="Artist B", album="Album", track=3),
        }
        self.patcher = patch.object(layout, "read_audio_info", side_effect=self._fake_info)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _fake_info(self, path):
        name = os.path.basename(path).lower()
        for keyword, info in self.infos.items():
            if keyword in name:
                return info
        return AudioInfo()

    def _make_file(self, artist, album, file_name, info):
        directory = os.path.join(self.root, artist, album)
        os.makedirs(directory, exist_ok=True)
        audio = os.path.join(directory, file_name)
        with open(audio, "w", encoding="utf-8") as f:
            f.write("dummy")
        with open(os.path.splitext(audio)[0] + ".lrc", "w", encoding="utf-8") as f:
            f.write("[ti:Old]\n[ar:Old]\n[al:Old]\n[00:00.00]lyric\n")
        with open(os.path.join(directory, "cover.jpg"), "wb") as f:
            f.write(b"jpg")

    def test_album_mode_merges_and_sorts(self):
        stats = layout.reorganize_output(self.root, "album", logger=lambda _msg: None)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["moved"], 3)

        album_dir = os.path.join(self.root, "Album")
        self.assertTrue(os.path.isdir(album_dir))
        for name in ("01 One.flac", "02 Two.flac", "03 Three.flac"):
            self.assertTrue(os.path.isfile(os.path.join(album_dir, name)), name)
            self.assertTrue(os.path.isfile(os.path.join(album_dir, os.path.splitext(name)[0] + ".lrc")))
        self.assertTrue(os.path.isfile(os.path.join(album_dir, "cover.jpg")))

        # 旧的分片目录应被清理
        self.assertFalse(os.path.isdir(os.path.join(self.root, "Artist A")))
        self.assertFalse(os.path.isdir(os.path.join(self.root, "Artist B")))

        # 歌词 [al:] 应被修正为专辑名
        with open(os.path.join(album_dir, "01 One.lrc"), encoding="utf-8") as lrc_file:
            lrc_text = lrc_file.read()
        self.assertIn("[al:Album]", lrc_text)

        # 重复整理应幂等
        second = layout.reorganize_output(self.root, "album", logger=lambda _msg: None)
        self.assertEqual(second["moved"], 0)
        self.assertEqual(second["kept"], 3)
        self.assertEqual(second["failed"], 0)

    def test_artist_mode(self):
        stats = layout.reorganize_output(self.root, "artist", logger=lambda _msg: None)
        self.assertEqual(stats["moved"], 3)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Artist A", "One.flac")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Artist A", "Two.lrc")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Artist B", "Three.flac")))
        self.assertFalse(os.path.isdir(os.path.join(self.root, "Artist A", "Album")))

    def test_flat_mode(self):
        stats = layout.reorganize_output(self.root, "flat", logger=lambda _msg: None)
        self.assertEqual(stats["moved"], 3)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Artist A - One.flac")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Artist B - Three.lrc")))
        self.assertFalse(os.path.isdir(os.path.join(self.root, "Artist A")))
        self.assertFalse(os.path.isdir(os.path.join(self.root, "Artist B")))

    def test_dry_run_does_not_move(self):
        before = sorted(
            os.path.relpath(os.path.join(current, name), self.root)
            for current, _dirs, names in os.walk(self.root)
            for name in names
        )
        stats = layout.reorganize_output(self.root, "album", logger=lambda _msg: None, dry_run=True)
        after = sorted(
            os.path.relpath(os.path.join(current, name), self.root)
            for current, _dirs, names in os.walk(self.root)
            for name in names
        )
        self.assertEqual(stats["moved"], 3)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)

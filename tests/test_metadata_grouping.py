#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""专辑元数据分组逻辑的回归测试（不访问网络、不解析真实音频）"""

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

import supplement_album_metadata as metadata  # noqa: E402


class TestAlbumGrouping(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

        # 旧版结构：一个目录 = 一张专辑
        self.single_dir = os.path.join(self.root, "Artist", "Album A")
        os.makedirs(self.single_dir)
        for name in ("01 A1.flac", "02 A2.flac"):
            open(os.path.join(self.single_dir, name), "wb").close()

        # 整理后的歌手目录：同一目录里有 2 张专辑
        self.mixed_dir = os.path.join(self.root, "Artist2")
        os.makedirs(self.mixed_dir)
        for name in ("B1.flac", "C1.flac"):
            open(os.path.join(self.mixed_dir, name), "wb").close()

        self.tags = {
            os.path.join(self.single_dir, "01 A1.flac"): {
                "artist": "Artist", "album": "Album A", "albumartist": "",
                "title": "A1", "track": 1,
            },
            os.path.join(self.single_dir, "02 A2.flac"): {
                "artist": "Artist", "album": "Album A", "albumartist": "",
                "title": "A2", "track": 2,
            },
            os.path.join(self.mixed_dir, "B1.flac"): {
                "artist": "Artist2", "album": "Album B", "albumartist": "",
                "title": "B1", "track": 1,
            },
            os.path.join(self.mixed_dir, "C1.flac"): {
                "artist": "Artist2", "album": "Album C", "albumartist": "",
                "title": "C1", "track": 1,
            },
        }

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_single_album_directory_uses_old_logic(self):
        with patch.object(metadata, "extract_audio_tags", side_effect=lambda p: self.tags[p]), \
             patch.object(metadata, "process_directory", return_value={
                 "files": [{"metadata_processed": True}, {"metadata_processed": True}],
                 "cover_saved": True,
             }) as process_directory, \
             patch.object(metadata, "process_album_group") as process_group:
            stats = metadata.process_album_directory(self.single_dir)

        process_directory.assert_called_once()
        process_group.assert_not_called()
        self.assertEqual(stats["file_stats"]["total"], 2)
        self.assertEqual(stats["file_stats"]["processed"], 2)

    def test_mixed_album_directory_is_split_by_tags(self):
        with patch.object(metadata, "extract_audio_tags", side_effect=lambda p: self.tags[p]), \
             patch.object(metadata, "process_directory", return_value={
                 "files": [{"metadata_processed": True}, {"metadata_processed": True}],
                 "cover_saved": True,
             }), \
             patch.object(metadata, "process_album_group", return_value={
                 "files": [{"metadata_processed": True}],
                 "cover_saved": False,
             }) as process_group:
            stats = metadata.process_album_directory(self.root)

        # 只有 Artist2 目录被拆分，Album A 目录仍走旧逻辑
        self.assertEqual(process_group.call_count, 2)
        called_albums = sorted(call.args[1] for call in process_group.call_args_list)
        self.assertEqual(called_albums, ["Album B", "Album C"])
        for call in process_group.call_args_list:
            # 多张专辑共用一个目录时不写 cover.jpg，避免互相覆盖
            self.assertFalse(call.kwargs["save_cover"])

        self.assertEqual(stats["file_stats"]["total"], 4)
        self.assertEqual(stats["file_stats"]["processed"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)

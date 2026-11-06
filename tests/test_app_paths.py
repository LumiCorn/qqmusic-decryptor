#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app_paths / config.ini 解析的回归测试

运行：
    python -m unittest discover -s tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app_paths import (  # noqa: E402
    get_app_root,
    get_config_path,
    load_config,
    resolve_path,
    resource_path,
    save_paths_to_config,
    save_setting_to_config,
)


class TestAppPaths(unittest.TestCase):
    def test_app_root_is_project_root_in_dev(self):
        self.assertEqual(os.path.normcase(get_app_root()), os.path.normcase(PROJECT_ROOT))

    def test_default_config_path_is_in_app_root(self):
        path = get_config_path()
        self.assertEqual(
            os.path.normcase(os.path.dirname(path)),
            os.path.normcase(get_app_root()),
        )
        self.assertEqual(os.path.basename(path), "config.ini")

    def test_resource_path_finds_hook_script(self):
        hook = resource_path("hook_qq_music.js")
        self.assertTrue(os.path.isfile(hook), hook)

    def test_resolve_relative_path_against_base(self):
        base = tempfile.mkdtemp()
        try:
            expected = os.path.normpath(os.path.join(base, "Music", "In"))
            self.assertEqual(resolve_path("Music/In", base), expected)
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_resolve_path_strips_quotes_and_expands_vars(self):
        os.environ["QQMUSIC_TEST_DIR"] = r"D:\TestMusic"
        try:
            self.assertEqual(resolve_path('"%QQMUSIC_TEST_DIR%"'), r"D:\TestMusic")
        finally:
            os.environ.pop("QQMUSIC_TEST_DIR", None)


class TestConfigLoading(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.ini")
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(
                "[PATHS]\n"
                "input_dir = Music/Encrypted\n"
                "output_dir = D:\\Music\\Decrypted\n"
                "\n"
                "[OPTIONS]\n"
                "max_retries = 7\n"
                "delete_source = false\n"
            )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_config_reads_explicit_path(self):
        config, path, loaded = load_config(self.config_path)
        self.assertTrue(loaded)
        self.assertEqual(os.path.normcase(path), os.path.normcase(self.config_path))
        self.assertEqual(config.get("OPTIONS", "max_retries"), "7")
        self.assertFalse(config.getboolean("OPTIONS", "delete_source"))

    def test_relative_config_path_resolved_against_app_root(self):
        config, path, _ = load_config(self.config_path)
        # 相对路径相对于程序根目录，而不是当前工作目录
        self.assertEqual(
            resolve_path(config.get("PATHS", "input_dir"), get_app_root()),
            os.path.normpath(os.path.join(get_app_root(), "Music", "Encrypted")),
        )

    def test_cli_reads_root_config_without_explicit_argument(self):
        """回归：不传 --config 时 main_cli 也必须读取根目录 config.ini"""
        from main_cli import QQMusicDecryptorCLI

        decryptor = QQMusicDecryptorCLI()
        root_config, _, _ = load_config(os.path.join(PROJECT_ROOT, "config.ini"))
        expected_input = resolve_path(
            root_config.get("PATHS", "input_dir"), PROJECT_ROOT
        )
        self.assertEqual(
            os.path.normcase(decryptor.config_path),
            os.path.normcase(os.path.join(PROJECT_ROOT, "config.ini")),
        )
        self.assertTrue(decryptor.config_loaded)
        self.assertEqual(
            os.path.normcase(
                resolve_path(decryptor.config.get("PATHS", "input_dir"), PROJECT_ROOT)
            ),
            os.path.normcase(expected_input),
        )


class TestSavePaths(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.ini")
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(
                "# 用户注释：不要丢失\n"
                "[PATHS]\n"
                "# 输入目录\n"
                "input_dir = G:\\Old\\In\n"
                "output_dir = G:\\Old\\Out\n"
                "\n"
                "[OPTIONS]\n"
                "max_retries = 3\n"
            )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_paths_updates_values_and_keeps_comments(self):
        save_paths_to_config(self.config_path, r"D:\New\In", r"D:\New\Out")
        with open(self.config_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("input_dir = D:\\New\\In", content)
        self.assertIn("output_dir = D:\\New\\Out", content)
        self.assertIn("# 用户注释：不要丢失", content)
        self.assertIn("# 输入目录", content)
        # 其他配置项保持不变
        self.assertIn("max_retries = 3", content)
        self.assertNotIn("G:\\Old\\In", content)

    def test_save_paths_creates_missing_config(self):
        missing = os.path.join(self.temp_dir, "new", "config.ini")
        save_paths_to_config(missing, r"D:\New\In", r"D:\New\Out")
        config, _, loaded = load_config(missing)
        self.assertTrue(loaded)
        self.assertEqual(config.get("PATHS", "input_dir"), r"D:\New\In")
        self.assertEqual(config.get("PATHS", "output_dir"), r"D:\New\Out")

    def test_save_setting_creates_output_section_and_keeps_comments(self):
        save_setting_to_config(self.config_path, "OUTPUT", "folder_mode", "artist")
        with open(self.config_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[OUTPUT]", content)
        self.assertIn("folder_mode = artist", content)
        self.assertIn("# 用户注释：不要丢失", content)

        # 再次修改同一项，不应重复插入
        save_setting_to_config(self.config_path, "OUTPUT", "folder_mode", "flat")
        with open(self.config_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content.count("folder_mode ="), 1)
        self.assertIn("folder_mode = flat", content)
        self.assertNotIn("folder_mode = artist", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)

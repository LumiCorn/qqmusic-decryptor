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
#
# GUI 部分基于 strelitzia-reg/qqmusic-decryptor (MIT) 修改
# https://github.com/strelitzia-reg/qqmusic-decryptor

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import frida
import os
import hashlib
import threading
import logging
import sys
from datetime import datetime
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_paths import (
    enable_utf8_console,
    get_app_root,
    load_config,
    resolve_path,
    resource_path,
    save_paths_to_config,
    save_setting_to_config,
)
from metadata_utils import (
    extract_track_number_from_filename,
    add_track_number_to_flac,
    process_album_metadata,
    QQMusicAPIClient
)
from output_layout import (
    FOLDER_MODE_CHOICES,
    build_output_path,
    folder_mode_label,
    normalize_folder_mode,
    read_audio_info,
    reorganize_output,
    summary_text,
)

class QQMusicDecryptorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("QQ音乐解密工具 v1.1")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 新增：配置日志（使用 logging.basicConfig）
        # 统一使用程序根目录：打包后 = exe 所在目录；开发时 = 项目根目录
        project_root = get_app_root()
        
        log_dir = os.path.join(project_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'gui.log')
        
        # 配置日志（输出到文件）
        import logging
        from logging.handlers import RotatingFileHandler
        
        # 创建文件处理器（带轮转）
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # 配置根 logger（只输出到文件）
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler],
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True
        )
        
        # 设置图标（如果有的话）
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass

        # 新增：删除选项变量（初始默认值，load_config 会更新）
        self.delete_source_var = tk.BooleanVar(value=True)
        self.delete_empty_dirs_var = tk.BooleanVar(value=True)
        self.delete_lyrics_var = tk.BooleanVar(value=True)
        self.default_delete_source = True
        self.default_delete_empty_dirs = True
        self.default_delete_lyrics = True

        # 新增：删除统计变量
        self.deleted_files = 0
        self.deleted_dirs = 0

        self.load_config()
 
        self.setup_ui()

        # 状态变量
        self.is_processing = False
        self.session = None
        self.script = None

        # 新增：删除选项变量
        self.delete_source_var = tk.BooleanVar(value=True)
        self.delete_empty_dirs_var = tk.BooleanVar(value=True)
        self.delete_lyrics_var = tk.BooleanVar(value=True)
        self.default_delete_source = True
        self.default_delete_empty_dirs = True
        self.default_delete_lyrics = True
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题
        title_label = ttk.Label(main_frame, text="QQ音乐解密工具", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 输入目录选择
        ttk.Label(main_frame, text="输入目录:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.input_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.input_path, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="浏览", command=self.browse_input).grid(row=1, column=2, pady=5)
        
        # 输出目录选择
        ttk.Label(main_frame, text="输出目录:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_path, width=50).grid(row=2, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="浏览", command=self.browse_output).grid(row=2, column=2, pady=5)
        
        # 控制按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)

        # 选项框架
        options_frame = ttk.LabelFrame(main_frame, text="选项")
        options_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=5, pady=5)

        # 删除源文件复选框
        ttk.Checkbutton(
            options_frame,
            text="转换后删除源文件",
            variable=self.delete_source_var
        ).grid(row=0, column=0, sticky=tk.W, pady=2)

        # 删除空目录复选框
        ttk.Checkbutton(
            options_frame,
            text="删除空目录",
            variable=self.delete_empty_dirs_var
        ).grid(row=0, column=1, sticky=tk.W, pady=2, padx=10)

        # 删除歌词文件复选框
        ttk.Checkbutton(
            options_frame,
            text="同时删除歌词文件",
            variable=self.delete_lyrics_var
        ).grid(row=0, column=2, sticky=tk.W, pady=2)

        # 输出整理方式
        ttk.Label(options_frame, text="输出整理:").grid(row=1, column=0, sticky=tk.W, pady=(8, 2))

        current_label = next(
            (label for label, value in FOLDER_MODE_CHOICES if value == self.folder_mode),
            FOLDER_MODE_CHOICES[0][0],
        )
        self.folder_mode_var = tk.StringVar(value=current_label)
        self.folder_mode_combo = ttk.Combobox(
            options_frame,
            textvariable=self.folder_mode_var,
            values=[label for label, _value in FOLDER_MODE_CHOICES],
            state="readonly",
            width=30,
        )
        self.folder_mode_combo.grid(row=1, column=1, sticky=tk.W, padx=10, pady=(8, 2))
        self.folder_mode_combo.bind("<<ComboboxSelected>>", self._on_folder_mode_changed)

        ttk.Label(
            options_frame,
            text="按专辑：合并同一专辑，按音轨排序，歌词同步改名",
            font=("Microsoft YaHei UI", 8),
            foreground="gray",
        ).grid(row=1, column=2, sticky=tk.W, padx=10, pady=(8, 2))

        # 控制按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=20)
        
        self.start_button = ttk.Button(button_frame, text="开始解密", command=self.start_decryption)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="停止", command=self.stop_decryption, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="整理已有文件", command=self.reorganize_existing).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="清空日志", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # 状态标签
        self.status_label = ttk.Label(main_frame, text="准备就绪")
        self.status_label.grid(row=7, column=0, columnspan=3, pady=5)
        
        # 统计信息
        stats_frame = ttk.Frame(main_frame)
        stats_frame.grid(row=8, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        ttk.Label(stats_frame, text="统计信息:").grid(row=0, column=0, sticky=tk.W)
        self.stats_text = tk.StringVar(value="总文件: 0, 成功: 0, 失败: 0, 跳过: 0")
        ttk.Label(stats_frame, textvariable=self.stats_text).grid(row=0, column=1, sticky=tk.W, padx=10)
        
        # 日志区域
        ttk.Label(main_frame, text="操作日志:").grid(row=9, column=0, sticky=tk.W, pady=(10, 0))
        self.log_area = scrolledtext.ScrolledText(main_frame, width=80, height=20)
        self.log_area.grid(row=10, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 署名
        ttk.Label(main_frame, text="工具由 Strelitzia 开发", font=("Arial", 8), foreground="gray").grid(
            row=9, column=2, sticky=tk.E, pady=(10, 0)
        )

        # 配置文件状态（让用户明确看到 exe 实际读取的是哪个 config.ini）
        config_state = "已加载" if self.config_loaded else "未找到，使用默认值"
        ttk.Label(
            main_frame,
            text=f"配置文件: {self.config_path}  [{config_state}]",
            font=("Microsoft YaHei UI", 8),
            foreground="gray",
        ).grid(row=11, column=0, columnspan=3, sticky=tk.W, pady=(0, 2))
        
        # 配置网格权重
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(10, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # 设置默认路径（从配置文件读取）
        self.input_path.set(self.default_input_dir)
        self.output_path.set(self.default_output_dir)
        
        # 添加 TextHandler 到 logger（输出到 GUI 文本框）
        # 这样日志就会同时输出到：文件、GUI 文本框
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.see(tk.END)
        
        self.text_handler = TextHandler(self.log_area)
        self.text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self.text_handler)
    
    # setup_logging() 方法已被 logging.basicConfig() 替代
    # 日志配置现在在 __init__() 方法中完成
    # 同时输出到文件和 GUI 文本框
    
    # 原来的 setup_logging() 方法（已废弃）
    # def setup_logging(self):
    #     # 创建自定义日志处理器
    #     class TextHandler(logging.Handler):
    #         def __init__(self, text_widget):
    #             super().__init__()
    #             self.text_widget = text_widget
    #         
    #         def emit(self, record):
    #             msg = self.format(record)
    #             self.text_widget.insert(tk.END, msg + '\n')
    #             self.text_widget.see(tk.END)
    #     
    #     # 配置日志
    #     self.log_handler = TextHandler(self.log_area)
    #     self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    #     
    #     self.logger = logging.getLogger()
    #     self.logger.setLevel(logging.INFO)
    #     self.logger.addHandler(self.log_handler)
    
    def load_config(self):
        """
        加载配置文件

        从程序根目录的 config.ini 读取：
        1. 路径配置作为默认值（用于 GUI 默认路径）
        2. 删除选项配置作为默认值

        打包后程序根目录 = exe 所在目录，因此 exe 同级的 config.ini 会生效。
        """
        self.config, self.config_path, self.config_loaded = load_config()
        cfg = self.config

        # 默认值从 config.ini 的 PATHS / OPTIONS 段读取
        default_input_dir = resolve_path(cfg.get('PATHS', 'input_dir', fallback=''), get_app_root())
        default_output_dir = resolve_path(cfg.get('PATHS', 'output_dir', fallback=''), get_app_root())

        default_delete_source = cfg.getboolean('OPTIONS', 'delete_source', fallback=True)
        default_delete_empty_dirs = cfg.getboolean('OPTIONS', 'delete_empty_dirs', fallback=True)
        default_delete_lyrics = cfg.getboolean('OPTIONS', 'delete_lyrics', fallback=True)

        default_metadata_processing_mode = cfg.get('OPTIONS', 'metadata_processing_mode', fallback='batch')
        default_skip_metadata_during_decrypt = cfg.getboolean(
            'OPTIONS', 'skip_metadata_during_decrypt', fallback=True
        )

        # 输出整理方式：album / artist / flat
        default_folder_mode = normalize_folder_mode(
            cfg.get('OUTPUT', 'folder_mode', fallback='album')
        )

        if self.config_loaded:
            print(f"[配置] 已加载配置文件: {self.config_path}")
        else:
            print(f"[配置] 配置文件不存在: {self.config_path}，使用默认配置")

        # 保存为实例变量，供后续使用
        self.default_input_dir = default_input_dir
        self.default_output_dir = default_output_dir
        self.default_delete_source = default_delete_source
        self.default_delete_empty_dirs = default_delete_empty_dirs
        self.default_delete_lyrics = default_delete_lyrics
        self.metadata_processing_mode = default_metadata_processing_mode
        self.skip_metadata_during_decrypt = default_skip_metadata_during_decrypt
        self.folder_mode = default_folder_mode

    def get_folder_mode(self):
        """从下拉框读取整理方式（返回 album / artist / flat）"""
        label = self.folder_mode_var.get()
        for choice_label, choice_value in FOLDER_MODE_CHOICES:
            if choice_label == label:
                return choice_value
        return normalize_folder_mode(label)

    def _on_folder_mode_changed(self, _event=None):
        """用户切换整理方式后立即保存到 config.ini（仅打包后的 exe）"""
        self.folder_mode = self.get_folder_mode()
        if not getattr(sys, 'frozen', False):
            return
        try:
            save_setting_to_config(
                self.config_path, 'OUTPUT', 'folder_mode', self.folder_mode
            )
            logging.info(f"已保存整理方式: {folder_mode_label(self.folder_mode)}")
        except Exception as e:
            logging.warning(f"保存整理方式失败: {e}")

    def _save_paths_to_config(self):
        """把用户选择的路径写回 exe 同级的 config.ini（仅打包后的 exe 自动保存）"""
        if not getattr(sys, 'frozen', False):
            return
        try:
            save_paths_to_config(self.config_path, self.input_path.get(), self.output_path.get())
            logging.info(f"已保存路径到配置文件: {self.config_path}")
        except Exception as e:
            logging.warning(f"保存路径到配置文件失败: {e}")

    def browse_input(self):
        path = filedialog.askdirectory(title="选择加密文件目录")
        if path:
            self.input_path.set(path)
            self._save_paths_to_config()
    
    def browse_output(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_path.set(path)
            self._save_paths_to_config()
    
    def log(self, message, level=logging.INFO):
        logging.getLogger().log(level, message)
    
    def clear_log(self):
        self.log_area.delete(1.0, tk.END)
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def update_stats(self, total, success, failed, skipped):
        self.stats_text.set(f"总文件: {total}, 成功: {success}, 失败: {failed}, 跳过: {skipped}")
    
    def start_decryption(self):
        if not self.input_path.get() or not self.output_path.get():
            messagebox.showerror("错误", "请选择输入和输出目录")
            return
        
        if not os.path.exists(self.input_path.get()):
            messagebox.showerror("错误", "输入目录不存在")
            return

        # 读取本次选择的整理方式
        self.folder_mode = self.get_folder_mode()
        if getattr(sys, 'frozen', False):
            try:
                save_setting_to_config(self.config_path, 'OUTPUT', 'folder_mode', self.folder_mode)
            except Exception:
                pass
        
        # 创建输出目录
        os.makedirs(self.output_path.get(), exist_ok=True)
        
        # 更新UI状态
        self.is_processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress['value'] = 0

        # 新增：重置删除统计
        self.deleted_files = 0
        self.deleted_dirs = 0
        
        # 在新线程中运行解密
        thread = threading.Thread(target=self.run_decryption)
        thread.daemon = True
        thread.start()
    
    def stop_decryption(self):
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.update_status("解密已停止")

        # 断开Frida连接
        if self.session:
            try:
                self.session.detach()
            except:
                pass

    def reorganize_existing(self):
        """按当前整理方式整理已有输出目录（不需要重新解密）"""
        if self.is_processing:
            messagebox.showwarning("请稍候", "当前正在处理文件，请等待完成后再整理。")
            return

        output_dir = self.output_path.get().strip()
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showerror("错误", "输出目录不存在")
            return

        mode = self.get_folder_mode()
        label = folder_mode_label(mode)
        if not messagebox.askyesno(
            "整理已有文件",
            f"将按「{label}」整理以下目录：\n{output_dir}\n\n"
            "会移动音频和歌词、合并重复的专辑文件夹，并清理空目录。\n"
            "是否继续？",
        ):
            return

        self.folder_mode = mode
        self.is_processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.update_status(f"正在整理：{label}")
        self.log("=" * 50)
        self.log(f"开始整理已有输出目录: {output_dir}")
        self.log(f"整理方式: {label}")

        def worker():
            try:
                stats = reorganize_output(output_dir, mode, logger=self.log)
                self.log(summary_text(stats))
                self.log("整理完成")
                self.root.after(0, lambda: messagebox.showinfo("整理完成", summary_text(stats)))
            except Exception as e:
                self.log(f"整理失败: {e}", logging.ERROR)
                error_text = str(e)
                self.root.after(0, lambda: messagebox.showerror("整理失败", error_text))
            finally:
                def restore_ui():
                    self.is_processing = False
                    self.start_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.DISABLED)
                    self.update_status("整理完成")

                self.root.after(0, restore_ui)

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def copy_lyrics_file(self, input_file, output_file):
        """
        复制同名的歌词文件到输出目录

        Args:
            input_file: 输入音频文件的完整路径
            output_file: 输出音频文件的完整路径
        """
        input_lyric = os.path.splitext(input_file)[0] + ".lrc"
        output_lyric = os.path.splitext(output_file)[0] + ".lrc"

        if not os.path.exists(input_lyric):
            return

        try:
            os.makedirs(os.path.dirname(output_lyric), exist_ok=True)
            shutil.copy2(input_lyric, output_lyric)
        except Exception as e:
            pass

    def delete_source_file(self, input_file, delete_lyrics=False):
        """
        删除源文件和（可选的）歌词文件

        注意：
        - 只检查源文件是否存在，不验证歌词复制是否成功（简化方案）
        - copy_lyrics_file() 方法无需修改

        Args:
            input_file: 输入文件的完整路径
            delete_lyrics: 是否同时删除歌词文件

        Returns:
            int: 删除的文件数量
        """
        deleted_count = 0

        try:
            # 删除源音频文件（解密成功后文件一定存在）
            if os.path.exists(input_file):
                os.remove(input_file)
                deleted_count += 1
                self.log(f"✓ 已删除源文件: {os.path.basename(input_file)}")

            # 删除歌词文件（只在源文件存在时检查）
            if delete_lyrics:
                lyric_file = os.path.splitext(input_file)[0] + ".lrc"
                if os.path.exists(lyric_file):
                    os.remove(lyric_file)
                    deleted_count += 1
                    self.log(f"✓ 已删除歌词文件: {os.path.basename(lyric_file)}")

        except Exception as e:
            self.log(f"删除文件失败: {e}", logging.WARNING)

        return deleted_count

    def cleanup_empty_dirs(self, dir_path, root_dir):
        """
        递归删除空目录，直到 root_dir

        Args:
            dir_path: 要检查的目录路径
            root_dir: 根目录（停止删除的边界）

        Returns:
            int: 删除的目录数量
        """
        deleted_count = 0

        # 规范化路径
        dir_path = os.path.normpath(dir_path)
        root_dir = os.path.normpath(root_dir)

        # 如果已经到达根目录或超出范围，停止
        if dir_path == root_dir or not dir_path.startswith(root_dir):
            return deleted_count

        try:
            # 检查目录是否为空
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.rmdir(dir_path)
                deleted_count += 1
                self.log(f"✓ 已删除空目录: {dir_path}")

                # 递归删除父目录
                parent_dir = os.path.dirname(dir_path)
                deleted_count += self.cleanup_empty_dirs(parent_dir, root_dir)

        except Exception as e:
            self.log(f"删除目录失败: {e}", logging.WARNING)

        return deleted_count

    def add_flac_metadata(self, flac_file_path):
        """
        为 FLAC 文件添加元数据（音轨号、封面、发行年份）
        
        Args:
            flac_file_path (str): FLAC 文件路径
        """
        try:
            filename = os.path.basename(flac_file_path)
            
            # 步骤1：添加音轨号
            track_number = extract_track_number_from_filename(filename)
            
            if track_number is not None:
                success = add_track_number_to_flac(flac_file_path, track_number)
                if success:
                    self.log(f"✓ 已添加音轨号 {track_number}")
                else:
                    self.log(f"✗ 添加音轨号失败", logging.WARNING)
            
            # 步骤2：处理专辑元数据（封面、发行年份）
            self.log("获取专辑信息...")
            api_client = QQMusicAPIClient()
            result = process_album_metadata(flac_file_path, api_client, use_cache=True)
            
            if result['success']:
                metadata = result.get('metadata', {})
                if metadata:
                    pub_year = metadata.get('pub_year')
                    if pub_year:
                        self.log(f"✓ 已添加发行年份 {pub_year}")
                        
                    if metadata.get('cover_data'):
                        self.log("✓ 已嵌入封面到文件")
                        self.log("✓ 已保存封面到 cover.jpg")
            else:
                self.log(f"未找到专辑信息: {result['message']}", logging.WARNING)
        
        except Exception as e:
            self.log(f"添加元数据异常: {e}", logging.WARNING)

    def run_supplement_metadata(self, album_dir):
        """
        运行元数据补充

        处理整个输出目录，批量添加音轨号、封面、年份
        """
        try:
            from supplement_album_metadata import process_album_directory
            process_album_directory(album_dir)
            self.log("✓ 元数据批量补充完成")
        except ImportError as e:
            self.log(f"导入元数据处理模块失败: {e}", logging.ERROR)
        except Exception as e:
            self.log(f"处理元数据时出错: {e}", logging.ERROR)

    def run_decryption(self):
        try:
            input_dir = self.input_path.get()
            output_dir = self.output_path.get()
            
            self.log("正在连接到QQ音乐进程...")
            self.update_status("正在连接到QQ音乐...")
            
            # 连接到QQ音乐进程
            try:
                self.session = frida.attach("QQMusic.exe")
                self.log("✓ 成功连接到QQ音乐进程")
            except Exception as e:
                self.log(f"✗ 连接QQ音乐进程失败: {e}", logging.ERROR)
                self.log("请确保: 1) QQ音乐正在运行 2) frida-server已启动", logging.ERROR)
                self.stop_decryption()
                return
            
            # 加载解密脚本（兼容源码运行与 PyInstaller 打包）
            try:
                hook_path = resource_path("hook_qq_music.js")
                with open(hook_path, "r", encoding="utf-8") as f:
                    script_code = f.read()
                self.script = self.session.create_script(script_code)
                self.script.load()
                self.log("✓ 解密脚本加载成功")
            except Exception as e:
                self.log(f"✗ 加载解密脚本失败: {e}", logging.ERROR)
                self.stop_decryption()
                return
            
            # 查找加密文件
            self.log("正在扫描加密文件...")
            self.update_status("正在扫描文件...")
            
            encrypted_files = []
            for root, dirs, files in os.walk(input_dir):
                for file in files:
                    file_ext = os.path.splitext(file)[-1].lower()
                    if file_ext in [".mflac", ".mgg"]:
                        encrypted_files.append(os.path.join(root, file))
            
            if not encrypted_files:
                self.log("未找到任何.mflac或.mgg文件", logging.WARNING)
                self.stop_decryption()
                return
            
            self.log(f"找到 {len(encrypted_files)} 个加密文件")
            self.update_status(f"开始解密 {len(encrypted_files)} 个文件...")
            
            # 统计变量
            total_files = len(encrypted_files)
            success_files = 0
            failed_files = 0
            skipped_files = 0
            
            # 处理每个文件
            for i, encrypted_file in enumerate(encrypted_files):
                if not self.is_processing:
                    break
                
                # 更新进度
                progress = (i / total_files) * 100
                self.progress['value'] = progress
                self.update_stats(total_files, success_files, failed_files, skipped_files)
                
                # 获取相对路径以保留目录结构
                relative_path = os.path.relpath(encrypted_file, input_dir)
                file_name = os.path.basename(encrypted_file)
                self.log(f"处理文件 {i+1}/{total_files}: {file_name}")
                
                # 构建输出文件名
                file_ext = os.path.splitext(file_name)[-1].lower()
                if file_ext == ".mflac":
                    output_ext = ".flac"
                else:  # .mgg
                    output_ext = ".ogg"
                
                output_file = os.path.splitext(file_name)[0] + output_ext
                # 替换扩展名并保留目录结构
                relative_path = os.path.splitext(relative_path)[0] + output_ext
                output_file_path = os.path.join(output_dir, relative_path)
                
                # 创建输出目录（包含子目录）
                output_dir_with_path = os.path.dirname(output_file_path)
                os.makedirs(output_dir_with_path, exist_ok=True)
                
                
                # 检查文件是否已存在
                if os.path.exists(output_file_path):
                    self.log(f"文件已存在，跳过: {output_file}")
                    skipped_files += 1
                    continue
                
                # 创建临时文件名
                temp_file_name = hashlib.md5(encrypted_file.encode()).hexdigest() + output_ext
                temp_file_path = os.path.join(output_dir, temp_file_name)
                
                try:
                    # 调用解密函数
                    self.log(f"开始解密: {file_name}")
                    result = self.script.exports_sync.decrypt(encrypted_file, temp_file_path)
                    
                    if "Success" in result:
                        # 新布局下，输出目录里可能已经有这首歌，避免重复生成副本
                        if self.folder_mode != 'mirror':
                            try:
                                layout_target = build_output_path(
                                    output_dir,
                                    read_audio_info(temp_file_path),
                                    self.folder_mode,
                                    temp_file_path,
                                )
                                if os.path.exists(layout_target) and not os.path.samefile(
                                    temp_file_path, layout_target
                                ):
                                    os.remove(temp_file_path)
                                    skipped_files += 1
                                    self.log(f"目标已存在，跳过: {os.path.basename(layout_target)}")
                                    continue
                            except Exception as e:
                                self.log(f"检查整理目标失败: {e}", logging.WARNING)

                        # 重命名临时文件
                        os.rename(temp_file_path, output_file_path)
                        success_files += 1
                        self.log(f"✓ 解密成功: {output_file}")

                        # 跳过解密时的元数据修改
                        # 元数据将在所有文件解密完成后统一处理
                        if not self.skip_metadata_during_decrypt and output_file_path.lower().endswith('.flac'):
                            self.add_flac_metadata(output_file_path)

                        self.copy_lyrics_file(encrypted_file, output_file_path)

                        # === 新增：删除源文件和空目录 ===
                        if self.delete_source_var.get():
                            # 删除源文件和歌词文件
                            deleted_count = self.delete_source_file(
                                encrypted_file,
                                self.delete_lyrics_var.get()
                            )
                            self.deleted_files += deleted_count

                            # 删除空目录
                            if self.delete_empty_dirs_var.get():
                                file_dir = os.path.dirname(encrypted_file)
                                deleted_dirs = self.cleanup_empty_dirs(file_dir, input_dir)
                                self.deleted_dirs += deleted_dirs
                        # ===============================
                    else:
                        failed_files += 1
                        self.log(f"✗ 解密失败: {file_name} - {result}", logging.ERROR)
                        # 清理临时文件
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                            
                except Exception as e:
                    failed_files += 1
                    self.log(f"✗ 处理文件时出错: {file_name} - {e}", logging.ERROR)
                    # 清理临时文件
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
            
            # 完成处理
            self.progress['value'] = 100
            self.update_stats(total_files, success_files, failed_files, skipped_files)
            if self.is_processing:
                self.log("=" * 50)
                self.log("批量解密完成!")
                self.log(f"总文件数: {total_files}")
                self.log(f"成功: {success_files}")
                self.log(f"失败: {failed_files}")
                self.log(f"跳过: {skipped_files}")
                self.log(f"已删除文件: {self.deleted_files}")
                self.log(f"已删除目录: {self.deleted_dirs}")
                self.log(f"输出目录: {output_dir}")
                self.log(f"输出整理: {folder_mode_label(self.folder_mode)}")

                # 解密完成后统一处理元数据（批量模式）
                if self.metadata_processing_mode == 'batch':
                    self.log("=" * 50)
                    self.log("解密完成，开始统一处理元数据")
                    self.log("=" * 50)
                    self.update_status("正在补充元数据...")

                    # 调用批量元数据处理
                    self.run_supplement_metadata(output_dir)

                    self.log("=" * 50)
                    self.log("元数据处理完成")
                    self.log("=" * 50)

                # 按用户选择的方式整理输出目录
                if self.folder_mode != 'mirror':
                    self.log("=" * 50)
                    self.log(f"开始整理输出目录（{folder_mode_label(self.folder_mode)}）")
                    self.log("=" * 50)
                    self.update_status("正在整理输出目录...")
                    try:
                        layout_stats = reorganize_output(
                            output_dir, self.folder_mode, logger=self.log
                        )
                        self.log(summary_text(layout_stats))
                    except Exception as e:
                        self.log(f"整理输出目录失败: {e}", logging.ERROR)

                self.update_status("解密完成")

                if failed_files == 0:
                    messagebox.showinfo("完成", 
                        f"解密完成！成功处理 {success_files} 个文件。\n"
                        f"已删除文件: {self.deleted_files}\n"
                        f"已删除目录: {self.deleted_dirs}")
                else:
                    messagebox.showwarning("完成", 
                        f"解密完成！\n"
                        f"成功: {success_files}\n"
                        f"失败: {failed_files}\n"
                        f"跳过: {skipped_files}\n"
                        f"已删除文件: {self.deleted_files}\n"
                        f"已删除目录: {self.deleted_dirs}")
            
        except Exception as e:
            self.log(f"解密过程发生错误: {e}", logging.ERROR)
            messagebox.showerror("错误", f"解密过程发生错误: {e}")
        
        finally:
            # 断开连接
            if self.session:
                try:
                    self.session.detach()
                except:
                    pass
            
            # 恢复UI状态
            self.is_processing = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

if __name__ == "__main__":
    enable_utf8_console()
    # 检查frida是否可用
    try:
        import frida
    except ImportError:
        print("错误: 未安装frida，请先运行: pip install -r requirements.txt")
        input("按回车键退出...")
        sys.exit(1)
    
    root = tk.Tk()
    app = QQMusicDecryptorGUI(root)
    root.mainloop()

# 🎵 QQ Music 解密工具

[![GitHub release](https://img.shields.io/github/v/release/LumiCorn/qqmusic-decryptor)](https://github.com/LumiCorn/qqmusic-decryptor/releases)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue)](https://www.gnu.org/licenses/agpl-3.0)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Frida](https://img.shields.io/badge/frida-16.7.10-green)](https://frida.re/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

> 🎯 批量解密 QQ 音乐加密音频文件（`.mflac`/`.mgg`）为标准格式（`.flac`/`.ogg`），并补充专辑元数据，一站式全自动搞定。

**[English Documentation](README.md)**

---

## ✨ 功能特性

- 🔓 **解密** — 通过 Frida 动态插桩将 `.mflac` → `.flac`、`.mgg` → `.ogg`
- 🖼️ **专辑元数据** — 嵌入专辑封面 + 从 QQ Music API 获取发行年份
- 📂 **保留目录结构** — 保持原始文件夹层次，井井有条
- ⏭️ **智能跳过** — 自动跳过已转换的文件，不重复劳动
- 🔄 **错误重试** — 失败自动重试（可配置，默认 3 次）
- 📋 **详细日志** — 逐文件解密日志 + JSON 统计摘要
- 🖥️ **双界面** — 命令行和图形界面两种模式，任你选择

---

## 🚀 快速开始

### 📋 前置条件

- ✅ **Python 3.8+**
- ✅ **QQ Music** 客户端已安装并登录 VIP 账号
- ✅ Windows 系统（工具通过 Frida 注入 `QQMusic.exe`）

### 📦 安装

```bash
# 1. 克隆仓库
git clone https://github.com/LumiCorn/qqmusic-decryptor.git
cd qqmusic-decryptor

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3.（可选）注册全局命令，方便任意位置使用
pip install -e .
```

安装后即可在任意位置使用 `qqmusic-decrypt`、`qqmusic-meta`、`qqmusic-gui` 命令。🎉

---

## 🪟 直接使用可执行程序（Windows）

已打包好的程序位于 `dist/QQMusicDecryptor/`：

| 程序 | 说明 |
|------|------|
| `QQMusicDecryptor.exe` | 🖥️ 图形界面版，双击启动，无控制台 |
| `QQMusicDecryptor-Admin.exe` | 🛡️ 管理员可见版，双击后通过 UAC 请求管理员权限，显示日志并执行解密 |

两个程序都会读取 **exe 所在目录（程序根目录）的 `config.ini`**，而不是当前工作目录；修改 `[PATHS]` 中的 `input_dir` / `output_dir` 后保存即可生效。

```ini
[PATHS]
input_dir = D:\Music\QQMusic\Download
output_dir = D:\Music\QQMusic\Decrypted
```

如果不确定程序实际读取的是哪个文件、哪个目录，可以运行：

```bash
QQMusicDecryptor-Admin.exe --info
```

它会列出程序根目录、实际加载的 `config.ini`、输入/输出目录、日志位置，且不会执行解密。

自行构建可执行程序：

```bash
pip install -r requirements.txt pyinstaller
python build_exe.py
```

产物：`dist/QQMusicDecryptor/` 与 `dist/QQMusicDecryptor-windows-x64.zip`。

> 🐞 已修复：此前命令行版本和打包后的 exe 在没有显式传 `--config` 时不会读取根目录的 `config.ini`，而是退回硬编码的 `G:\QQMusic\...` 默认路径。

---

## 📖 使用说明

### ⚡ 全局命令（执行 `pip install -e .` 后）

| 命令 | 作用 |
|------|------|
| `qqmusic-decrypt` | 🔓 解密全部文件 + 补充元数据 |
| `qqmusic-meta` | 🖼️ 仅补充专辑元数据（封面 + 年份） |
| `qqmusic-gui` | 🖥️ 启动图形界面 |

### 🐚 Shell 脚本（Git Bash）

```bash
# 解密 + 元数据补充（全流程）
bash src/shell/auto_decrypt.sh

# 仅解密（GUI 前台模式）
bash src/shell/run_gui_simple.sh

# 仅解密（GUI 后台模式）
bash src/shell/start_gui.sh

# 仅补充专辑元数据
bash src/shell/run_supplement.sh

# 检查环境
bash src/shell/check_env.sh
```

### 🪟 Batch 脚本（Windows）

双击即可运行：

| 脚本 | 作用 |
|------|------|
| `src/bat/run_gui_simple.bat` | 🖥️ 启动 GUI（前台） |
| `src/bat/start_gui_english.bat` | 🖥️ 启动 GUI（英文提示 + 前置检查） |
| `src/bat/run_supplement.bat` | 🖼️ 补充专辑元数据 |
| `src/bat/auto_decrypt.bat` | 🔓 全流程解密 |
| `src/bat/check_env.bat` | 🔍 环境检查 |
| `src/bat/install_dependencies.bat` | 📦 一键安装依赖 |

### ⌨️ 命令行参数

```bash
# 自定义路径解密
python src/main_cli.py --input "D:\Music" --output "D:\Output"

# 为指定专辑目录补充元数据
python src/supplement_album_metadata.py "D:\Music\Decrypted\专辑名"

# 试运行（不实际修改文件）
python src/supplement_album_metadata.py "D:\Music\Decrypted" --dry-run

# 详细日志输出
python src/main_cli.py --verbose
```

---

## ⚙️ 配置说明

编辑项目根目录的 `config.ini`：

```ini
[PATHS]
input_dir = G:\QQMusic\Download\VipSongsDownload
output_dir = G:\QQMusic\Decrypted

[OUTPUT]
# album = 按专辑分文件夹（推荐）
# artist = 按歌手分文件夹
# flat = 不分文件夹
folder_mode = album

[OPTIONS]
max_retries = 3
preserve_structure = true
skip_existing = true
delete_source = true
```

### 📂 输出整理方式

QQ 音乐的下载目录通常按「歌手/专辑」存放，同一张专辑如果有很多合作歌手，会被拆成多个歌手文件夹。`[OUTPUT] folder_mode` 控制解密后的整理方式：

| 值 | 效果 |
|----|------|
| `album` | 🎵 按专辑分文件夹：把同一张专辑散落在不同歌手文件夹中的曲目合并，文件名按音轨号排序（`01 歌名.flac`），歌词同步改名并修正 `[ti]/[ar]/[al]` |
| `artist` | 🎤 按主歌手分文件夹：每首歌取第一主歌手，文件夹内按歌名排序 |
| `flat` | 📁 不分文件夹：所有歌曲直接放在输出目录，文件名使用「歌手 - 歌名」 |

图形界面可以直接在「输出整理」下拉框中选择；管理员版也可以用 `--layout` 指定。

### 🧹 整理已有输出目录

如果之前已经解密过、但文件夹很乱，不需要重新解密：

```bash
# 按专辑整理已有文件（会移动音频和歌词、合并专辑文件夹、清理空目录）
QQMusicDecryptor-Admin.exe --reorganize --layout album

# 只预览会移动到哪里，不修改任何文件
QQMusicDecryptor-Admin.exe --reorganize --layout album --dry-run
```

图形界面中也可以点击「整理已有文件」按钮。

补充元数据时也可直接传参：

```bash
qqmusic-meta "D:/MyMusic/Decrypted"
```

---

## 📁 项目结构

```
qqmusic-decryptor/
├── src/                        # 📂 源码目录
│   ├── main_cli.py             # ⚙️ CLI 解密引擎
│   ├── supplement_album_metadata.py  # 🖼️ 专辑元数据工具
│   ├── metadata_utils.py       # 🛠️ 元数据工具库
│   ├── qqmusic_api_client.py   # 🌐 QQ Music API 客户端
│   ├── hook_qq_music.js        # 🪝 Frida Hook 脚本
│   ├── qqmusic_decrypt/        # 🔗 全局 CLI 入口
│   │   └── cli.py              # qqmusic-decrypt / -meta / -gui
│   ├── gui/                    # 🖥️ GUI 应用
│   │   └── main_gui.py
│   ├── bat/                    # 🪟 Batch 脚本 (.bat)
│   └── shell/                  # 🐚 Shell 脚本 (.sh)
├── docs/                       # 📚 文档目录（用户指南、开发文档、更新日志）
├── config.ini                  # ⚙️ 用户配置文件
├── pyproject.toml              # 📦 包配置（全局命令注册）
├── requirements.txt            # 📄 Python 依赖
├── AGENTS.md                   # 🤖 AI 助手项目指南
├── README.md                   # 🇺🇸 English documentation
└── README.zh-CN.md             # 🇨🇳 中文文档
```

---

## 🧩 工作原理

1. 🪝 **Frida** 注入 QQ Music 进程（`QQMusic.exe`）
2. 🎯 Hook `QQMusicCommon.dll` 中的 `EncAndDesMediaFile` 类
3. 📖 以 64KB 块大小读取解密后的音频数据
4. 💾 写入临时文件，重命名为最终格式
5. 🖼️ 可选步骤：通过 QQ Music API 补充元数据（封面、发行年份）

> 💡 无需单独下载 `frida-server.exe` — Frida Python 包自带内置 helper 进程，开箱即用。

---

## ❓ 常见问题

**💬 需要单独下载 frida-server 吗？**  
不需要。Frida Python 包自带内置 helper 进程，开箱即用。

**💬 没有 VIP 账号能用吗？**  
不能。解密依赖 QQ Music 内部的解密函数，需要有效的 VIP 会话。

**💬 为什么用 Frida 而不是直接解析文件？**  
QQ 音乐的加密文件采用私有格式，只能由 QQ Music 进程本身解密。Frida 让我们能实时调用原生解密函数。

**💬 能在 Linux/macOS 上运行吗？**  
工具主要为 Windows 设计（注入 `QQMusic.exe`）。CLI 和元数据工具在其他平台可能可用，但需要能访问 QQ Music 进程。

---

## 📜 许可证

[GNU AGPL v3](LICENSE) © 2026 — 自由使用、修改、分享。开源 forever。🎵

---

## 🙏 致谢

- [Frida](https://frida.re/) — 动态插桩工具包
- [mutagen](https://mutagen.readthedocs.io/) — 音频元数据处理
- [FountainChan/qqmusic-decryptor](https://github.com/FountainChan/qqmusic-decryptor) — 上游项目，本仓库基于它继续开发。
- [strelitzia-reg/qqmusic-decryptor](https://github.com/strelitzia-reg/qqmusic-decryptor) — 本项目的原项目和灵感来源。GUI 界面（`src/gui/`）修改自该项目。感谢！🙌

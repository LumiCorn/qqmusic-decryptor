# Changelog

## [Unreleased]

## [1.2.0] - 2026-11-07

### Added
- Add LICENSE (AGPL v3)
- Add CONTRIBUTING.md
- Add proper credits to original project `strelitzia-reg/qqmusic-decryptor`
- Add `src/app_paths.py`: unified program-root / `config.ini` / resource resolution
- Add `src/admin_launcher.py`: visible console program that self-elevates via UAC and decrypts using the `config.ini` next to the exe
- Add `build_exe.py`: one-command build of the GUI and admin executables into one shared `dist/QQMusicDecryptor/`
- Add `--info` to the CLI and admin program to print the resolved config and directories
- Add regression tests in `tests/test_app_paths.py`
- Add `src/output_layout.py`: album / artist / flat output organization, lyric renaming and `[ti]/[ar]/[al]` correction
- Add `[OUTPUT] folder_mode` config option and GUI output-layout dropdown
- Add `--layout` / `--reorganize` / `--dry-run` to the CLI and admin program
- Add "整理已有文件" button to the GUI to reorganize an existing output folder without re-decrypting
- Add tests for output organization and album grouping

### Fixed
- CLI ignored the root `config.ini` when `--config` was omitted and always fell back to hard-coded `G:\QQMusic\...` paths
- Packaged exe could not find `config.ini` / `hook_qq_music.js` / `logs` because paths were derived from `__file__` or the current working directory
- GUI wrote saved paths to the current working directory instead of the exe's `config.ini`
- Metadata supplement is now called in-process, so packaged executables no longer require a separate `python` interpreter
- Album metadata supplement now splits a directory containing multiple albums by tags, so artist/flat layouts no longer overwrite every song with the first album's year/cover

### Changed
- Clean up residual files for open-source release
- Update .gitignore with explicit hidden directory listing

## [1.1.0] - 2026-01-31

### Added
- GUI log management
- CLI: `qqmusic-decrypt` global command via `pip install -e .`

### Fixed
- Major fixes and optimizations (see detailed logs)

## [1.0.0] - 2026-01-30

### Added
- Batch decrypt `.mflac` → `.flac`, `.mgg` → `.ogg` via Frida
- Album metadata supplement (cover art embed + release year from QQ Music API)
- Directory structure preservation
- Smart skip for already-converted files
- Error retry mechanism (configurable, default 3 attempts)
- Detailed logging with JSON stats summary
- Dual interface: CLI and GUI modes
- Track number writing from filename
- OGG metadata support
- Source file deletion option
- Lyrics file copy feature

### Changed
- Metadata processing optimized with batch mode
- Switch to QQ Music official API for album covers
- Reorganize project structure

## [0.x] - 2026-01-28/29

### Added
- Initial project setup
- Basic decrypt functionality
- Album metadata supplement (first working version)
- Cover art save path fix

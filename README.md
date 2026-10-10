<p align="center">
  <img src="assets/Banner.png" alt="Omni Download Manager â€” project banner" width="100%">
</p>

# Omni Download Manager

<p align="center">
  <strong>A modern, lightweight HTTP/HTTPS download manager for Windows, built with Python and PySide6.</strong><br>
  <strong>ÛŒÚ© Ø¯Ø§Ù†Ù„ÙˆØ¯Ù…Ù†ÛŒØ¬Ø± Ù…Ø¯Ø±Ù† Ùˆ Ø³Ø¨Ú© Ø¨Ø±Ø§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§ÛŒ HTTP/HTTPS Ø¯Ø± ÙˆÛŒÙ†Ø¯ÙˆØ²ØŒ Ø³Ø§Ø®ØªÙ‡â€ŒØ´Ø¯Ù‡ Ø¨Ø§ Python Ùˆ PySide6.</strong>
</p>

<p align="center">
  <b>Version 0.2.0</b> Â· <b>Python + PySide6</b> Â· <b>Portable &amp; Setup builds</b> Â· <b>142 Tests Passing</b>
</p>

---

## ðŸ‡¬ðŸ‡§ English

### Overview

**Omni Download Manager (ODM)** is a desktop download manager built with **Python and PySide6**. It focuses on a reliable core download workflow while providing queue management, pause/resume, retries, scheduling, speed limiting, search, filtering, history, notifications, and a modern dark/light interface.

The project is designed as a modular foundation that can grow into a more capable download-management application without coupling the download engine tightly to the user interface.

### âœ¨ Highlights

| | Capability | | Capability |
|---|---|---|---|
| âš¡ | HTTP/HTTPS downloads | ðŸ”— | Adaptive multi-connection downloads |
| â¯ï¸ | Pause & resume | ðŸ” | Automatic retry |
| ðŸš€ | Up to 5 active downloads | ðŸ¢ | Global speed limit |
| ðŸ—“ï¸ | One-time scheduling | ðŸ”Ž | Search & sorting |
| ðŸ—‚ï¸ | File categories & filters | â˜‘ï¸ | Bulk actions |
| ðŸ’¾ | SQLite download history | ðŸŒ“ | Dark & light themes |
| ðŸ”” | Windows completion notifications | ðŸ“¦ | Portable Windows build |

### Download engine

- HTTP and HTTPS downloads.
- Streaming downloads directly to disk instead of loading the complete file into memory.
- Automatically uses up to **4 HTTP Range connections** for eligible files when the server returns valid partial responses; otherwise it falls back to a normal download.
- Progress percentage, downloaded/total size, speed, and estimated remaining time when the total size is known.
- Multi-part progress is aggregated from actual bytes and its segment state is persisted for safe resume after pausing or restarting.
- Pause/resume through HTTP `Range` when supported by the server.
- Incomplete downloads are kept as `.part` files so they can be resumed.
- Manual retry plus up to **3 automatic retries** for transient failures, with increasing delays.
- Filename detection from `Content-Disposition` or the URL.
- Existing files are not overwritten; conflicting names are automatically renamed, for example `report (1).pdf`.
- Cancelled downloads remove their partial data, while paused downloads keep it for later resume.

### Queue, scheduling & speed control

- FIFO download queue.
- Up to **5 active downloads** at the same time.
- Optional global download-speed limit shared by active downloads.
- One-time scheduling based on local date/time.
- Scheduled downloads are persisted and can continue after restarting the application.
- Downloads interrupted by closing the application are restored as paused items.

### Download library

- Views for **All Downloads, In Progress, Completed, and Failed**.
- Search by filename or URL.
- Sort by newest, oldest, filename, or file size.
- File-type categories: Archives, Video, Audio, Images, Documents, Programs, and Other.
- Multi-selection with `Ctrl` / `Shift`; a plain click selects one row, and clicking that selected row again clears the selection.
- Bulk pause, resume, cancel, and remove actions.
- Open downloaded files or their containing folders.
- Copy download URLs from the context menu.
- Optional deletion of a completed file from disk when removing its history entry.

### Interface & settings

- Modern **PySide6 / Qt 6** desktop interface.
- Dark and light themes with a pink accent design.
- Windows title-bar integration where supported.
- Configurable default download directory.
- Option to start downloads immediately.
- Confirmation before destructive actions.
- Configurable connection and read timeouts.
- Windows completion notifications, enabled by default.
- Optional system-proxy support, enabled by default.
- Settings are saved automatically.

---

## ðŸ–¼ï¸ Screenshots

The gallery below highlights the interface redesign introduced in **v0.2.0**.

<!-- Keep screenshots free of personal usernames, paths, and private filenames. -->
<p align="center">
  <strong>Previous interface</strong>
</p>
<p align="center">
  <img src="assets/ui-before.png" alt="Omni Download Manager previous interface" width="900">
</p>

<p align="center">
  <strong>Redesigned interface Â· v0.2.0</strong>
</p>
<p align="center">
  <img src="assets/ui-v0.2.0.png" alt="Omni Download Manager redesigned interface in version 0.2.0" width="900">
</p>

---

## ðŸ› ï¸ Technology

| Area | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | PySide6 / Qt 6 |
| HTTP | `requests` |
| Database | SQLite / `sqlite3` |
| Settings | JSON |
| Packaging | PyInstaller |
| Installer | Inno Setup |
| Testing | Python `unittest` |

The runtime dependency set is intentionally small: **PySide6** and **requests** are the main third-party dependencies.

---

## ðŸš€ Getting Started

### Windows â€” easiest method

From the project root:

```bat
run.bat
```

The script creates the virtual environment when needed, installs dependencies, and starts the application.

### Manual setup

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

You can also run the package directly:

```bat
python -m omni_download_manager
```

For an editable installation and the `odm` command:

```bat
python -m pip install -e .
odm
```

---

## ðŸ“¦ Portable Windows Version

ODM is distributed in two ways: a portable folder and a Windows Setup installer.

### Portable

1. Extract the ZIP package completely.
2. Keep the `_internal` folder next to `Omni Download Manager.exe`.
3. Run `Omni Download Manager.exe`.

> **Important:** the portable executable must not be separated from `_internal`.

### Setup installer

The Inno Setup script `omni download manager v 0.2.0.iss` packages the same folder into `installer\Omni-Download-Manager-Setup.exe`. See [Build a Windows Release](#-build-a-windows-release).

---

## ðŸ§ª Testing

Run the complete test suite with:

```bat
python -m unittest discover -s tests -t .
```

The current verified suite contains **142 passing tests**. Coverage includes download behavior, HTTP Range detection and fallback, multi-part transfer integrity and fallback, pause/resume, queue scheduling, retries, shared speed limiting, scheduled starts, restart recovery, event dispatching outside the manager lock, category filtering, system-proxy configuration, search/sorting, list selection and bulk actions, persistence, completion notifications, and icon loading.

Download-related tests use a **local HTTP server**, so they do not depend on an external download service.

---

## ðŸ—ï¸ Architecture

```text
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚        PySide6 / Qt UI        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                â”‚ Qt events/signals
                â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚       Download Manager        â”‚
â”‚ queue Â· retry Â· scheduling   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
        â”‚               â”‚
        â–¼               â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Adaptive HTTP Engine    â”‚  â”‚   SQLite     â”‚
â”‚ single / multi-part     â”‚  â”‚ repository   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
             â”‚
             â–¼
           Files
```

Main project areas:

```text
omni_download_manager/
â”œâ”€â”€ core/        Domain models, states, errors and file categories
â”œâ”€â”€ engine/      Adaptive HTTP download strategies, segments, speed and filenames
â”œâ”€â”€ storage/     SQLite repository and migrations
â”œâ”€â”€ config/      Paths and application settings
â”œâ”€â”€ services/    Queue, scheduling, retries, workers and orchestration
â”œâ”€â”€ ui/          PySide6 interface, dialogs, views and themes
â””â”€â”€ utils/       Formatting, validation, logging and OS integration
```

The download engine is separated from the UI and persistence layers. Worker threads perform downloads independently, while Qt events/signals carry state changes back to the GUI layer.

---

## ðŸ’¾ Data & Storage

On Windows, the default application-data directory is:

```text
%APPDATA%\Omni Download Manager\
```

Typical contents:

```text
settings.json
downloads.db
logs/
  omni_download_manager.log
```

The location can be overridden with:

```text
ODM_DATA_DIR
```

The project also maintains compatibility with the older `FETCHLY_DATA_DIR` data location during migration.

---

## ðŸ”¨ Build a Windows Release

PyInstaller configuration is provided in the project.

```bat
python -m pip install pyinstaller
python scripts\make_icon.py
pyinstaller --noconfirm packaging\omni_download_manager.spec
```

The build produces a folder-based portable application containing the executable and `_internal` directory. The complete output folder should be packaged for distribution.

### Build the Setup installer

With [Inno Setup 6 or 7](https://jrsoftware.org/isinfo.php) installed:

```bat
"C:\Program Files\Inno Setup 7\ISCC.exe" "omni download manager v 0.2.0.iss"
```

The script reads `dist\Omni Download Manager\*` (relative to the repository root, so it works from any checkout) and writes `installer\Omni-Download-Manager-Setup.exe`.

> `dist\` and `installer\` are build output and are excluded from version control. Rebuild the portable folder before compiling the installer so the package contains the current code.

---

## âš ï¸ Current Limitations

The project is intentionally focused on its current core feature set. The following are **not implemented yet**:

- FTP downloads.
- BitTorrent support.
- Browser integration for automatically capturing download links.
- Account login, cookies, or configurable custom request headers.
- A dedicated manual-proxy configuration interface; the current option uses the system proxy.
- Resuming a download from a server that refuses HTTP `Range` requests.

---

## ðŸ—ºï¸ Project Status

**Omni Download Manager 0.2.0** adds adaptive multi-connection downloads and a redesigned desktop interface to the existing download workflow.

The architecture is deliberately modular so future versions can extend the transfer layer and application features without requiring a complete rewrite of the UI or storage system.

---

## ðŸ¤ Contributing

Contributions, bug reports, and ideas are welcome. When submitting a change, please keep the existing modular architecture in mind and run the test suite before opening a pull request.

---

## ðŸ“„ License

No license has been selected or included yet. Until a license is added, reuse,
modification, and redistribution terms are not defined. Add a license before
describing the project as open source or redistributing it.

---

# ðŸ‡®ðŸ‡· ÙØ§Ø±Ø³ÛŒ

## Ù…Ø¹Ø±ÙÛŒ

**Omni Download Manager (ODM)** ÛŒÚ© Ø¯Ø§Ù†Ù„ÙˆØ¯Ù…Ù†ÛŒØ¬Ø± Ø¯Ø³Ú©ØªØ§Ù¾ Ø§Ø³Øª Ú©Ù‡ Ø¨Ø§ **Python Ùˆ PySide6** Ø³Ø§Ø®ØªÙ‡ Ø´Ø¯Ù‡ Ùˆ ØªÙ…Ø±Ú©Ø² Ø¢Ù† Ø±ÙˆÛŒ ÛŒÚ© ØªØ¬Ø±Ø¨Ù‡Ù” Ù‚Ø§Ø¨Ù„â€ŒØ§Ø¹ØªÙ…Ø§Ø¯ Ø¨Ø±Ø§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§ÛŒ HTTP/HTTPS Ø§Ø³Øª.

Ø§ÛŒÙ† Ù¾Ø±ÙˆÚ˜Ù‡ Ø¹Ù„Ø§ÙˆÙ‡ Ø¨Ø± Ù‡Ø³ØªÙ‡Ù” Ø¯Ø§Ù†Ù„ÙˆØ¯ØŒ Ø§Ù…Ú©Ø§Ù†Ø§ØªÛŒ Ù…Ø«Ù„ Ù…Ø¯ÛŒØ±ÛŒØª ØµÙØŒ Ù…Ú©Ø« Ùˆ Ø§Ø¯Ø§Ù…Ù‡ØŒ ØªÙ„Ø§Ø´ Ù…Ø¬Ø¯Ø¯ØŒ Ø²Ù…Ø§Ù†â€ŒØ¨Ù†Ø¯ÛŒØŒ Ù…Ø­Ø¯ÙˆØ¯ÛŒØª Ø³Ø±Ø¹ØªØŒ Ø¬Ø³Øªâ€ŒÙˆØ¬ÙˆØŒ Ù…Ø±ØªØ¨â€ŒØ³Ø§Ø²ÛŒØŒ ÙÛŒÙ„ØªØ± Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒØŒ ØªØ§Ø±ÛŒØ®Ú†Ù‡Ù” Ø¯Ø§Ù†Ù„ÙˆØ¯ØŒ Ø§Ø¹Ù„Ø§Ù† Ùˆ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø±ÙˆØ´Ù†/ØªÛŒØ±Ù‡ Ø±Ø§ Ø§Ø±Ø§Ø¦Ù‡ Ù…ÛŒâ€ŒØ¯Ù‡Ø¯.

Ù…Ø¹Ù…Ø§Ø±ÛŒ Ø¨Ø±Ù†Ø§Ù…Ù‡ Ø¨Ù‡â€ŒØµÙˆØ±Øª Ù…Ø§Ú˜ÙˆÙ„Ø§Ø± Ø·Ø±Ø§Ø­ÛŒ Ø´Ø¯Ù‡ ØªØ§ Ø¨ØªÙˆØ§Ù† Ø§Ù…Ú©Ø§Ù†Ø§Øª Ø¢ÛŒÙ†Ø¯Ù‡ Ø±Ø§ Ø¨Ø¯ÙˆÙ† ÙˆØ§Ø¨Ø³ØªÚ¯ÛŒ Ø´Ø¯ÛŒØ¯ Ø¨ÛŒÙ† Ù…ÙˆØªÙˆØ± Ø¯Ø§Ù†Ù„ÙˆØ¯ØŒ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ùˆ Ø°Ø®ÛŒØ±Ù‡â€ŒØ³Ø§Ø²ÛŒ Ø§Ø¶Ø§ÙÙ‡ Ú©Ø±Ø¯.

## âœ¨ Ø§Ù…Ú©Ø§Ù†Ø§Øª Ø§ØµÙ„ÛŒ

- Ø¯Ø§Ù†Ù„ÙˆØ¯ ÙØ§ÛŒÙ„ Ø§Ø² Ù„ÛŒÙ†Ú©â€ŒÙ‡Ø§ÛŒ `HTTP` Ùˆ `HTTPS`.
- Ø¯Ø§Ù†Ù„ÙˆØ¯ Ú†Ù†Ø¯Ø§ØªØµØ§Ù„ÛŒ Ø®ÙˆØ¯Ú©Ø§Ø± ØªØ§ **Û´ Ø§ØªØµØ§Ù„** Ø¨Ø±Ø§ÛŒ ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ù…Ù†Ø§Ø³Ø¨ Ùˆ Ø³Ø±ÙˆØ±Ù‡Ø§ÛŒ Ø¯Ø§Ø±Ø§ÛŒ Ù¾Ø§Ø³Ø® Ù…Ø¹ØªØ¨Ø± `Range`Ø› Ø¯Ø± ØºÛŒØ± Ø§ÛŒÙ† ØµÙˆØ±Øª Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø§ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ù…Ø¹Ù…ÙˆÙ„ÛŒ.
- Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø¬Ø±ÛŒØ§Ù†ÛŒ Ùˆ Ú©Ù…â€ŒÙ…ØµØ±Ù Ø§Ø² Ù†Ø¸Ø± Ø­Ø§ÙØ¸Ù‡.
- Ù…Ø­Ø§Ø³Ø¨Ù‡Ù” Ù¾ÛŒØ´Ø±ÙØª Ú†Ù†Ø¯Ø¨Ø®Ø´ÛŒ Ø¨Ø± Ø§Ø³Ø§Ø³ Ù…Ø¬Ù…ÙˆØ¹ Ø¨Ø§ÛŒØªâ€ŒÙ‡Ø§ Ùˆ Ù†Ú¯Ù‡Ø¯Ø§Ø±ÛŒ ÙˆØ¶Ø¹ÛŒØª Ø¨Ø®Ø´â€ŒÙ‡Ø§ Ø¨Ø±Ø§ÛŒ Ø§Ø¯Ø§Ù…Ù‡Ù” Ø§Ù…Ù† Ù¾Ø³ Ø§Ø² Ù…Ú©Ø« ÛŒØ§ Ø§Ø¬Ø±Ø§ÛŒ Ø¯ÙˆØ¨Ø§Ø±Ù‡.
- Ù†Ù…Ø§ÛŒØ´ Ø¯Ø±ØµØ¯ Ù¾ÛŒØ´Ø±ÙØªØŒ Ø­Ø¬Ù…ØŒ Ø³Ø±Ø¹Øª Ùˆ Ø²Ù…Ø§Ù† Ø¨Ø§Ù‚ÛŒâ€ŒÙ…Ø§Ù†Ø¯Ù‡ Ø¯Ø± ØµÙˆØ±Øª Ù…Ø´Ø®Øµ Ø¨ÙˆØ¯Ù† Ø­Ø¬Ù… ÙØ§ÛŒÙ„.
- Ù…Ú©Ø« Ùˆ Ø§Ø¯Ø§Ù…Ù‡Ù” Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø¯Ø± ØµÙˆØ±Øª Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ø³Ø±ÙˆØ± Ø§Ø² HTTP `Range`.
- Ù†Ú¯Ù‡Ø¯Ø§Ø±ÛŒ ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ù†Ø§Ù‚Øµ Ø¨Ø§ Ù¾Ø³ÙˆÙ†Ø¯ `.part`.
- Ø­Ø¯Ø§Ú©Ø«Ø± **Û³ ØªÙ„Ø§Ø´ Ù…Ø¬Ø¯Ø¯ Ø®ÙˆØ¯Ú©Ø§Ø±** Ø¨Ø±Ø§ÛŒ Ø®Ø·Ø§Ù‡Ø§ÛŒ Ù…ÙˆÙ‚Øª.
- ØµÙ FIFO Ø¨Ø§ Ø­Ø¯Ø§Ú©Ø«Ø± **Ûµ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ù‡Ù…â€ŒØ²Ù…Ø§Ù†**.
- Ù…Ø­Ø¯ÙˆØ¯ÛŒØª Ø³Ø±Ø¹Øª Ú©Ù„ÛŒ Ùˆ Ù…Ø´ØªØ±Ú© Ø¨ÛŒÙ† Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§.
- Ø²Ù…Ø§Ù†â€ŒØ¨Ù†Ø¯ÛŒ ÛŒÚ©â€ŒØ¨Ø§Ø±Ù‡Ù” Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø¨Ø± Ø§Ø³Ø§Ø³ Ø²Ù…Ø§Ù† Ù…Ø­Ù„ÛŒ.
- Ø¨Ø§Ø²ÛŒØ§Ø¨ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§ÛŒ Ù†Ø§ØªÙ…Ø§Ù… Ù¾Ø³ Ø§Ø² Ø§Ø¬Ø±Ø§ÛŒ Ù…Ø¬Ø¯Ø¯ Ø¨Ø±Ù†Ø§Ù…Ù‡.
- Ø¬Ø³Øªâ€ŒÙˆØ¬Ùˆ Ø¨Ø± Ø§Ø³Ø§Ø³ Ù†Ø§Ù… ÙØ§ÛŒÙ„ ÛŒØ§ URL.
- Ù…Ø±ØªØ¨â€ŒØ³Ø§Ø²ÛŒ Ø¨Ø± Ø§Ø³Ø§Ø³ Ø¬Ø¯ÛŒØ¯ØªØ±ÛŒÙ†ØŒ Ù‚Ø¯ÛŒÙ…ÛŒâ€ŒØªØ±ÛŒÙ†ØŒ Ù†Ø§Ù… Ùˆ Ø­Ø¬Ù….
- ÙÛŒÙ„ØªØ± Ø¯Ø³ØªÙ‡â€ŒÙ‡Ø§ÛŒ ÙØ§ÛŒÙ„ Ø´Ø§Ù…Ù„ Ø¢Ø±Ø´ÛŒÙˆØŒ ÙˆÛŒØ¯Ø¦ÙˆØŒ ØµÙˆØªØŒ ØªØµÙˆÛŒØ±ØŒ Ø³Ù†Ø¯ØŒ Ø¨Ø±Ù†Ø§Ù…Ù‡ Ùˆ Ø³Ø§ÛŒØ± ÙØ§ÛŒÙ„â€ŒÙ‡Ø§.
- Ø§Ù†ØªØ®Ø§Ø¨ Ú†Ù†Ø¯ØªØ§ÛŒÛŒ Ùˆ Ø¹Ù…Ù„ÛŒØ§Øª Ú¯Ø±ÙˆÙ‡ÛŒ.
- Ø¨Ø§Ø²Ú©Ø±Ø¯Ù† ÙØ§ÛŒÙ„ ÛŒØ§ Ù¾ÙˆØ´Ù‡Ù” Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ú©Ù¾ÛŒ Ù„ÛŒÙ†Ú©.
- Ø§Ø¹Ù„Ø§Ù† ØªÚ©Ù…ÛŒÙ„ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø¯Ø± ÙˆÛŒÙ†Ø¯ÙˆØ².
- Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ø§Ø² Ù¾Ø±ÙˆÚ©Ø³ÛŒ Ø³ÛŒØ³ØªÙ….
- ØªÙ… Ø±ÙˆØ´Ù† Ùˆ ØªØ§Ø±ÛŒÚ© Ø¨Ø§ Ø·Ø±Ø§Ø­ÛŒ Ù…Ø¯Ø±Ù†.
- Ø°Ø®ÛŒØ±Ù‡Ù” ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ùˆ ØªØ§Ø±ÛŒØ®Ú†Ù‡Ù” Ø¯Ø§Ù†Ù„ÙˆØ¯.

## ðŸ–¥ï¸ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ùˆ ØªØµØ§ÙˆÛŒØ±

Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø¨Ø§ **PySide6 / Qt 6** Ø³Ø§Ø®ØªÙ‡ Ø´Ø¯Ù‡ Ø§Ø³Øª. Ø¯Ø± Ù†Ø³Ø®Ù‡Ù” `0.2.0`ØŒ Ú†ÛŒØ¯Ù…Ø§Ù† Ø§Ø¨Ø²Ø§Ø±Ù‡Ø§ Ø¨Ø§Ø²Ø·Ø±Ø§Ø­ÛŒ Ø´Ø¯Ù‡ Ùˆ Ù¾ÛŒÙ…Ø§ÛŒØ´ ØµÙØ­Ø§Øª Ø¨Ù‡ Ù†ÙˆØ§Ø± Ù¾Ø§ÛŒÛŒÙ†ÛŒ Ù…Ù†ØªÙ‚Ù„ Ø´Ø¯Ù‡ Ø§Ø³Øª.

<!-- Ø§Ø³Ú©Ø±ÛŒÙ†â€ŒØ´Ø§Øªâ€ŒÙ‡Ø§ Ù†Ø¨Ø§ÛŒØ¯ Ù†Ø§Ù… Ú©Ø§Ø±Ø¨Ø±ÛŒ ÙˆÛŒÙ†Ø¯ÙˆØ²ØŒ Ù…Ø³ÛŒØ±Ù‡Ø§ÛŒ Ø´Ø®ØµÛŒ ÛŒØ§ Ù†Ø§Ù… ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ø®ØµÙˆØµÛŒ Ø±Ø§ Ù†Ù…Ø§ÛŒØ´ Ø¯Ù‡Ù†Ø¯. -->
<p align="center">
  <strong>Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ù‚Ø¨Ù„ÛŒ</strong>
</p>
<p align="center">
  <img src="assets/ui-before.png" alt="Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ù‚Ø¨Ù„ÛŒ Omni Download Manager" width="900">
</p>

<p align="center">
  <strong>Ø±Ø§Ø¨Ø· Ø¨Ø§Ø²Ø·Ø±Ø§Ø­ÛŒâ€ŒØ´Ø¯Ù‡ Â· Ù†Ø³Ø®Ù‡Ù” 0.2.0</strong>
</p>
<p align="center">
  <img src="assets/ui-v0.2.0.png" alt="Ø±Ø§Ø¨Ø· Ø¨Ø§Ø²Ø·Ø±Ø§Ø­ÛŒâ€ŒØ´Ø¯Ù‡ Omni Download Manager Ø¯Ø± Ù†Ø³Ø®Ù‡ 0.2.0" width="900">
</p>

## ðŸš€ Ø§Ø¬Ø±Ø§ÛŒ Ù¾Ø±ÙˆÚ˜Ù‡ Ø¯Ø± ÙˆÛŒÙ†Ø¯ÙˆØ²

Ø³Ø§Ø¯Ù‡â€ŒØªØ±ÛŒÙ† Ø±ÙˆØ´:

```bat
run.bat
```

ÛŒØ§ Ø¨Ù‡â€ŒØµÙˆØ±Øª Ø¯Ø³ØªÛŒ:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Ø±ÙˆØ´ Ø¬Ø§ÛŒÚ¯Ø²ÛŒÙ†:

```bat
python -m omni_download_manager
```

## ðŸ“¦ Ù†Ø³Ø®Ù‡Ù” Portable

Ù†Ø³Ø®Ù‡Ù” ÙˆÛŒÙ†Ø¯ÙˆØ²ÛŒ Ø¨Ù‡ Ø¯Ùˆ Ø´Ú©Ù„ ØªÙˆØ²ÛŒØ¹ Ù…ÛŒâ€ŒØ´ÙˆØ¯: Ù¾ÙˆØ´Ù‡Ù” Portable Ùˆ Ù†ØµØ¨â€ŒÚ©Ù†Ù†Ø¯Ù‡Ù” Setup.

### Portable

Ø¨Ø¹Ø¯ Ø§Ø² Ø§Ø³ØªØ®Ø±Ø§Ø¬ ZIPØŒ ÙØ§ÛŒÙ„ Ø²ÛŒØ± Ø±Ø§ Ø§Ø¬Ø±Ø§ Ú©Ù†ÛŒØ¯:

```text
Omni Download Manager.exe
```

Ù¾ÙˆØ´Ù‡Ù” `_internal` Ø¨Ø§ÛŒØ¯ Ø¯Ø± Ú©Ù†Ø§Ø± ÙØ§ÛŒÙ„ EXE Ø¨Ø§Ù‚ÛŒ Ø¨Ù…Ø§Ù†Ø¯.

### Ù†ØµØ¨â€ŒÚ©Ù†Ù†Ø¯Ù‡Ù” Setup

Ø§Ø³Ú©Ø±ÛŒÙ¾Øª Inno Setup Ø¨Ø§ Ù†Ø§Ù… `omni download manager v 0.2.0.iss` Ù‡Ù…Ø§Ù† Ù¾ÙˆØ´Ù‡ Ø±Ø§ Ø¨Ù‡ ÙØ§ÛŒÙ„ `installer\Omni-Download-Manager-Setup.exe` ØªØ¨Ø¯ÛŒÙ„ Ù…ÛŒâ€ŒÚ©Ù†Ø¯. Ø¬Ø²Ø¦ÛŒØ§Øª Ø¯Ø± Ø¨Ø®Ø´ [Ø³Ø§Ø®Øª Ù†Ø³Ø®Ù‡Ù” ÙˆÛŒÙ†Ø¯ÙˆØ²](#-Ø³Ø§Ø®Øª-Ù†Ø³Ø®Ù‡Ù”-ÙˆÛŒÙ†Ø¯ÙˆØ²) Ø¢Ù…Ø¯Ù‡ Ø§Ø³Øª.

## ðŸ§ª ØªØ³Øªâ€ŒÙ‡Ø§

Ø¨Ø±Ø§ÛŒ Ø§Ø¬Ø±Ø§ÛŒ ØªØ³Øªâ€ŒÙ‡Ø§:

```bat
python -m unittest discover -s tests -t .
```

Ø¯Ø± Ø¢Ø®Ø±ÛŒÙ† Ø§Ø¬Ø±Ø§ÛŒ ØªØ£ÛŒÛŒØ¯Ø´Ø¯Ù‡ØŒ **Ù‡Ø± Û±Û´Û² ØªØ³Øª Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ù¾Ø§Ø³ Ø´Ø¯Ù‡â€ŒØ§Ù†Ø¯**. ØªØ³Øªâ€ŒÙ‡Ø§ ØªØ´Ø®ÛŒØµ Ùˆ fallback Ø¯Ø± HTTP RangeØŒ ØµØ­Øª Ø¯Ø§Ù†Ù„ÙˆØ¯ Ú†Ù†Ø¯Ø¨Ø®Ø´ÛŒ Ùˆ fallback Ø¢Ù†ØŒ Ù…Ú©Ø«/Ø§Ø¯Ø§Ù…Ù‡ØŒ ØµÙØŒ retryØŒ Ø²Ù…Ø§Ù†â€ŒØ¨Ù†Ø¯ÛŒØŒ Ø¨Ø§Ø²ÛŒØ§Ø¨ÛŒØŒ Ø§Ù†ØªØ´Ø§Ø± Ø±ÙˆÛŒØ¯Ø§Ø¯Ù‡Ø§ Ø®Ø§Ø±Ø¬ Ø§Ø² Ù‚ÙÙ„ Ù…Ø¯ÛŒØ±ØŒ ÙÛŒÙ„ØªØ±ØŒ Ø¬Ø³Øªâ€ŒÙˆØ¬ÙˆØŒ Ø°Ø®ÛŒØ±Ù‡â€ŒØ³Ø§Ø²ÛŒØŒ Ø±ÙØªØ§Ø± Ø§Ù†ØªØ®Ø§Ø¨ Ø¯Ø± ÙÙ‡Ø±Ø³Øª Ùˆ Ù‚Ø§Ø¨Ù„ÛŒØªâ€ŒÙ‡Ø§ÛŒ Ù…Ø±ØªØ¨Ø· Ø¨Ø§ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø±Ø§ Ø¨Ø±Ø±Ø³ÛŒ Ù…ÛŒâ€ŒÚ©Ù†Ù†Ø¯.

ØªØ³Øªâ€ŒÙ‡Ø§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø§Ø² ÛŒÚ© HTTP server Ù…Ø­Ù„ÛŒ Ø§Ø³ØªÙØ§Ø¯Ù‡ Ù…ÛŒâ€ŒÚ©Ù†Ù†Ø¯ Ùˆ Ø¨Ù‡ Ø³Ø±ÙˆÛŒØ³ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø®Ø§Ø±Ø¬ÛŒ ÙˆØ§Ø¨Ø³ØªÙ‡ Ù†ÛŒØ³ØªÙ†Ø¯.

## ðŸ—ï¸ Ù…Ø¹Ù…Ø§Ø±ÛŒ

Ù¾Ø±ÙˆÚ˜Ù‡ Ø¨Ù‡ Ø¨Ø®Ø´â€ŒÙ‡Ø§ÛŒ Ù…Ø³ØªÙ‚Ù„ÛŒ ØªÙ‚Ø³ÛŒÙ… Ø´Ø¯Ù‡ Ø§Ø³Øª:

- `core` â€” Ù…Ø¯Ù„â€ŒÙ‡Ø§ØŒ ÙˆØ¶Ø¹ÛŒØªâ€ŒÙ‡Ø§ØŒ Ø®Ø·Ø§Ù‡Ø§ Ùˆ Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒ ÙØ§ÛŒÙ„â€ŒÙ‡Ø§.
- `engine` â€” Ø±Ø§Ù‡Ø¨Ø±Ø¯Ù‡Ø§ÛŒ ØªØ·Ø¨ÛŒÙ‚ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ HTTP ØªÚ©â€ŒØ§ØªØµØ§Ù„ÛŒ/Ú†Ù†Ø¯Ø¨Ø®Ø´ÛŒØŒ segmentÙ‡Ø§ØŒ Ø§Ù†Ø¯Ø§Ø²Ù‡â€ŒÚ¯ÛŒØ±ÛŒ Ø³Ø±Ø¹Øª Ùˆ Ù…Ø¯ÛŒØ±ÛŒØª Ù†Ø§Ù… ÙØ§ÛŒÙ„.
- `storage` â€” SQLite Ùˆ migrationÙ‡Ø§.
- `config` â€” Ù…Ø³ÛŒØ±Ù‡Ø§ Ùˆ ØªÙ†Ø¸ÛŒÙ…Ø§Øª.
- `services` â€” ØµÙØŒ Ø²Ù…Ø§Ù†â€ŒØ¨Ù†Ø¯ÛŒØŒ retryØŒ workerÙ‡Ø§ Ùˆ Ù‡Ù…Ø§Ù‡Ù†Ú¯ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§.
- `ui` â€” Ø±Ø§Ø¨Ø· PySide6ØŒ Ø¯ÛŒØ§Ù„ÙˆÚ¯â€ŒÙ‡Ø§ØŒ ØµÙØ­Ø§Øª Ùˆ ØªÙ…â€ŒÙ‡Ø§.
- `utils` â€” Ø§Ø¨Ø²Ø§Ø±Ù‡Ø§ÛŒ Ú©Ù…Ú©ÛŒØŒ Ù„Ø§Ú¯ØŒ Ø§Ø¹ØªØ¨Ø§Ø±Ø³Ù†Ø¬ÛŒ Ùˆ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³ÛŒØ³ØªÙ…â€ŒØ¹Ø§Ù…Ù„.

Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§ Ø¯Ø± worker thread Ø§Ù†Ø¬Ø§Ù… Ù…ÛŒâ€ŒØ´ÙˆÙ†Ø¯ Ùˆ ØªØºÛŒÛŒØ±Ø§Øª ÙˆØ¶Ø¹ÛŒØª Ø§Ø² Ø·Ø±ÛŒÙ‚ Ø±ÙˆÛŒØ¯Ø§Ø¯Ù‡Ø§ Ùˆ Ø³ÛŒÚ¯Ù†Ø§Ù„â€ŒÙ‡Ø§ÛŒ Qt Ø¨Ù‡ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ù…Ù†ØªÙ‚Ù„ Ù…ÛŒâ€ŒØ´ÙˆÙ†Ø¯.

## ðŸ’¾ Ø°Ø®ÛŒØ±Ù‡â€ŒØ³Ø§Ø²ÛŒ Ø§Ø·Ù„Ø§Ø¹Ø§Øª

Ø¯Ø± ÙˆÛŒÙ†Ø¯ÙˆØ²ØŒ Ù…Ø³ÛŒØ± Ù¾ÛŒØ´â€ŒÙØ±Ø¶ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¨Ø±Ù†Ø§Ù…Ù‡:

```text
%APPDATA%\Omni Download Manager\
```

Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø§ØµÙ„ÛŒ Ø´Ø§Ù…Ù„ Ù…ÙˆØ§Ø±Ø¯ Ø²ÛŒØ± Ø§Ø³Øª:

```text
settings.json
downloads.db
logs/
```

Ù…Ø³ÛŒØ± Ø°Ø®ÛŒØ±Ù‡â€ŒØ³Ø§Ø²ÛŒ Ø±Ø§ Ù…ÛŒâ€ŒØªÙˆØ§Ù† Ø¨Ø§ Ù…ØªØºÛŒØ± Ø²ÛŒØ± ØªØºÛŒÛŒØ± Ø¯Ø§Ø¯:

```text
ODM_DATA_DIR
```

Ø³Ø§Ø²Ú¯Ø§Ø±ÛŒ Ø¨Ø§ Ù…Ø³ÛŒØ± Ù‚Ø¯ÛŒÙ…ÛŒ `FETCHLY_DATA_DIR` Ù†ÛŒØ² Ø¨Ø±Ø§ÛŒ Ù…Ù‡Ø§Ø¬Ø±Øª Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¯Ø± Ù†Ø¸Ø± Ú¯Ø±ÙØªÙ‡ Ø´Ø¯Ù‡ Ø§Ø³Øª.

## ðŸ”¨ Ø³Ø§Ø®Øª Ù†Ø³Ø®Ù‡Ù” ÙˆÛŒÙ†Ø¯ÙˆØ²

Ø¨Ø±Ø§ÛŒ Ø³Ø§Ø®Øª Ù†Ø³Ø®Ù‡Ù” Portable Ø¨Ø§ PyInstaller:

```bat
python -m pip install pyinstaller
python scripts\make_icon.py
pyinstaller --noconfirm packaging\omni_download_manager.spec
```

Ø®Ø±ÙˆØ¬ÛŒ Ø´Ø§Ù…Ù„ ÙØ§ÛŒÙ„ Ø§Ø¬Ø±Ø§ÛŒÛŒ Ùˆ Ù¾ÙˆØ´Ù‡Ù” `_internal` Ø§Ø³Øª Ùˆ Ø¨Ø±Ø§ÛŒ ØªÙˆØ²ÛŒØ¹ Ø¨Ø§ÛŒØ¯ Ú©Ù„ Ù¾ÙˆØ´Ù‡ Ø¨Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒ Ø´ÙˆØ¯.

### Ø³Ø§Ø®Øª Ù†ØµØ¨â€ŒÚ©Ù†Ù†Ø¯Ù‡Ù” Setup

Ø¨Ø§ Ù†ØµØ¨ Ø¨ÙˆØ¯Ù† [Inno Setup Ù†Ø³Ø®Ù‡Ù” Û¶ ÛŒØ§ Û·](https://jrsoftware.org/isinfo.php):

```bat
"C:\Program Files\Inno Setup 7\ISCC.exe" "omni download manager v 0.2.0.iss"
```

Ø§Ø³Ú©Ø±ÛŒÙ¾Øª Ù…Ø­ØªÙˆØ§ÛŒ `dist\Omni Download Manager\*` Ø±Ø§ Ù…ÛŒâ€ŒØ®ÙˆØ§Ù†Ø¯ (Ù…Ø³ÛŒØ±Ù‡Ø§ Ù†Ø³Ø¨ÛŒ Ù‡Ø³ØªÙ†Ø¯ Ùˆ Ø§Ø² Ù‡Ø± checkout Ú©Ø§Ø± Ù…ÛŒâ€ŒÚ©Ù†Ù†Ø¯) Ùˆ Ø®Ø±ÙˆØ¬ÛŒ Ø±Ø§ Ø¯Ø± `installer\Omni-Download-Manager-Setup.exe` Ù…ÛŒâ€ŒÙ†ÙˆÛŒØ³Ø¯.

> Ù¾ÙˆØ´Ù‡â€ŒÙ‡Ø§ÛŒ `dist\` Ùˆ `installer\` Ø®Ø±ÙˆØ¬ÛŒ build Ù‡Ø³ØªÙ†Ø¯ Ùˆ Ø¯Ø± Ú©Ù†ØªØ±Ù„ Ù†Ø³Ø®Ù‡ Ø«Ø¨Øª Ù†Ù…ÛŒâ€ŒØ´ÙˆÙ†Ø¯. Ù¾ÛŒØ´ Ø§Ø² Ø³Ø§Ø®Øª Ù†ØµØ¨â€ŒÚ©Ù†Ù†Ø¯Ù‡ØŒ Ù¾ÙˆØ´Ù‡Ù” Portable Ø±Ø§ Ø¯ÙˆØ¨Ø§Ø±Ù‡ Ø¨Ø³Ø§Ø²ÛŒØ¯ ØªØ§ Ø¨Ø³ØªÙ‡ Ø´Ø§Ù…Ù„ Ú©Ø¯ Ø¨Ù‡â€ŒØ±ÙˆØ² Ø¨Ø§Ø´Ø¯.

## âš ï¸ Ù…Ø­Ø¯ÙˆØ¯ÛŒØªâ€ŒÙ‡Ø§ÛŒ ÙØ¹Ù„ÛŒ

Ø¯Ø± Ù†Ø³Ø®Ù‡Ù” `0.2.0` Ù…ÙˆØ§Ø±Ø¯ Ø²ÛŒØ± Ù‡Ù†ÙˆØ² Ù¾ÛŒØ§Ø¯Ù‡â€ŒØ³Ø§Ø²ÛŒ Ù†Ø´Ø¯Ù‡â€ŒØ§Ù†Ø¯:

- Ø¯Ø§Ù†Ù„ÙˆØ¯ FTP.
- Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ø§Ø² BitTorrent.
- Ø§ØªØµØ§Ù„ Ù…Ø³ØªÙ‚ÛŒÙ… Ø¨Ù‡ Ù…Ø±ÙˆØ±Ú¯Ø± Ø¨Ø±Ø§ÛŒ Ø¯Ø±ÛŒØ§ÙØª Ø®ÙˆØ¯Ú©Ø§Ø± Ù„ÛŒÙ†Ú© Ø¯Ø§Ù†Ù„ÙˆØ¯.
- ÙˆØ±ÙˆØ¯ Ø¨Ù‡ Ø­Ø³Ø§Ø¨ØŒ Cookie Ùˆ Header Ø³ÙØ§Ø±Ø´ÛŒ Ù‚Ø§Ø¨Ù„ ØªÙ†Ø¸ÛŒÙ….
- Ø±Ø§Ø¨Ø· Ù…Ø³ØªÙ‚Ù„ Ø¨Ø±Ø§ÛŒ ØªÙ†Ø¸ÛŒÙ… Ø¯Ø³ØªÛŒ Proxy.
- Ø§Ø¯Ø§Ù…Ù‡Ù” Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø§Ø² Ø³Ø±ÙˆØ±ÛŒ Ú©Ù‡ Ø§Ø² HTTP `Range` Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ù†Ù…ÛŒâ€ŒÚ©Ù†Ø¯.

## ðŸ“„ Ù…Ø¬ÙˆØ²

ÙØ¹Ù„Ø§Ù‹ Ù…Ø¬ÙˆØ²ÛŒ Ø¨Ø±Ø§ÛŒ Ù¾Ø±ÙˆÚ˜Ù‡ Ø§Ù†ØªØ®Ø§Ø¨ ÛŒØ§ Ø¨Ù‡ Ù…Ø®Ø²Ù† Ø§Ø¶Ø§ÙÙ‡ Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª. ØªØ§ Ø²Ù…Ø§Ù† Ø§Ø¶Ø§ÙÙ‡â€ŒØ´Ø¯Ù† ÙØ§ÛŒÙ„
Ù…Ø¬ÙˆØ²ØŒ Ø´Ø±Ø§ÛŒØ· Ø§Ø³ØªÙØ§Ø¯Ù‡Ù” Ù…Ø¬Ø¯Ø¯ØŒ ØªØºÛŒÛŒØ± Ùˆ Ø¨Ø§Ø²ØªÙˆØ²ÛŒØ¹ Ù…Ø´Ø®Øµ Ù†ÛŒØ³Øª. Ù¾ÛŒØ´ Ø§Ø² Ù…Ø¹Ø±ÙÛŒ Ù¾Ø±ÙˆÚ˜Ù‡ Ø¨Ù‡â€ŒØ¹Ù†ÙˆØ§Ù†
Ù…ØªÙ†â€ŒØ¨Ø§Ø² ÛŒØ§ Ø¨Ø§Ø²ØªÙˆØ²ÛŒØ¹ Ø¢Ù†ØŒ ÛŒÚ© Ù…Ø¬ÙˆØ² Ø§Ù†ØªØ®Ø§Ø¨ Ùˆ Ø§Ø¶Ø§ÙÙ‡ Ú©Ù†ÛŒØ¯.

## ðŸ—ºï¸ ÙˆØ¶Ø¹ÛŒØª Ù¾Ø±ÙˆÚ˜Ù‡

Ù†Ø³Ø®Ù‡Ù” **0.2.0** Ø¨Ø§ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ú†Ù†Ø¯Ø§ØªØµØ§Ù„ÛŒ ØªØ·Ø¨ÛŒÙ‚ÛŒ Ùˆ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø¨Ø§Ø²Ø·Ø±Ø§Ø­ÛŒâ€ŒØ´Ø¯Ù‡ØŒ Ø¨Ø± Ù¾Ø§ÛŒÙ‡Ù” Ù‡Ø³ØªÙ‡Ù” Ù¾Ø§ÛŒØ¯Ø§Ø± Ø¯Ø§Ù†Ù„ÙˆØ¯ØŒ Ù…Ø¯ÛŒØ±ÛŒØª ØµÙØŒ Ø²Ù…Ø§Ù†â€ŒØ¨Ù†Ø¯ÛŒ Ùˆ ØªØ§Ø±ÛŒØ®Ú†Ù‡Ù” Ø¯Ø§Ø¦Ù…ÛŒ Ø³Ø§Ø®ØªÙ‡ Ø´Ø¯Ù‡ Ø§Ø³Øª.

Ø³Ø§Ø®ØªØ§Ø± Ù…Ø§Ú˜ÙˆÙ„Ø§Ø± Ù¾Ø±ÙˆÚ˜Ù‡ Ø§Ø¬Ø§Ø²Ù‡ Ù…ÛŒâ€ŒØ¯Ù‡Ø¯ Ø¯Ø± Ù†Ø³Ø®Ù‡â€ŒÙ‡Ø§ÛŒ Ø¨Ø¹Ø¯ÛŒ Ø§Ù…Ú©Ø§Ù†Ø§Øª Ø¨ÛŒØ´ØªØ±ÛŒ Ø¨Ù‡ Ù…ÙˆØªÙˆØ± Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ø®ÙˆØ¯ Ø¨Ø±Ù†Ø§Ù…Ù‡ Ø§Ø¶Ø§ÙÙ‡ Ø´ÙˆØ¯ØŒ Ø¨Ø¯ÙˆÙ† Ø§ÛŒÙ†Ú©Ù‡ Ù†ÛŒØ§Ø² Ø¨Ù‡ Ø¨Ø§Ø²Ù†ÙˆÛŒØ³ÛŒ Ú©Ø§Ù…Ù„ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ ÛŒØ§ Ø³ÛŒØ³ØªÙ… Ø°Ø®ÛŒØ±Ù‡â€ŒØ³Ø§Ø²ÛŒ Ø¨Ø§Ø´Ø¯.

---

<p align="center">
  <strong>Omni Download Manager Â· v0.2.0</strong><br>
  Built with Python & PySide6 Â· Made for Windows
</p>


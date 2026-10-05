# Omni Download Manager

<p align="center">
  <strong>A modern, lightweight HTTP/HTTPS download manager for Windows.</strong><br>
  <strong>یک دانلودمنیجر مدرن و سبک برای دانلودهای HTTP/HTTPS در ویندوز.</strong>
</p>

<p align="center">
  <b>Version 0.1.0</b> · <b>Python + PySide6</b> · <b>Portable Windows Build</b> · <b>106 Tests Passing</b>
</p>

---

## 🇬🇧 English

### Overview

**Omni Download Manager (ODM)** is a desktop download manager built with **Python and PySide6**. It focuses on a reliable core download workflow while providing queue management, pause/resume, retries, scheduling, speed limiting, search, filtering, history, notifications, and a modern dark/light interface.

The project is designed as a modular foundation that can grow into a more capable download-management application without coupling the download engine tightly to the user interface.

### ✨ Highlights

| | Capability | | Capability |
|---|---|---|---|
| ⚡ | HTTP/HTTPS downloads | 📋 | FIFO queue |
| ⏯️ | Pause & resume | 🔁 | Automatic retry |
| 🚀 | Up to 5 active downloads | 🐢 | Global speed limit |
| 🗓️ | One-time scheduling | 🔎 | Search & sorting |
| 🗂️ | File categories & filters | ☑️ | Bulk actions |
| 💾 | SQLite download history | 🌓 | Dark & light themes |
| 🔔 | Windows completion notifications | 📦 | Portable Windows build |

### Download engine

- HTTP and HTTPS downloads.
- Streaming downloads directly to disk instead of loading the complete file into memory.
- Progress percentage, downloaded/total size, speed, and estimated remaining time when the total size is known.
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
- Multi-selection with `Ctrl` / `Shift`.
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

## 🖼️ Screenshots

> The screenshot gallery will be restored after clean, anonymized screenshots are ready. The current source images contain personal paths and filenames.

---

## 🛠️ Technology

| Area | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | PySide6 / Qt 6 |
| HTTP | `requests` |
| Database | SQLite / `sqlite3` |
| Settings | JSON |
| Packaging | PyInstaller |
| Testing | Python `unittest` |

The runtime dependency set is intentionally small: **PySide6** and **requests** are the main third-party dependencies.

---

## 🚀 Getting Started

### Windows — easiest method

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

## 📦 Portable Windows Version

ODM can be distributed as a portable Windows application.

1. Extract the ZIP package completely.
2. Keep the `_internal` folder next to `Omni Download Manager.exe`.
3. Run `Omni Download Manager.exe`.

> **Important:** the current Windows release is **Portable**, not a traditional Setup/Installer package. Do not separate the executable from `_internal`.

---

## 🧪 Testing

Run the complete test suite with:

```bat
python -m unittest discover -s tests -t .
```

The current verified suite contains **106 passing tests**. Coverage includes download behavior, queue scheduling, pause/cancel/resume, retries, shared speed limiting, scheduled starts, restart recovery, category filtering, system-proxy configuration, search/sorting, bulk actions, persistence, completion notifications, and icon loading.

Download-related tests use a **local HTTP server**, so they do not depend on an external download service.

---

## 🏗️ Architecture

```text
┌───────────────────────────────┐
│        PySide6 / Qt UI        │
└───────────────┬───────────────┘
                │ Qt events/signals
                ▼
┌───────────────────────────────┐
│       Download Manager        │
│ queue · retry · scheduling   │
└───────┬───────────────┬───────┘
        │               │
        ▼               ▼
┌──────────────┐  ┌──────────────┐
│ HTTP Engine  │  │   SQLite     │
│ downloader   │  │ repository   │
└──────┬───────┘  └──────────────┘
       │
       ▼
     Files
```

Main project areas:

```text
omni_download_manager/
├── core/        Domain models, states, errors and file categories
├── engine/      HTTP download engine, speed meter and filename handling
├── storage/     SQLite repository and migrations
├── config/      Paths and application settings
├── services/    Queue, scheduling, retries, workers and orchestration
├── ui/          PySide6 interface, dialogs, views and themes
└── utils/       Formatting, validation, logging and OS integration
```

The download engine is separated from the UI and persistence layers. Worker threads perform downloads independently, while Qt events/signals carry state changes back to the GUI layer.

---

## 💾 Data & Storage

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

## 🔨 Build a Windows Release

PyInstaller configuration is provided in the project.

```bat
python -m pip install pyinstaller
python scripts\make_icon.py
pyinstaller --noconfirm packaging\omni_download_manager.spec
```

The build produces a folder-based portable application containing the executable and `_internal` directory. The complete output folder should be packaged for distribution.

---

## ⚠️ Current Limitations

The project is intentionally focused on its current core feature set. The following are **not implemented yet**:

- FTP downloads.
- BitTorrent support.
- Browser integration for automatically capturing download links.
- Multi-connection / segmented downloads.
- Account login, cookies, or configurable custom request headers.
- A dedicated manual-proxy configuration interface; the current option uses the system proxy.
- Traditional installer/setup packaging.

---

## 🗺️ Project Status

**Omni Download Manager 0.1.0** is an early but functional release focused on a stable download workflow, persistent history, queue management, scheduling, and a polished desktop UI.

The architecture is deliberately modular so future versions can extend the transfer layer and application features without requiring a complete rewrite of the UI or storage system.

---

## 🤝 Contributing

Contributions, bug reports, and ideas are welcome. When submitting a change, please keep the existing modular architecture in mind and run the test suite before opening a pull request.

---

## 📄 License

No license has been selected or included yet. Until a license is added, reuse,
modification, and redistribution terms are not defined. Add a license before
describing the project as open source or redistributing it.

---

# 🇮🇷 فارسی

## معرفی

**Omni Download Manager (ODM)** یک دانلودمنیجر دسکتاپ است که با **Python و PySide6** ساخته شده و تمرکز آن روی یک تجربهٔ قابل‌اعتماد برای دانلودهای HTTP/HTTPS است.

این پروژه علاوه بر هستهٔ دانلود، امکاناتی مثل مدیریت صف، مکث و ادامه، تلاش مجدد، زمان‌بندی، محدودیت سرعت، جست‌وجو، مرتب‌سازی، فیلتر دسته‌بندی، تاریخچهٔ دانلود، اعلان و رابط کاربری روشن/تیره را ارائه می‌دهد.

معماری برنامه به‌صورت ماژولار طراحی شده تا بتوان امکانات آینده را بدون وابستگی شدید بین موتور دانلود، رابط کاربری و ذخیره‌سازی اضافه کرد.

## ✨ امکانات اصلی

- دانلود فایل از لینک‌های `HTTP` و `HTTPS`.
- دانلود جریانی و کم‌مصرف از نظر حافظه.
- نمایش درصد پیشرفت، حجم، سرعت و زمان باقی‌مانده در صورت مشخص بودن حجم فایل.
- مکث و ادامهٔ دانلود در صورت پشتیبانی سرور از HTTP `Range`.
- نگهداری فایل‌های ناقص با پسوند `.part`.
- حداکثر **۳ تلاش مجدد خودکار** برای خطاهای موقت.
- صف FIFO با حداکثر **۵ دانلود هم‌زمان**.
- محدودیت سرعت کلی و مشترک بین دانلودها.
- زمان‌بندی یک‌بارهٔ دانلود بر اساس زمان محلی.
- بازیابی دانلودهای ناتمام پس از اجرای مجدد برنامه.
- جست‌وجو بر اساس نام فایل یا URL.
- مرتب‌سازی بر اساس جدیدترین، قدیمی‌ترین، نام و حجم.
- فیلتر دسته‌های فایل شامل آرشیو، ویدئو، صوت، تصویر، سند، برنامه و سایر فایل‌ها.
- انتخاب چندتایی و عملیات گروهی.
- بازکردن فایل یا پوشهٔ دانلود و کپی لینک.
- اعلان تکمیل دانلود در ویندوز.
- پشتیبانی از پروکسی سیستم.
- تم روشن و تاریک با طراحی مدرن.
- ذخیرهٔ تنظیمات و تاریخچهٔ دانلود.

## 🖥️ رابط کاربری

رابط کاربری با **PySide6 / Qt 6** ساخته شده و شامل صفحات اصلی دانلودها، وضعیت دانلود، جست‌وجو، مرتب‌سازی، فیلترها، دیالوگ افزودن دانلود و تنظیمات است.

گالری اسکرین‌شات‌ها پس از آماده‌شدن تصاویر تمیز و بدون مسیرها و نام‌فایل‌های شخصی دوباره اضافه می‌شود.

## 🚀 اجرای پروژه در ویندوز

ساده‌ترین روش:

```bat
run.bat
```

یا به‌صورت دستی:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

روش جایگزین:

```bat
python -m omni_download_manager
```

## 📦 نسخهٔ Portable

نسخهٔ ویندوزی فعلی **Portable** است و نصب‌کنندهٔ Setup نیست.

بعد از استخراج ZIP، فایل زیر را اجرا کنید:

```text
Omni Download Manager.exe
```

پوشهٔ `_internal` باید در کنار فایل EXE باقی بماند.

## 🧪 تست‌ها

برای اجرای تست‌ها:

```bat
python -m unittest discover -s tests -t .
```

در آخرین اجرای تأییدشده، **هر ۱۰۶ تست با موفقیت پاس شده‌اند**. تست‌ها بخش‌های مختلف موتور دانلود، صف، retry، زمان‌بندی، بازیابی، فیلتر، جست‌وجو، ذخیره‌سازی و قابلیت‌های مرتبط با رابط کاربری را بررسی می‌کنند.

تست‌های دانلود از یک HTTP server محلی استفاده می‌کنند و به سرویس دانلود خارجی وابسته نیستند.

## 🏗️ معماری

پروژه به بخش‌های مستقلی تقسیم شده است:

- `core` — مدل‌ها، وضعیت‌ها، خطاها و دسته‌بندی فایل‌ها.
- `engine` — موتور HTTP، اندازه‌گیری سرعت و مدیریت نام فایل.
- `storage` — SQLite و migrationها.
- `config` — مسیرها و تنظیمات.
- `services` — صف، زمان‌بندی، retry، workerها و هماهنگی دانلودها.
- `ui` — رابط PySide6، دیالوگ‌ها، صفحات و تم‌ها.
- `utils` — ابزارهای کمکی، لاگ، اعتبارسنجی و ارتباط با سیستم‌عامل.

دانلودها در worker thread انجام می‌شوند و تغییرات وضعیت از طریق رویدادها و سیگنال‌های Qt به رابط کاربری منتقل می‌شوند.

## 💾 ذخیره‌سازی اطلاعات

در ویندوز، مسیر پیش‌فرض اطلاعات برنامه:

```text
%APPDATA%\Omni Download Manager\
```

اطلاعات اصلی شامل موارد زیر است:

```text
settings.json
downloads.db
logs/
```

مسیر ذخیره‌سازی را می‌توان با متغیر زیر تغییر داد:

```text
ODM_DATA_DIR
```

سازگاری با مسیر قدیمی `FETCHLY_DATA_DIR` نیز برای مهاجرت اطلاعات در نظر گرفته شده است.

## 🔨 ساخت نسخهٔ ویندوز

برای ساخت نسخهٔ Portable با PyInstaller:

```bat
python -m pip install pyinstaller
python scripts\make_icon.py
pyinstaller --noconfirm packaging\omni_download_manager.spec
```

خروجی شامل فایل اجرایی و پوشهٔ `_internal` است و برای توزیع باید کل پوشه بسته‌بندی شود.

## ⚠️ محدودیت‌های فعلی

در نسخهٔ `0.1.0` موارد زیر هنوز پیاده‌سازی نشده‌اند:

- دانلود FTP.
- پشتیبانی از BitTorrent.
- اتصال مستقیم به مرورگر برای دریافت خودکار لینک دانلود.
- دانلود چنداتصالی یا Segmented.
- ورود به حساب، Cookie و Header سفارشی قابل تنظیم.
- رابط مستقل برای تنظیم دستی Proxy.
- نصب‌کنندهٔ سنتی Setup/Installer.

## 📄 مجوز

فعلاً مجوزی برای پروژه انتخاب یا به مخزن اضافه نشده است. تا زمان اضافه‌شدن فایل
مجوز، شرایط استفادهٔ مجدد، تغییر و بازتوزیع مشخص نیست. پیش از معرفی پروژه به‌عنوان
متن‌باز یا بازتوزیع آن، یک مجوز انتخاب و اضافه کنید.

## 🗺️ وضعیت پروژه

نسخهٔ **0.1.0** یک نسخهٔ اولیه اما کاربردی از Omni Download Manager است که روی یک هستهٔ دانلود پایدار، مدیریت صف، زمان‌بندی، تاریخچهٔ دائمی و رابط کاربری مرتب تمرکز دارد.

ساختار ماژولار پروژه اجازه می‌دهد در نسخه‌های بعدی امکانات بیشتری به موتور دانلود و خود برنامه اضافه شود، بدون اینکه نیاز به بازنویسی کامل رابط کاربری یا سیستم ذخیره‌سازی باشد.

---

<p align="center">
  <strong>Omni Download Manager · v0.1.0</strong><br>
  Built with Python & PySide6 · Made for Windows
</p>

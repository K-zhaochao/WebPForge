<div align="center">

# WebPForge

**Batch image → WebP converter for the desktop · Double-click to run · No Python required**

[![Build & Release](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml/badge.svg)](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/K-zhaochao/WebPForge?color=3ac0d6&label=release)](https://github.com/K-zhaochao/WebPForge/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-6f7cff)

[中文](README.md) · **English**

Drop in a pile of JPG / PNG / BMP / GIF / TIFF files, hit **Start**, and get smaller WebP images.

</div>

---

## Download

Grab the archive for your system from [**Releases**](https://github.com/K-zhaochao/WebPForge/releases/latest) and just double-click it:

| Platform | File |
|---|---|
| Windows 10/11 (x64) | `WebPForge-<version>-Windows-x64.zip` → run `WebPForge.exe` |
| macOS (Apple Silicon / M-series) | `WebPForge-<version>-macOS-ARM64.zip` → run `WebPForge.app` |
| macOS (Intel) | see the note below ↓ |

> **Intel Mac users**: GitHub's Intel runner image (`macos-13`) is being retired and its queue
> times are extreme, so the Intel build is **triggered manually** — bundling it into the release
> pipeline would stall every release.
> Go to [Actions → Build macOS Intel (manual)](https://github.com/K-zhaochao/WebPForge/actions/workflows/build-intel.yml),
> click **Run workflow**, then download `WebPForge-macOS-Intel.zip` from that run's Artifacts.
> Alternatively, just run `./build_macos.sh` on your own Intel Mac.

> The app is **not code-signed**, so the first launch triggers a system warning — this is expected:
> - **Windows**: SmartScreen → *More info* → *Run anyway*
> - **macOS**: right-click the app → *Open* → *Open* again (or run `xattr -cr WebPForge.app`)

The user interface is currently in Chinese. The app itself is language-neutral in behaviour;
contributions adding i18n are welcome.

---

## Features

| Feature | Notes |
|---|---|
| Batch conversion | Add hundreds or thousands of images; converts in parallel |
| Drag & drop | Drop files/folders straight onto the window (Windows) |
| Quality control | Adjustable 1–100, plus a true **lossless** mode |
| Transparency kept | PNG alpha channels are preserved |
| Auto-rotate | Applies EXIF orientation from phone photos |
| Animation kept | Animated GIF → **animated WebP**, frames and loop intact |
| Smart mode | If the result would be *larger*, the original is kept — no generation loss |
| Never overwrites | Name clashes become `name(1).webp`; your files are never lost |
| Keep structure | Optionally recreates the sub-folder hierarchy |
| Resize limit | Cap the longest edge at N pixels for the whole batch |
| Unicode-safe | Chinese (and any non-ASCII) file names and paths work |
| Fully offline | No network access, nothing is uploaded |

**Input**: JPG / JPEG / PNG / BMP / GIF / TIFF / TGA / ICO / WebP / AVIF and anything else Pillow can read.
**Output**: **WebP (default)**, plus PNG / JPEG / AVIF.

---

## Interface

```
┌────────────────────────────────────────────────────────────┐
│  ➕Add images  📁Add folder  ➖Remove  🗑Clear   ■Stop ▶Start │
├──────────────────────────────┬─────────────────────────────┤
│  File            Size   Status│  ┌─Preview─┬─Settings─┐     │
│  photo1.jpg     2.1 MB   Done │  │                │       │
│  photo2.png     840 KB   Wait │  │  image preview │       │
│  ...                          │  │                │       │
├──────────────────────────────┴─────────────────────────────┤
│  ████████████████████░░░░░░░░  Converting 128/200 …         │
│                        200 files · 128 done · 76% smaller   │
└────────────────────────────────────────────────────────────┘
```

### Recommended settings

| Option | Recommendation |
|---|---|
| **Format** | Keep `WebP`; switch to JPEG/PNG only for legacy software |
| **Quality** | **75–85** is the sweet spot for the web; 90–95 for archiving |
| **Lossless** | Only when you need pixel-exact output (much larger files) |
| **Smart mode** | **Leave it on** — prevents re-compressing already-optimised images |
| **Output location** | Defaults to *next to the original*; pick a separate folder for big batches |
| **Keep sub-folder structure** | Enable when processing a whole project tree |
| **Overwrite same-name files** | **Off** by default (auto-renaming is safer) |
| **Flatten transparency** | Needed only when converting to JPEG |
| **Max edge** | `0` = no resize; e.g. `1920` to cap the width of the whole batch |

---

## Command line

The packaged app doubles as a CLI tool:

```bash
# Convert a whole folder to WebP at quality 80
WebPForge --cli -i ./photos -o ./out -q 80

# Recurse and preserve the folder structure
WebPForge --cli -i ./albums -o ./webp --keep -q 75

# Lossless, capped at 1920px on the longest edge
WebPForge --cli -i ./raw -o ./large --lossless --max-edge 1920

# Same thing from source
python webp_converter.py --cli -i ./photos -o ./out -q 80
```

### Options

| Flag | Description |
|---|---|
| `--cli` | Command-line mode (don't open the GUI) |
| `-i, --input` | Input files / folders / globs (one or more) |
| `-o, --outdir` | Output directory (default: next to each source file) |
| `-q, --quality` | Quality 1–100, default 80 |
| `-f, --format` | Output format: `webp` (default) / `png` / `jpeg` / `avif` |
| `--lossless` | Lossless encoding |
| `--keep` | Preserve sub-folder structure |
| `--overwrite` | Overwrite same-name files (default: auto-rename) |
| `--flatten` | Fill transparent areas with a background colour |
| `--bg` | Fill colour, default `#ffffff` |
| `--max-edge` | Cap the longest edge in pixels; 0 = no resize |
| `--smaller-only` | Only write the result if it is smaller |
| `--no-recursive` | Do not descend into sub-folders |
| `-j, --workers` | Worker threads (default: automatic) |
| `--json` | Machine-readable JSON output |
| `--selftest` | Verify the environment and conversion pipeline |

---

## Run from source

```bash
git clone https://github.com/K-zhaochao/WebPForge.git
cd WebPForge
python -m pip install pillow
python webp_converter.py            # open the GUI
python webp_converter.py --selftest
```

Requires Python **3.8+** with **tkinter** (bundled in the official python.org installers; on Linux usually `python3-tk`).

---

## Building it yourself

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

Outputs `dist\WebPForge.exe` (single file) and `release\WebPForge-Windows.zip`.

### macOS

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Outputs `dist/WebPForge.app` and `dist/WebPForge.dmg`.

> macOS apps must be built on macOS. If you'd rather not set up a toolchain,
> just push a tag and let GitHub Actions build it for you.

### Manual build

```bash
python -m pip install pillow pyinstaller
python tools/make_icon.py assets
pyinstaller --clean --noconfirm build.spec
```

---

## Releasing

Push a version tag and GitHub Actions builds all three platforms and creates the Release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

See [`.github/workflows/build.yml`](.github/workflows/build.yml): Windows and Apple Silicon build
in parallel, results are zipped for double-click use, and the Release is created with the installers attached.

The Intel build lives in [`.github/workflows/build-intel.yml`](.github/workflows/build-intel.yml) and is
triggered manually — **deliberately kept out of the automatic pipeline**, because GitHub's Intel runners
often queue for 30+ minutes and would stall every release.

The release notes template lives in [`.github/RELEASE_BODY.md`](.github/RELEASE_BODY.md);
the version and download file names are substituted automatically at publish time.

---

## Project layout

```
WebPForge/
├── webp_converter.py            # everything: GUI + engine + CLI
├── build.spec                   # PyInstaller configuration
├── build_windows.ps1            # one-shot Windows build (self-tests the output)
├── build_macos.sh               # one-shot macOS build (.app + .dmg)
├── convert.bat                  # Windows CLI launcher
├── version_info.txt             # exe version resource
├── assets/                      # icons (generated by make_icon.py)
├── .github/
│   ├── workflows/
│   │   ├── build.yml            # auto build Windows + Apple Silicon, publish Release
│   │   └── build-intel.yml      # manual Intel build (keeps releases fast)
│   └── RELEASE_BODY.md          # release notes template
└── tools/
    ├── make_icon.py             # generate .ico / .icns
    ├── make_testdata.py         # generate test images (unicode/alpha/animated/corrupt)
    ├── stress_test.py           # concurrency stress test
    ├── test_gui_flow.py         # GUI interaction chain test
    ├── test_gui_launch.py       # GUI launch test
    ├── diag_gui.py              # GUI diagnostics
    └── find_window.py           # locate the app window (verifies packaged output)
```

---

## Testing

```bash
python webp_converter.py --selftest          # environment + conversion self-test
python tools/make_testdata.py _testdata      # create test images
python tools/stress_test.py _stress          # concurrency test (72 clashing names)
python tools/test_gui_flow.py                # GUI interaction chain
```

---

## FAQ

**Why did the file get *bigger*?**
The source was probably already WebP, or an aggressively compressed JPEG. Keep **Smart mode** on and those files are skipped automatically.

**My transparent PNG came out with a white background.**
WebP **does** support transparency and it is preserved by default. Transparency is only lost if you enable *flatten transparency* or choose JPEG as the output format.

**Do animated GIFs become static?**
No. Converting to WebP keeps every frame, per-frame duration and the loop count.

**Will it overwrite my originals?**
Never. The tool only *adds* `.webp` files; originals are never deleted or modified. Name clashes become `name(1).webp`.

**How long does a few thousand images take?**
The app scales across your CPU cores automatically. 1,000 typical photos usually take 1–3 minutes.

**Does it phone home?**
No. Everything happens locally and nothing is uploaded.

**Nothing happens when I double-click on Windows.**
Some antivirus tools block freshly built executables — whitelist it, or run
`WebPForge.exe --selftest` from a terminal (the report is written to `WebPForge_selftest.txt`
next to the executable).

**macOS says the app "is damaged and can't be opened".**
That's Gatekeeper reacting to an unsigned app. Run `xattr -cr WebPForge.app` to clear it.

---

## License

[MIT License](LICENSE) · free to use, modify and redistribute

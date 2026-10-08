<div align="center">

# WebPForge

**Batch image → WebP converter for the desktop · Double-click to run · No Python required**

[![Build & Release](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml/badge.svg)](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/K-zhaochao/WebPForge?color=3ac0d6&label=release)](https://github.com/K-zhaochao/WebPForge/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-6f7cff)

[中文](README.md) · **English**

[**Official website & live WebP demo (Chinese)**](https://webp.royi.net/)

Drop in a pile of JPG / PNG / BMP / GIF / TIFF files, hit **Start**, and get smaller WebP images.

</div>

---

## Download

The [official website](https://webp.royi.net/) provides release downloads and a working browser demo.
The demo converts static JPEG, PNG and WebP images locally, with a quality slider, visual comparison and downloadable output.
Install the PWA on Android through the browser menu, or on iOS through Safari → Share → Add to Home Screen. This is an installable web app, not an APK or App Store native app. Offline conversion works after the initial cache finishes.
Images are never uploaded. For batches, animation and lossless encoding, use the desktop application.
Website development and GitHub Pages deployment are documented in [docs/website.md](docs/website.md).

Grab the archive for your system from [**Releases**](https://github.com/K-zhaochao/WebPForge/releases/latest) and just double-click it:

| Platform | File |
|---|---|
| Windows 10/11 (x64) | `WebPForge-<version>-Windows-x64.zip` → run `WebPForge.exe` |
| macOS (Apple Silicon / M-series) | `WebPForge-<version>-macOS-ARM64.zip` → run `WebPForge.app` |
| macOS (Intel) | `WebPForge-<version>-macOS-Intel.zip` → run `WebPForge.app` |

> **Intel Mac users**: v1.1.0 and newer releases include a separate Intel package, built automatically.

> The app is **not code-signed**, so the first launch triggers a system warning — this is expected:
> - **Windows**: SmartScreen → *More info* → *Run anyway*
> - **macOS**: right-click the app → *Open* → *Open* again (or run `xattr -cr WebPForge.app`)

The user interface is currently in Chinese. The app itself is language-neutral in behaviour;
contributions adding i18n are welcome.

---

## Features

| Feature | Notes |
|---|---|
| Batch conversion | Background folder scanning, bounded parallel tasks, progress in completion order |
| Drag & drop | Drop files/folders straight onto the window (Windows) |
| Quality control | Adjustable 1–100, plus a true **lossless** mode |
| Transparency kept | PNG alpha channels are preserved |
| Auto-rotate | Applies EXIF orientation from phone photos |
| Animation kept | Animated GIF → **animated WebP**, frames and loop intact |
| Smart mode | Skips results that are not smaller, without creating an output; on by default in the GUI, opt in with `--smaller-only` in the CLI |
| Source protection | Auto-renames by default; optional overwrite replaces existing outputs while protecting every input in the batch |
| Stop and retry | Resume cancelled tasks or retry only failed files; one bad input does not abort the batch |
| Preview | Correct photo orientation, fit-to-window thumbnails, actual output size after conversion |
| Keep structure | Optionally recreates the sub-folder hierarchy |
| Resize limit | Cap the longest edge at N pixels for the whole batch |
| Unicode-safe | Chinese (and any non-ASCII) file names and paths work |
| Fully offline | No network access, nothing is uploaded |

**Input**: JPG / JPEG / PNG / BMP / GIF / TIFF / TGA / ICO / WebP / AVIF and anything else Pillow can read.
**Output**: **WebP (default)**, plus PNG / JPEG / AVIF.

AVIF encoding depends on your Pillow installation; use a recent Python and Pillow.
Some recognized extensions, including HEIC and RAW, require extra Pillow plugins.
Unsupported or corrupt files are reported individually.

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

### Stop, resume, and retry

- **Stop** or `Esc` stops new tasks, waits for active encoders, and cleans temporary files.
- Cancelled files have a separate status and count. They do not inflate savings or force progress to 100%.
- **Start** resumes failed or cancelled items; **Retry failed** processes only failures.
- If everything has completed or been smart-skipped, Start asks before processing the whole list again.
- Adding, removing, clearing, and changing conversion settings are locked during scanning/conversion. Closing the window stops work before exiting.
- **Open output folder** in the preview tab opens the selected output directory, or the source directory when no output was created.

Folder scans exclude a nested custom output directory. Existing queue entries are kept;
explicitly selecting that directory or its files is still supported.

### Recommended settings

| Option | Recommendation |
|---|---|
| **Format** | Keep `WebP`; switch to JPEG/PNG only for legacy software |
| **Quality** | **75–85** is the sweet spot for the web; 90–95 for archiving |
| **Lossless** | WebP / PNG only; disables PNG palette quantization. Unavailable for JPEG / AVIF |
| **Smart mode** | Keeps only smaller results; turn off if every input must produce a target-format file |
| **Output location** | Defaults to *next to the original*; pick a separate folder for big batches |
| **Keep sub-folder structure** | Enable when processing a whole project tree |
| **Overwrite existing outputs** | **Off** by default; input files and conflicting outputs within a batch still get unique names |
| **Flatten transparency** | Needed only when converting to JPEG |
| **Max edge** | `0` = no resize; e.g. `1920` to cap the width of the whole batch |

PNG uses palette quantization when quality is below 100 and lossless is off.
Invalid colors, dimensions, and CLI numeric options are reported before conversion.

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
| `-o, --outdir` | Output directory (omitted: next to the source; `-o .`: current working directory) |
| `-q, --quality` | Quality 1–100, default 80 |
| `-f, --format` | Output format: `webp` (default) / `png` / `jpeg` / `avif` |
| `--lossless` | Lossless WebP / PNG; rejected for JPEG / AVIF |
| `--keep` | Preserve sub-folder structure |
| `--overwrite` | Replace existing outputs while protecting all batch inputs and concurrent outputs |
| `--flatten` | Fill transparent areas with a background colour |
| `--bg` | Fill colour, default `#ffffff` |
| `--max-edge` | Cap the longest edge in pixels; 0 = no resize |
| `--smaller-only` | Only write the result if it is smaller |
| `--no-recursive` | Do not descend into sub-folders |
| `-j, --workers` | Worker threads (default: automatic) |
| `--json` | JSON summary and per-file output paths, status, sizes, and errors |
| `--selftest [REPORT]` | Verify the environment and conversion pipeline; optional report path |

`Ctrl+C` requests cancellation and cleans unpublished results.
Exit codes: `0` success/smart skips, `1` no inputs or environment error, `2` invalid arguments,
`3` file failures, `130` cancelled items.
JSON retains the original summary fields and adds `cancelled` and `items`.
Per-file status is `ok`, `skipped`, `failed`, or `cancelled`; `output` is `null` when nothing was produced.
On Windows, CLI stdout and stderr use UTF-8 and support pipes and file redirection.

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

Update APP_VERSION in webp_converter.py, both numeric and string versions in version_info.txt, and CHANGELOG. Test before tagging. Example for a future unused version:

```bash
git add .
git commit -m "Release WebPForge v1.2.0"
git push origin main
git tag -a v1.2.0 -m "WebPForge v1.2.0"
git push origin v1.2.0
```

The workflow packages Windows x64, macOS ARM64 and Intel in parallel, then publishes the three ZIPs, the web ZIP, SHA256SUMS.txt and release-manifest.json. The website refreshes downloads after the release workflow completes. Manual runs only build artifacts. See [release maintenance](docs/releases.md).


---

## Project layout

```
WebPForge/
├── webp_converter.py            # everything: GUI + engine + CLI
├── CHANGELOG.md                 # changes and validation notes
├── tests/                       # conversion, file safety, CLI, and real GUI tests
├── build.spec                   # PyInstaller configuration
├── build_windows.ps1            # one-shot Windows build (self-tests the output)
├── build_macos.sh               # one-shot macOS build (.app + .dmg)
├── convert.bat                  # Windows CLI launcher
├── version_info.txt             # exe version resource
├── assets/                      # icons (generated by make_icon.py)
├── .github/
│   ├── workflows/
│   │   ├── test.yml             # Windows / Linux regression tests
│   │   ├── build.yml            # auto build Windows + Apple Silicon, publish Release
│   │   └── build-intel.yml      # standalone Intel build fallback
│   └── RELEASE_BODY.md          # release notes template
└── tools/
    ├── make_icon.py             # generate .ico / .icns
    ├── make_testdata.py         # generate test images (unicode/alpha/animated/corrupt)
    ├── stress_test.py           # concurrency stress test
    ├── test_gui_flow.py         # GUI interaction chain test
    ├── test_gui_launch.py       # GUI launch test
    ├── test_packaged.py         # EXE self-test, JSON redirection, all output formats
    ├── diag_gui.py              # GUI diagnostics
    └── find_window.py           # locate the app window (verifies packaged output)
```

---

## Testing

```bash
python -m unittest discover -s tests -v      # all regressions (GUI needs a display)
python webp_converter.py --selftest          # environment + conversion self-test
python tools/make_testdata.py _testdata      # create test images
python tools/stress_test.py _stress          # concurrency test (72 clashing names)
python tools/test_gui_flow.py               # real GUI: preview, stop, resume, retry
python tools/test_gui_launch.py             # GUI creation and normal shutdown on the main thread
python tools/test_packaged.py dist/WebPForge.exe  # packaged checks (requires AVIF-capable Pillow)
```

Regression tests create and clean their own temporary images; `_testdata` is not required.
On headless Linux, run `xvfb-run -a python -m unittest discover -s tests -v`.
GUI tests explicitly skip when no display is available. The test workflow covers
Windows / Linux and Python 3.8 / 3.13.

---

## FAQ

**Why did the file get *bigger*?**
The source was probably already WebP, or an aggressively compressed JPEG. Keep **Smart mode** on and those files are skipped automatically.

**My transparent PNG came out with a white background.**
WebP **does** support transparency and it is preserved by default. Transparency is only lost if you enable *flatten transparency* or choose JPEG as the output format.

**Do animated GIFs become static?**
WebP keeps every frame, duration, and loop setting. A GIF without loop metadata plays once.
PNG / JPEG / AVIF currently retain only the first frame; the result message states this.

**Will it overwrite my originals?**
By default the tool only adds files; clashes become `name(1).webp`. Even with overwrite enabled,
every input in the current batch is protected. Existing outputs are replaced only after successful
encoding; failures and cancellation preserve them.

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

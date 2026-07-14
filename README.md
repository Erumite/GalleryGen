# Family Photo Gallery Generator

Scans a folder of photos and generates a single self-contained `index.html` file you can open in any browser — no server required. The HTML embeds the full file tree, EXIF metadata, and a JavaScript viewer, so it works offline and is easy to share.

## Features

- Folder navigation with breadcrumb trail
- Lightbox viewer with keyboard navigation (←/→/Esc)
- Face detection bounding boxes (hover to reveal names) from EXIF region data
- Captions, people, and tags shown per photo
- Search across filenames, captions, tags, and tagged people names

## Requirements

[exiftool](https://exiftool.org) must be installed and on your PATH.

- **Mac**: `brew install exiftool`
- **Windows**: download the installer from https://exiftool.org
- **Linux**: `sudo apt install libimage-exiftool-perl`

## Usage

**From a downloaded executable** (see [Releases](../../releases)):

```bash
# Mac/Linux — scan current directory, write index.html
./generate_gallery

# Scan a specific folder
./generate_gallery /path/to/photos

# Write output to a different file
./generate_gallery /path/to/photos -o gallery.html
```

```powershell
# Windows
generate_gallery.exe C:\Photos
generate_gallery.exe C:\Photos -o gallery.html
```

**From Python source**:

```bash
python3 generate_gallery.py /path/to/photos
```

Open the resulting `index.html` in any browser.

## Options

| Argument | Default | Description |
|---|---|---|
| `directory` | `.` (current dir) | Root folder to scan for images |
| `-o, --output FILE` | `index.html` | Output HTML file path |

Supported image formats: `.jpg`, `.jpeg`, `.png`, `.webp`

## Building from source

```bash
pip install pyinstaller
pyinstaller --onefile generate_gallery.py
# Output: dist/generate_gallery  (or dist/generate_gallery.exe on Windows)
```

Pre-built binaries for Mac and Windows are produced automatically by the GitHub Actions workflow on every push to `main` (downloadable from the Actions tab) and attached to GitHub Releases when a version tag is pushed:

```bash
git tag v1.0
git push origin v1.0
```

#!/bin/bash
# resize_optimize.sh - usage: ./resize_optimize.sh /path/to/folder 1024 [--jpegoptim] [--optipng]

# For very large photos, this may be useful for shrinking their size for a gallery that can fit on a thumb drive.
# This is DESTRUCTIVE, so only run on a backup of the original images before shrinking them for a gallery.

FOLDER="$1"
MAX_SIZE="$2"
OPT_JPEG=false
OPT_PNG=false

shift 2
for arg in "$@"; do
    case $arg in
        --jpegoptim) OPT_JPEG=true ;;
        --optipng) OPT_PNG=true ;;
    esac
done

if [ -z "$FOLDER" ] || [ -z "$MAX_SIZE" ]; then
    echo "Usage: $0 <folder> <max_size> [--jpegoptim] [--optipng]"
    exit 1
fi

# Find image files, resize only those larger than max_size
find "$FOLDER" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) -print0 | while IFS= read -r -d '' file; do
    # Resize with ImageMagick (preserves EXIF)
    mogrify -resize "${MAX_SIZE}x${MAX_SIZE}>" -quality 90 "$file"

    ext="${file##*.}"
    if [[ "$ext" =~ ^(jpg|jpeg)$ ]] && [ "$OPT_JPEG" = true ]; then
        if command -v jpegoptim >/dev/null 2>&1; then
            jpegoptim "$file"   # preserves EXIF by default
        else
            echo "Warning: jpegoptim not installed."
        fi
    elif [ "$ext" = "png" ] && [ "$OPT_PNG" = true ]; then
        if command -v optipng >/dev/null 2>&1; then
            optipng "$file"      # preserves metadata by default
        else
            echo "Warning: optipng not installed."
        fi
    fi
done
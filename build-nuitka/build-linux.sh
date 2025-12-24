#!/bin/bash
# Nuitka build script for Vial on Linux
# Run from the gui directory: ./build-nuitka/build-linux.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$GUI_DIR/src/main/python"
RESOURCES_DIR="$GUI_DIR/src/main/resources/base"
OUTPUT_DIR="$GUI_DIR/build-nuitka/output"

# Read version from base.json
VERSION=$(python3 -c "import json; print(json.load(open('$GUI_DIR/src/build/settings/base.json'))['version'])")

echo "Building Vial version $VERSION"

# Clean previous build
rm -rf "$OUTPUT_DIR"

# Run Nuitka
python3 -m nuitka \
    --standalone \
    --enable-plugin=pyqt5 \
    --include-data-dir="$RESOURCES_DIR"=. \
    --include-data-file="$GUI_DIR/src/build/settings/base.json"=build_settings.json \
    --linux-icon="$GUI_DIR/src/main/icons/linux/256.png" \
    --output-dir="$OUTPUT_DIR" \
    --output-filename=Vial \
    --assume-yes-for-downloads \
    --remove-output \
    "$SRC_DIR/main.py"

echo ""
echo "Build complete! Output in: $OUTPUT_DIR/main.dist"
echo ""
echo "To run: $OUTPUT_DIR/main.dist/Vial"
echo ""
echo "To create AppImage, use appimagetool on the main.dist directory"

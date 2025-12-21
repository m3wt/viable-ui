#!/bin/bash

set -e

export LD_LIBRARY_PATH=/python36/prefix/lib/

# Copy source to writable location (source is mounted read-only)
echo "Preparing build directory..."
rm -rf /build
cp -a /vial-gui /build
cd /build

# Use persistent venv from volume if it exists and is valid
VENV_DIR="/venv/docker_venv"
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo "Using cached virtual environment..."
    . "$VENV_DIR/bin/activate"
else
    echo "Creating new virtual environment..."
    /python36/prefix/bin/python3 -m venv "$VENV_DIR"
    . "$VENV_DIR/bin/activate"
fi

# Always ensure pip is up to date and requirements are installed
pip install --upgrade pip
pip install -r requirements.txt

echo "Running fbs freeze..."
fbs freeze

echo "Running fbs installer..."
fbs installer

deactivate

echo "Creating AppImage..."
/pkg2appimage-*/pkg2appimage misc/Vial.yml

mv out/Vial-*.AppImage /output/Vial-x86_64.AppImage
echo "Done!"

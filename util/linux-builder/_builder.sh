#!/bin/bash

set -e

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
    python3 -m venv "$VENV_DIR"
    . "$VENV_DIR/bin/activate"
fi

# Always ensure pip is up to date and requirements are installed
pip install --upgrade pip
pip install -r requirements-build.txt

echo "Running Nuitka build..."
export QT_API=pyside6
./build-nuitka/build-linux.sh

deactivate

echo "Creating AppImage..."
APPDIR="/build/Vial.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/applications"

# Copy Nuitka output
cp -a build-nuitka/output/main.dist/* "$APPDIR/usr/bin/"

# Bundle system libraries for portability
# Note: We copy specific versions and create symlinks as needed
copy_lib() {
  local lib="$1"
  for path in /usr/lib/x86_64-linux-gnu /lib/x86_64-linux-gnu; do
    if [ -f "$path/$lib" ]; then
      cp -L "$path/$lib" "$APPDIR/usr/lib/"
      return 0
    fi
  done
  return 1
}

# XCB and X11 libraries
for lib in libxcb-cursor.so.0 libxcb-icccm.so.4 libxcb-util.so.1 \
           libxcb-image.so.0 libxcb-keysyms.so.1 libxcb-randr.so.0 \
           libxcb-render-util.so.0 libxcb-render.so.0 libxcb-shape.so.0 \
           libxcb-shm.so.0 libxcb-sync.so.1 libxcb-xfixes.so.0 \
           libxcb-xkb.so.1 libxcb.so.1 libxcb-glx.so.0 \
           libxkbcommon.so.0 libxkbcommon-x11.so.0 \
           libX11.so.6 libX11-xcb.so.1 libXau.so.6 libXdmcp.so.6; do
  copy_lib "$lib"
done

# Additional required libraries
for lib in libzstd.so.1 libz.so.1 libbsd.so.0 libmd.so.0; do
  copy_lib "$lib"
done

# Copy icon
cp src/main/icons/linux/256.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/vial.png"
cp src/main/icons/linux/256.png "$APPDIR/vial.png"

# Create desktop file
cat > "$APPDIR/vial.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Vial
Comment=Configure your Vial-enabled keyboard
Exec=Vial
Icon=vial
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;vial;qmk;firmware;
StartupNotify=true
EOF
cp "$APPDIR/vial.desktop" "$APPDIR/usr/share/applications/"

# Create AppRun
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/sh
HERE=$(dirname $(readlink -f "${0}"))
export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/bin:${LD_LIBRARY_PATH}"
export QT_QPA_PLATFORM=xcb
exec "${HERE}/usr/bin/Vial" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Build AppImage
ARCH=x86_64 appimagetool "$APPDIR" /output/Vial-x86_64.AppImage

echo "Done!"

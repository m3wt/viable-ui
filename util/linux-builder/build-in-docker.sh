#!/usr/bin/env bash

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$HERE/../.." && pwd)

# Use podman if available, otherwise docker
if command -v podman &> /dev/null; then
    CONTAINER_ENGINE=podman
elif command -v docker &> /dev/null; then
    CONTAINER_ENGINE=docker
else
    echo "Error: Neither podman nor docker found"
    exit 1
fi

echo "Using container engine: $CONTAINER_ENGINE"

# Helper functions to abstract engine differences
image_exists() {
    if [ "$CONTAINER_ENGINE" = "podman" ]; then
        $CONTAINER_ENGINE image exists "$1" 2>/dev/null
    else
        $CONTAINER_ENGINE image inspect "$1" &>/dev/null
    fi
}

volume_exists() {
    if [ "$CONTAINER_ENGINE" = "podman" ]; then
        $CONTAINER_ENGINE volume exists "$1" 2>/dev/null
    else
        $CONTAINER_ENGINE volume inspect "$1" &>/dev/null
    fi
}

cd "$HERE"
mkdir -p output

BASE_IMAGE="vialguibuilder-base:latest"
VENV_VOLUME="vialguibuilder-venv"

build_base_image() {
    echo "Building base image (this may take a while, but only needs to be done once)..."
    $CONTAINER_ENGINE build -t "$BASE_IMAGE" -f Dockerfile.base "$HERE"
}

if [ "$1" = "--rebuild-base" ]; then
    build_base_image
    shift
elif ! image_exists "$BASE_IMAGE"; then
    build_base_image
fi

if ! volume_exists "$VENV_VOLUME"; then
    $CONTAINER_ENGINE volume create "$VENV_VOLUME"
fi

# Run build with source mounted as volume (incremental)
echo "Running incremental build..."
$CONTAINER_ENGINE run --privileged --rm \
    -v "$REPO_ROOT:/vial-gui:ro" \
    -v "$VENV_VOLUME:/venv" \
    -v "$(realpath output):/output" \
    "$BASE_IMAGE" \
    bash /vial-gui/util/linux-builder/_builder.sh

echo ""
echo "Build complete:"
ls -lah output

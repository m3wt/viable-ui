#!/bin/bash
# Creates minimal TrueType CJK font subsets for ISO/JIS key labels
# TrueType (glyf) required for Qt WASM compatibility - CFF fonts don't work
# Requires: nix-shell with packages below

# Characters needed:
# Japanese: カタカナひらがな変換無英数かな¥漢字
# Korean: 한영漢字

set -e

# Download M PLUS 1 (Japanese TTF)
curl -sL "https://github.com/coz-m/MPLUS_FONTS/raw/master/fonts/ttf/Mplus1-Regular.ttf" -o mplus.ttf

nix-shell -p nanum python3Packages.fonttools --run '
# Japanese subset from M PLUS
pyftsubset mplus.ttf \
    --text="カタカナひらがな変換無英数かな¥漢字" \
    --output-file=MPlus-JP.ttf

# Korean subset from Nanum
nanum_font=$(find /nix/store -path "*nanum*" -name "NanumBarunGothic.ttf" 2>/dev/null | head -1)
pyftsubset "$nanum_font" \
    --text="한영漢字" \
    --output-file=Nanum-KR.ttf
'

rm -f mplus.ttf
echo "Created:"
ls -lh MPlus-JP.ttf Nanum-KR.ttf

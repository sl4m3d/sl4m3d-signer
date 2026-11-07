#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller==6.16.0

brew install openssl@3
OPENSSL_PREFIX="$(brew --prefix openssl@3)"

ARCH="$(uname -m)"
OUT="$ROOT/mac/output/$ARCH"

mkdir -p "$OUT"
rm -rf build dist

pyinstaller --noconfirm --clean --windowed --onedir \
  --name "sl4m3d Signer" \
  --add-data "linux/source-portable/app/assets:assets" \
  linux/source-portable/app/src/signer.py

APP="$ROOT/dist/sl4m3d Signer.app"

if [[ ! -d "$APP" ]]; then
    echo "PyInstaller did not create the app bundle" >&2
    exit 1
fi

OPENSSL_DIR="$APP/Contents/Frameworks/openssl"

mkdir -p \
  "$OPENSSL_DIR/bin" \
  "$OPENSSL_DIR/lib/ossl-modules" \
  "$OPENSSL_DIR/ssl"

cp -L "$OPENSSL_PREFIX/bin/openssl" \
  "$OPENSSL_DIR/bin/openssl"

cp -L "$OPENSSL_PREFIX/lib/libcrypto.3.dylib" \
  "$OPENSSL_DIR/lib/libcrypto.3.dylib"

cp -L "$OPENSSL_PREFIX/lib/libssl.3.dylib" \
  "$OPENSSL_DIR/lib/libssl.3.dylib"

cp -L "$OPENSSL_PREFIX/lib/ossl-modules/legacy.dylib" \
  "$OPENSSL_DIR/lib/ossl-modules/legacy.dylib"

if [[ -f "$OPENSSL_PREFIX/ssl/openssl.cnf" ]]; then
    cp -L "$OPENSSL_PREFIX/ssl/openssl.cnf" \
      "$OPENSSL_DIR/ssl/openssl.cnf"
fi

install_name_tool -change \
  "$OPENSSL_PREFIX/lib/libcrypto.3.dylib" \
  "@loader_path/../libcrypto.3.dylib" \
  "$OPENSSL_DIR/lib/libssl.3.dylib" || true

install_name_tool -change \
  "$OPENSSL_PREFIX/lib/libcrypto.3.dylib" \
  "@executable_path/../lib/libcrypto.3.dylib" \
  "$OPENSSL_DIR/bin/openssl" || true

install_name_tool -change \
  "$OPENSSL_PREFIX/lib/libssl.3.dylib" \
  "@executable_path/../lib/libssl.3.dylib" \
  "$OPENSSL_DIR/bin/openssl" || true

install_name_tool -change \
  "$OPENSSL_PREFIX/lib/libcrypto.3.dylib" \
  "@loader_path/../libcrypto.3.dylib" \
  "$OPENSSL_DIR/lib/ossl-modules/legacy.dylib" || true

chmod 755 "$OPENSSL_DIR/bin/openssl"

codesign --force --deep --sign - "$APP"

DMG="$OUT/sl4m3d-Signer-v1.2.0-$ARCH.dmg"
PKG="$OUT/sl4m3d-Signer-v1.2.0-$ARCH.pkg"

rm -f "$DMG" "$PKG"

# Create a clean staging directory for the DMG.
STAGE="$ROOT/mac/dmg-stage-$ARCH"

rm -rf "$STAGE"
mkdir -p "$STAGE"

ditto "$APP" "$STAGE/$(basename "$APP")"

# Retry DMG creation in case macOS reports a temporary resource lock.
DMG_CREATED=false

for attempt in 1 2 3; do
    echo "Creating DMG (attempt $attempt/3)..."

    if hdiutil create \
        -volname "sl4m3d Signer v1.2.0" \
        -srcfolder "$STAGE" \
        -ov \
        -format UDZO \
        "$DMG"; then

        DMG_CREATED=true
        break
    fi

    echo "DMG creation failed. Retrying..."
    rm -f "$DMG"
    sleep 5
done

rm -rf "$STAGE"

if [[ "$DMG_CREATED" != true ]]; then
    echo "DMG creation failed after 3 attempts."
    exit 1
fi

PKGROOT="$ROOT/mac/pkgroot-$ARCH"

rm -rf "$PKGROOT"
mkdir -p "$PKGROOT/Applications"

ditto "$APP" "$PKGROOT/Applications/$(basename "$APP")"

pkgbuild \
  --root "$PKGROOT" \
  --identifier "is.great.sl4m3d.signer" \
  --version "1.2.0" \
  --install-location / \
  "$PKG"

shasum -a 256 "$DMG" "$PKG" > "$OUT/SHA256SUMS.txt"

test -s "$DMG"
test -s "$PKG"

echo "BUILT: $DMG"
echo "BUILT: $PKG"
echo "NOTE: ad-hoc signed only; Developer ID signing and notarization are not configured."

# sl4m3d Signer v1.2 — Native installer build kit

This package contains the current v1.2 sources/build recipes and one GitHub Actions workflow that builds the requested native installers in the requested order and assembles a ZIP with `linux/`, `windows/`, `android/`, and `mac/` folders.

## Important: no native binaries are fabricated

The current local build host is Debian 13 x86_64. It does not contain Windows/Inno Setup, Android SDK/Gradle, or macOS/Xcode packaging tools. Replit's existing project is currently paused and the connected GitHub account has no repository available. Therefore this environment cannot honestly produce or test the EXE, APK, DMG, or PKG binaries.

## Build in GitHub Actions

1. Create a private or public GitHub repository you control.
2. Upload the *contents* of this folder to the repository root (keep `.github/` hidden folder).
3. Open **Actions → Build sl4m3d Signer installers → Run workflow**.
4. Wait for all four jobs to finish successfully.
5. Download the artifact `sl4m3d-signer-installers-v1.2`.

The workflow uses native Windows, Android/Linux, Intel macOS, and Apple Silicon macOS runners. It does not sign the Windows executable with an Authenticode certificate or notarize macOS packages. Those require owner-controlled signing credentials; do not put private signing keys into this repository.

## Output layout

```text
release/
  linux/
    installer.deb
    sl4m3d-signer-linux-portable.tar.gz
  windows/
    installer.exe
  android/
    installer.apk
  mac/
    installer-intel.dmg
    installer-intel.pkg
    installer-arm64.dmg
    installer-arm64.pkg
  SHA256SUMS.txt
```

## Android caveat

The APK is a debug-signed installable build, suitable for device testing. A Play Store/public release needs a stable app-signing key controlled by the publisher. This workflow intentionally does not create or store one.

## macOS caveat

The macOS build script creates ad-hoc-signed local-test packages. They are not Developer ID signed or notarized, so Gatekeeper may warn when users open them. Intel and Apple Silicon are built separately.

## Windows caveat

The EXE is packaged by Inno Setup. It is not Authenticode-signed, so Windows SmartScreen may show an unknown-publisher warning.

# Windows build source (v1.2.0)

This folder contains the reproducible Windows x64 build recipe, PyInstaller requirements, Inno Setup definition and GitHub Actions workflow. It does **not** contain an EXE because the current build host is Linux and cannot run a native Windows packaging toolchain.

## Build on Windows 10/11 x64

1. Install Python 3.13, OpenSSL 3 and Inno Setup 6.
2. Ensure `openssl.exe` and `ISCC.exe` are available on PATH.
3. From the extracted project root, run `windows\\build-windows.ps1` in PowerShell.
4. The script fails if the PyInstaller bundle, OpenSSL runtime or Inno Setup output is missing. It does not create an empty placeholder.

The output file is `windows/output/sl4m3d-Signer-Setup-v1.2.0.exe`. The build is unsigned until a trusted code-signing certificate is supplied. Offline signing works after installation because OpenSSL is bundled.

GitHub Actions recipe: `windows/ci/build-windows.yml` (copy to `.github/workflows/build-windows.yml` in a repository containing this release tree).

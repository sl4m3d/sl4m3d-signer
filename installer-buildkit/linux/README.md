# Linux downloads — sl4m3d Signer 1.2.0

## `installer.deb`

A real Debian package, built on Debian 13 (Trixie), `Architecture: all`. It installs the GUI and CLI launchers. Runtime requirements are Python 3.9+, Tkinter and OpenSSL 3.x. On Debian/Ubuntu, install the package with `sudo apt install ./installer.deb`.

## Portable TAR.GZ

The portable archive contains the application source and launcher. It is not a self-contained Python runtime: Python 3.9+, Tkinter and OpenSSL 3.x must already be present on the target Linux system. The core certificate, CMS and profile operations work without network access. Optional aggregate statistics are off by default and require explicit consent in Settings.

## Verification

See `TEST-REPORT.txt`. Do not interpret the local Debian 13 tests as validation on every Linux distribution or desktop environment.

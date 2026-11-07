# sl4m3d Signer v1.2.0 — Release Candidate

This archive uses four platform directories:

- `linux/`: **built and locally verified** Debian `.deb` installer plus portable source archive.
- `windows/`: Windows installer source and CI workflow. The `.exe` installer is **not included** because this Linux build host cannot execute a native Windows build.
- `android/`: native Android project and CI workflow. The `.apk` is **not included** because Android SDK/Gradle Android toolchain are not installed here.
- `mac/`: Intel and Apple Silicon packaging scripts and CI workflow. `.dmg` and `.pkg` are **not included** because this host is not macOS.

No empty or placeholder installers are supplied. Windows/Android/macOS artifacts become available only after the relevant native workflow builds and tests them.

## Local tests performed

- Python syntax compilation of all desktop modules
- RSA 2048 and EC P-256 certificate/P12 creation and identity-match validation
- CMS signing and integrity verification
- CER-only DER export with no persisted private key or P12
- `.mobileconfig` XML plist generation and payload validation
- GUI screen construction under Xvfb; scroll region tested at the supported minimum desktop window size
- Debian package metadata, extracted package self-test and installation file layout

See `linux/TEST-REPORT.txt` for the exact local result. Cross-platform binaries are explicitly marked unbuilt until CI artifacts exist.

# macOS build source (v1.2.0)

The build script produces an `.app`, compressed `.dmg` and installer `.pkg` on a real macOS host. The CI matrix is split between Intel x86_64 (`macos-15-intel`) and Apple Silicon arm64 (`macos-latest`). No macOS binary is included in this release candidate because the current host is Linux.

Run `bash mac/build-macos.sh` from a checked-out copy of the project on macOS 15 with Xcode Command Line Tools, Homebrew and Python 3.13. It bundles OpenSSL 3 and its legacy provider with the application. The generated package is ad-hoc signed only: it is **not** signed with a Developer ID and is **not** notarized. Public distribution requires the owner to provide a Developer ID signing identity and complete Apple notarization. Older macOS versions are not guaranteed by this macOS 15 build matrix.

GitHub Actions recipe: `mac/ci/build-macos.yml` (copy to `.github/workflows/build-macos.yml`).

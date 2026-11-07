#!/bin/sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required." >&2; exit 1
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "OpenSSL is required." >&2; exit 1
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  echo "Tkinter is missing. Install your distribution's python3-tk package." >&2; exit 1
fi
exec python3 "$HERE/app/src/signer.py" "$@"

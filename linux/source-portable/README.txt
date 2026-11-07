sl4m3d Signer v1.2.0 - Linux portable

Start GUI: ./run.sh
CLI: python3 app/src/cli.py --help
Self-test: ./run.sh --self-test is not supported; use python3 app/src/cli.py self-test

Requirements: Python 3.9+, Tkinter, and OpenSSL 3.x.
The core signer runs offline. Optional aggregate statistics are disabled by default and require explicit opt-in in Settings.
The optional statistics event contains only event=cms_sign and app_version. No files, names, paths, certificates, keys, passwords, device IDs or IP addresses are sent.

Supported exports include public DER .cer (CER-only mode), password-protected .p12 identities, CMS/PKCS#7 signatures and XML .mobileconfig profiles.

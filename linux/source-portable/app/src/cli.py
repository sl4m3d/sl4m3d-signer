#!/usr/bin/env python3
"""Offline command-line interface shared with the Android Termux package."""
import argparse
import getpass
import sys
from pathlib import Path

import crypto_core as core


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sl4m3d-signer", description="Offline X.509, CMS and mobileconfig utility")
    parser.add_argument("--version", action="version", version=f"sl4m3d Signer {core.APP_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    make = sub.add_parser("make-cert", help="Create a .cer certificate and password-protected .p12 identity")
    make.add_argument("--name", required=True)
    make.add_argument("--days", type=int, default=365)
    make.add_argument("--algorithm", choices=("RSA 2048", "RSA 3072", "RSA 4096", "EC P-256", "EC P-384"), default="RSA 3072")
    make.add_argument("--output-dir", type=Path, default=Path.cwd())
    make.add_argument("--ca", action="store_true", help="Create a local CA certificate")
    make.add_argument("--overwrite", action="store_true")
    make.add_argument("--cer-only", action="store_true", help="Export only the public DER .cer; no private key or P12 is kept")

    sign = sub.add_parser("sign", help="Create and verify an attached CMS signature")
    sign.add_argument("file", type=Path)
    sign.add_argument("--identity", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    sign.add_argument("--overwrite", action="store_true")

    verify = sub.add_parser("verify", help="Verify CMS content integrity and extract the original content")
    verify.add_argument("signature", type=Path)
    verify.add_argument("--output", type=Path, required=True)
    verify.add_argument("--content", type=Path, help="Original content for detached CMS signatures")
    verify.add_argument("--overwrite", action="store_true")

    inspect = sub.add_parser("inspect", help="Inspect CER/CRT/PEM/DER/P12/PFX")
    inspect.add_argument("file", type=Path)

    mobile = sub.add_parser("make-mobileconfig", help="Create a local XML Apple configuration profile")
    mobile.add_argument("--name", required=True)
    mobile.add_argument("--identifier", required=True)
    mobile.add_argument("--organization", default="sl4m3d")
    mobile.add_argument("--output", type=Path, required=True)
    mobile.add_argument("--webclip-label")
    mobile.add_argument("--webclip-url")
    mobile.add_argument("--wifi", action="store_true")
    mobile.add_argument("--sign-with", type=Path)
    mobile.add_argument("--overwrite", action="store_true")

    sub.add_parser("self-test", help="Run local offline cryptography tests")
    args = parser.parse_args(argv)

    try:
        if args.command == "make-cert":
            password = "" if args.cer_only else getpass.getpass("New .p12 password (minimum 8 characters): ")
            cert, p12 = core.create_certificate(args.name, args.days, args.algorithm, args.output_dir, password, args.ca, args.overwrite, export_identity=not args.cer_only)
            print(f"CER: {cert}")
            if p12 is not None:
                print(f"P12: {p12}\nThe certificate and private key were validated.")
            else:
                print("CER-only export: the private key was temporary and has not been retained.")
        elif args.command == "sign":
            password = getpass.getpass("P12/PFX password: ")
            result = core.sign_file(args.file, args.identity, password, args.output, overwrite=args.overwrite)
            print(f"Signed and verified: {result}")
        elif args.command == "verify":
            result, note = core.verify_cms(args.signature, args.output, args.content, overwrite=args.overwrite)
            print(f"Verified: {result}\n{note}")
        elif args.command == "inspect":
            password = getpass.getpass("P12/PFX password (leave blank for public certificate): ") if args.file.suffix.lower() in (".p12", ".pfx") else None
            print(core.inspect_certificate(args.file, password))
        elif args.command == "make-mobileconfig":
            wifi_password = getpass.getpass("WPA/WPA2 password (8-63 bytes): ") if args.wifi else None
            wifi_ssid = input("Wi-Fi SSID: ").strip() if args.wifi else None
            result = core.make_mobileconfig(args.output, args.name, args.identifier, args.organization, args.webclip_label, args.webclip_url, wifi_ssid, wifi_password, overwrite=args.overwrite)
            if args.sign_with:
                password = getpass.getpass("Signing identity password: ")
                signed = result.with_name(result.stem + ".signed.mobileconfig")
                core.sign_file(result, args.sign_with, password, signed, overwrite=args.overwrite)
                print(f"Profile: {result}\nSigned profile: {signed}")
            else:
                print(f"Profile: {result}\nUnsigned profile. Sign it before distribution when required.")
        elif args.command == "self-test":
            from selftest import run_self_tests
            for item in run_self_tests():
                print(f"PASS  {item}")
            print("All self-tests passed.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

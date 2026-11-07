"""Small, fully local diagnostic suite used by the GUI and CLI."""
from __future__ import annotations

import hashlib
import plistlib
import tempfile
from pathlib import Path

import crypto_core as core


def run_self_tests():
    passed = []
    with tempfile.TemporaryDirectory(prefix="sl4m3d-selftest-") as raw:
        root = Path(raw)
        for algorithm in ("RSA 2048", "EC P-256"):
            out = root / algorithm.replace(" ", "-")
            out.mkdir()
            cert, p12 = core.create_certificate("sl4m3d selftest", 2, algorithm, out, "selftest-password", overwrite=False)
            assert p12 is not None and cert.suffix == ".cer" and p12.suffix == ".p12"
            assert cert.read_bytes()[0] == 0x30  # DER ASN.1 SEQUENCE
            detail = core.inspect_certificate(cert)
            assert "subject=" in detail.lower()
            identity_detail = core.inspect_certificate(p12, "selftest-password")
            assert "privater schlüssel vorhanden" in identity_detail.lower()
            with core._safe_temp() as tmp:
                try:
                    core.extract_identity(p12, "wrong-password", tmp)
                except core.CryptoError:
                    pass
                else:
                    raise AssertionError("Wrong P12 password was accepted")
            source = out / "payload.mobileconfig"
            source.write_bytes(b"<?xml version=\"1.0\"?><plist><dict><key>Test</key><true/></dict></plist>")
            signature = out / "payload.signed.p7m"
            core.sign_file(source, p12, "selftest-password", signature)
            recovered = out / "recovered.bin"
            core.verify_cms(signature, recovered)
            assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(recovered.read_bytes()).digest()
            tampered = out / "tampered.p7m"
            corrupt = bytearray(signature.read_bytes())
            signed_content_offset = corrupt.find(source.read_bytes())
            assert signed_content_offset >= 0, "Attached CMS content could not be located for tamper test"
            corrupt[signed_content_offset] ^= 0x01
            tampered.write_bytes(corrupt)
            try:
                core.verify_cms(tampered, out / "tampered-output.bin")
            except core.CryptoError:
                pass
            else:
                raise AssertionError("Tampered CMS signature was accepted")
            try:
                core.create_certificate("sl4m3d selftest", 2, algorithm, out, "selftest-password", overwrite=False)
            except core.CryptoError:
                pass
            else:
                raise AssertionError("Existing certificate outputs were overwritten without consent")
            passed.append(f"{algorithm} DER certificate, P12 password/key validation, CMS integrity/tamper/overwrite checks")
        cer_only_dir = root / "cer-only"
        cer_only_dir.mkdir()
        cer_only, identity = core.create_certificate("CER only test", 30, "RSA 2048", cer_only_dir, export_identity=False)
        assert identity is None and cer_only.exists() and cer_only.suffix == ".cer"
        assert not (cer_only_dir / "CER_only_test.p12").exists()
        core.inspect_certificate(cer_only)
        passed.append("CER-only export leaves no private key or P12 file")
        # Profile XML schema and payload test.
        profile = root / "test.mobileconfig"
        core.make_mobileconfig(profile, "Selftest", "is.great.sl4m3d.selftest", "sl4m3d", "Test", "https://example.com", "TestNetwork", "test-password")
        obj = plistlib.loads(profile.read_bytes())
        assert obj["PayloadType"] == "Configuration" and len(obj["PayloadContent"]) == 2
        passed.append(".mobileconfig XML plist and Web Clip/Wi-Fi payload validation")

        # Exercise stream-safe file hashing and CMS operations with a larger payload.
        large = root / "large-payload.bin"
        large.write_bytes((b"sl4m3d-offline-test\x00" * 32768))
        identity_dir = root / "RSA-2048"
        p12 = identity_dir / "sl4m3d_selftest.p12"
        signed = root / "large-payload.p7m"
        extracted = root / "large-recovered.bin"
        core.sign_file(large, p12, "selftest-password", signed)
        core.verify_cms(signed, extracted)
        assert hashlib.sha256(large.read_bytes()).digest() == hashlib.sha256(extracted.read_bytes()).digest()
        passed.append("Large binary payload signing and verification")
    return passed

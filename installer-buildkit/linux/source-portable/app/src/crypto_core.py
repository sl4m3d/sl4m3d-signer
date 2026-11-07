"""Local-only certificate, CMS and Apple configuration-profile operations.

No network access, analytics, telemetry, or remote storage is used by this module.
"""
from __future__ import annotations

import hashlib
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

APP_VERSION = "1.2.0"


def app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        root = base / "sl4m3d" / "Signer"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        root = base / "sl4m3d-signer"
    root.mkdir(parents=True, exist_ok=True)
    try:
        if os.name != "nt":
            os.chmod(root, 0o700)
    except OSError:
        pass
    return root


DATA_DIR = app_data_dir()
LIBRARY_DIR = DATA_DIR / "library"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
try:
    if os.name != "nt":
        os.chmod(LIBRARY_DIR, 0o700)
except OSError:
    pass


class CryptoError(RuntimeError):
    """Raised when an OpenSSL operation or validation fails."""


def openssl_path() -> str:
    """Resolve system or bundled OpenSSL without relying on a GUI launch PATH."""
    env_override = os.environ.get("SL4M3D_OPENSSL", "").strip()
    candidates: list[Path] = []
    if env_override:
        candidates.append(Path(env_override).expanduser())
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)))
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parent)
    for root in roots:
        for relative in (
            Path("openssl/bin/openssl"), Path("openssl/bin/openssl.exe"),
            Path("openssl/openssl"), Path("openssl/openssl.exe"),
            Path("bin/openssl"), Path("bin/openssl.exe"),
        ):
            candidates.append(root / relative)
    if sys.platform == "darwin":
        executable_dir = Path(sys.executable).resolve().parent
        candidates.extend((
            executable_dir.parent / "Frameworks" / "openssl" / "bin" / "openssl",
            executable_dir.parent / "Resources" / "openssl" / "bin" / "openssl",
        ))
    # Finder-launched macOS apps often receive a reduced PATH without Homebrew.
    if sys.platform == "darwin":
        candidates.extend((Path("/opt/homebrew/bin/openssl"), Path("/usr/local/bin/openssl"), Path("/usr/bin/openssl")))
    for candidate in candidates:
        try:
            if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK)):
                return str(candidate.resolve())
        except OSError:
            continue
    candidate = shutil.which("openssl")
    if candidate:
        return candidate
    raise CryptoError(
        "OpenSSL 3 wurde nicht gefunden. Nutze das gebündelte OpenSSL oder installiere OpenSSL 3 und starte sl4m3d Signer erneut."
    )


def run_openssl(args, password: Optional[str] = None, timeout: int = 300) -> bytes:
    """Run OpenSSL without a shell and never place passwords in argv."""
    if password is not None and ("\n" in password or "\r" in password or "\x00" in password):
        raise CryptoError("Passwörter dürfen keine Zeilenumbrüche oder Nullbytes enthalten.")
    command = [openssl_path(), *(str(x) for x in args)]
    input_data = (password + "\n").encode("utf-8") if password is not None else None
    env = os.environ.copy()
    executable_parent = Path(command[0]).resolve().parent
    module_candidates = (
        executable_parent / "ossl-modules",
        executable_parent.parent / "lib" / "ossl-modules",
        executable_parent.parent / "ossl-modules",
    )
    for bundled_modules in module_candidates:
        if bundled_modules.is_dir():
            env.setdefault("OPENSSL_MODULES", str(bundled_modules))
            break
    config_candidates = (
        executable_parent / "openssl.cnf",
        executable_parent.parent / "ssl" / "openssl.cnf",
        executable_parent.parent / "openssl.cnf",
    )
    for bundled_config in config_candidates:
        if bundled_config.is_file():
            env.setdefault("OPENSSL_CONF", str(bundled_config))
            break
    try:
        proc = subprocess.run(
            command,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            close_fds=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise CryptoError(f"OpenSSL hat das Zeitlimit von {timeout} Sekunden überschritten.") from exc
    except OSError as exc:
        raise CryptoError(f"OpenSSL konnte nicht gestartet werden: {exc}") from exc
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        if "mac verify error" in detail.lower() or "maybe wrong password" in detail.lower():
            detail = "PKCS#12-Passwort falsch oder Datei beschädigt."
        raise CryptoError(detail or f"OpenSSL-Fehler (Exit-Code {proc.returncode}).")
    return proc.stdout


def _safe_temp(parent: Path = DATA_DIR, prefix: str = "work-"):
    folder = Path(tempfile.mkdtemp(prefix=prefix, dir=str(parent)))
    try:
        if os.name != "nt":
            os.chmod(folder, 0o700)
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


# Expose as a context manager without a dependency on third-party packages.
from contextlib import contextmanager
_safe_temp = contextmanager(_safe_temp)


def _public_key_from_cert(cert_path: Path) -> bytes:
    try:
        return run_openssl(["x509", "-in", cert_path, "-pubkey", "-noout"]).strip()
    except CryptoError:
        return run_openssl(["x509", "-inform", "DER", "-in", cert_path, "-pubkey", "-noout"]).strip()


def _public_key_from_private(key_path: Path) -> bytes:
    return run_openssl(["pkey", "-in", key_path, "-pubout"]).strip()


def ensure_matching_pair(cert_path: Path, key_path: Path) -> None:
    cert_pub = _public_key_from_cert(Path(cert_path))
    key_pub = _public_key_from_private(Path(key_path))
    if not cert_pub or cert_pub != key_pub:
        raise CryptoError("Zertifikat und privater Schlüssel gehören nicht zusammen.")


def _pkcs12_args(extra: list[str], source: Path, password: str, dest: Path) -> None:
    """Import P12/PFX, retrying with OpenSSL 3 legacy provider for older files."""
    base = ["pkcs12", "-in", source, *extra, "-out", dest, "-passin", "stdin"]
    try:
        run_openssl(base, password=password)
    except CryptoError as first_error:
        try:
            run_openssl(["pkcs12", "-legacy", "-in", source, *extra, "-out", dest, "-passin", "stdin"], password=password)
        except CryptoError:
            raise first_error


def extract_identity(p12_path: Path, password: str, folder: Path) -> tuple[Path, Path]:
    """Extract cert/key into a caller-owned private temp folder and validate match."""
    p12_path = Path(p12_path).expanduser().resolve(strict=True)
    if p12_path.suffix.lower() not in (".p12", ".pfx"):
        raise CryptoError("Erwartet wird eine .p12- oder .pfx-Datei mit privatem Schlüssel.")
    if not p12_path.is_file():
        raise CryptoError("Die Identitätsdatei ist keine reguläre Datei.")
    cert = folder / "identity-cert.pem"
    key = folder / "identity-key.pem"
    _pkcs12_args(["-clcerts", "-nokeys"], p12_path, password, cert)
    _pkcs12_args(["-nocerts", "-nodes"], p12_path, password, key)
    if not cert.exists() or cert.stat().st_size == 0 or not key.exists() or key.stat().st_size == 0:
        raise CryptoError("Die PKCS#12-Datei enthält kein vollständiges Zertifikat-Schlüssel-Paar.")
    try:
        if os.name != "nt":
            os.chmod(key, 0o600)
    except OSError:
        pass
    ensure_matching_pair(cert, key)
    return cert, key


def _safe_stem(value: str) -> str:
    result = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value).strip("_")
    return (result[:64] or "certificate")


def _escape_conf_value(value: str) -> str:
    if not value or any(ord(c) < 32 or c in "\r\n\x00" for c in value):
        raise CryptoError("Der Zertifikatsname ist leer oder enthält ungültige Steuerzeichen.")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _commit_pair(temp_cert: Path, temp_p12: Path, cert_out: Path, p12_out: Path, overwrite: bool) -> None:
    """Replace both outputs transactionally; preserve existing files on failure."""
    outputs = [cert_out, p12_out]
    if any(p.exists() for p in outputs) and not overwrite:
        raise CryptoError("Eine Zieldatei existiert bereits. Bestätige das Überschreiben.")
    staging: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    try:
        for final, source in ((cert_out, temp_cert), (p12_out, temp_p12)):
            stage = final.with_name(final.name + ".new-" + uuid.uuid4().hex)
            shutil.copy2(source, stage)
            staging[final] = stage
        for final in outputs:
            if final.exists():
                backup = final.with_name(final.name + ".backup-" + uuid.uuid4().hex)
                os.replace(final, backup)
                backups[final] = backup
        for final in outputs:
            os.replace(staging[final], final)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    except Exception:
        for final in outputs:
            if final in backups and backups[final].exists():
                try:
                    final.unlink(missing_ok=True)
                    os.replace(backups[final], final)
                except OSError:
                    pass
        raise
    finally:
        for path in (*staging.values(), *backups.values()):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def _commit_single(source: Path, final: Path, overwrite: bool) -> None:
    if final.exists() and not overwrite:
        raise CryptoError("Die Zieldatei existiert bereits. Bestätige das Überschreiben ausdrücklich.")
    staged = final.with_name(final.name + ".new-" + uuid.uuid4().hex)
    try:
        shutil.copy2(source, staged)
        if os.name != "nt":
            os.chmod(staged, 0o644)
        os.replace(staged, final)
    finally:
        staged.unlink(missing_ok=True)


def create_certificate(
    common_name: str,
    days: int,
    algorithm: str,
    export_dir: Path,
    password: str = "",
    is_ca: bool = False,
    overwrite: bool = False,
    export_identity: bool = True,
) -> tuple[Path, Optional[Path]]:
    """Create a self-signed X.509 certificate, optionally with a matching password-protected P12."""
    common_name = common_name.strip()
    if not common_name:
        raise CryptoError("Der Common Name darf nicht leer sein.")
    if not isinstance(days, int) or not 1 <= days <= 3650:
        raise CryptoError("Die Gültigkeit muss zwischen 1 und 3650 Tagen liegen.")
    if export_identity and (len(password) < 8 or "\n" in password or "\r" in password or "\x00" in password):
        raise CryptoError("Das P12-Passwort muss mindestens 8 Zeichen haben und darf keine Zeilenumbrüche enthalten.")
    if algorithm not in ("RSA 2048", "RSA 3072", "RSA 4096", "EC P-256", "EC P-384"):
        raise CryptoError("Nicht unterstützter Schlüsselalgorithmus.")
    export_dir = Path(export_dir).expanduser().resolve(strict=True)
    if not export_dir.is_dir():
        raise CryptoError("Der Exportpfad ist kein Ordner.")
    stem = _safe_stem(common_name)
    cert_out = export_dir / (stem + ".cer")
    p12_out = export_dir / (stem + ".p12") if export_identity else None
    outputs = [cert_out] + ([p12_out] if p12_out is not None else [])
    if any(path.exists() for path in outputs) and not overwrite:
        raise CryptoError("Eine Zieldatei existiert bereits. Bestätige das Überschreiben ausdrücklich.")
    with _safe_temp(export_dir, ".signer-create-") as temp:
        key = temp / "private-key.pem"
        cert_pem = temp / "certificate.pem"
        p12 = temp / "identity.p12"
        check_cert = temp / "check-cert.pem"
        check_key = temp / "check-key.pem"
        config = temp / "openssl.cnf"
        if algorithm.startswith("RSA"):
            bits = int(algorithm.split()[1])
            run_openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", f"rsa_keygen_bits:{bits}", "-out", key])
        else:
            curve = "prime256v1" if "256" in algorithm else "secp384r1"
            run_openssl(["genpkey", "-algorithm", "EC", "-pkeyopt", f"ec_paramgen_curve:{curve}", "-out", key])
        if os.name != "nt":
            os.chmod(key, 0o600)
        if is_ca:
            extensions = "basicConstraints = critical,CA:TRUE,pathlen:0\nkeyUsage = critical,keyCertSign,cRLSign,digitalSignature\nsubjectKeyIdentifier = hash\nauthorityKeyIdentifier = keyid:always\n"
        else:
            extensions = "basicConstraints = critical,CA:FALSE\nkeyUsage = critical,digitalSignature,keyEncipherment\nextendedKeyUsage = clientAuth,emailProtection\nsubjectKeyIdentifier = hash\nauthorityKeyIdentifier = keyid:always\n"
        config.write_text(
            "[ req ]\nprompt = no\ndistinguished_name = dn\nx509_extensions = extensions\n"
            "[ dn ]\nCN = \"" + _escape_conf_value(common_name) + "\"\n"
            "[ extensions ]\n" + extensions,
            encoding="utf-8",
        )
        run_openssl(["req", "-new", "-x509", "-sha256", "-days", str(days), "-key", key, "-out", cert_pem, "-config", config])
        ensure_matching_pair(cert_pem, key)
        cert_der = temp / "certificate.cer"
        run_openssl(["x509", "-in", cert_pem, "-outform", "DER", "-out", cert_der])
        if export_identity and p12_out is not None:
            run_openssl(["pkcs12", "-export", "-inkey", key, "-in", cert_pem, "-out", p12, "-passout", "stdin"], password=password)
            if os.name != "nt":
                os.chmod(p12, 0o600)
            _pkcs12_args(["-clcerts", "-nokeys"], p12, password, check_cert)
            _pkcs12_args(["-nocerts", "-nodes"], p12, password, check_key)
            ensure_matching_pair(check_cert, check_key)
            _commit_pair(cert_der, p12, cert_out, p12_out, overwrite=overwrite)
        else:
            _commit_single(cert_der, cert_out, overwrite=overwrite)
    return cert_out, p12_out


def _hash_file(path: Path) -> bytes:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.digest()


def sign_file(source_path: Path, p12_path: Path, password: str, target_path: Path, overwrite: bool = False) -> Path:
    source = Path(source_path).expanduser().resolve(strict=True)
    identity = Path(p12_path).expanduser().resolve(strict=True)
    target = Path(target_path).expanduser().absolute()
    if not source.is_file() or not identity.is_file():
        raise CryptoError("Eingabedatei oder Identität ist keine reguläre Datei.")
    if source == target.resolve(strict=False):
        raise CryptoError("Die Signatur darf die Originaldatei nicht überschreiben.")
    if source == identity:
        raise CryptoError("Dokument und Signaturidentität müssen unterschiedliche Dateien sein.")
    if target.exists() and not overwrite:
        raise CryptoError("Die Ausgabedatei existiert bereits. Bestätige das Überschreiben ausdrücklich.")
    target.parent.mkdir(parents=True, exist_ok=True)
    before_hash = _hash_file(source)
    with _safe_temp(DATA_DIR, "sign-") as temp:
        cert, key = extract_identity(identity, password, temp)
        signed = temp / "signed.der"
        recovered = temp / "verified-payload.bin"
        run_openssl(["cms", "-sign", "-binary", "-in", source, "-signer", cert, "-inkey", key, "-outform", "DER", "-out", signed, "-nodetach"])
        run_openssl(["cms", "-verify", "-binary", "-inform", "DER", "-in", signed, "-noverify", "-out", recovered])
        if before_hash != _hash_file(recovered):
            raise CryptoError("CMS wurde erzeugt, aber die Rückprüfung ergab einen anderen Dateiinhalt.")
        # Write next to the target and atomically replace it only after verification.
        staged = target.with_name(target.name + ".new-" + uuid.uuid4().hex)
        try:
            shutil.copyfile(signed, staged)
            os.replace(staged, target)
        finally:
            staged.unlink(missing_ok=True)
    return target


def verify_cms(signature_path: Path, output_path: Path, detached_content: Optional[Path] = None, overwrite: bool = False) -> tuple[Path, str]:
    signature = Path(signature_path).expanduser().resolve(strict=True)
    output = Path(output_path).expanduser().absolute()
    if not signature.is_file():
        raise CryptoError("Die Signaturdatei wurde nicht gefunden.")
    content_path = Path(detached_content).expanduser().resolve(strict=True) if detached_content else None
    if output.resolve(strict=False) == signature or (content_path is not None and output.resolve(strict=False) == content_path):
        raise CryptoError("Der extrahierte Inhalt darf weder Signatur noch Originaldatei überschreiben.")
    if output.exists() and not overwrite:
        raise CryptoError("Die Ausgabedatei existiert bereits. Bestätige das Überschreiben ausdrücklich.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with _safe_temp(DATA_DIR, "verify-") as temp:
        recovered = temp / "recovered.bin"
        base = ["cms", "-verify", "-binary", "-noverify", "-in", signature]
        try:
            run_openssl([*base, "-inform", "DER", "-out", recovered, *( ["-content", content_path] if content_path else [])])
        except CryptoError as der_error:
            try:
                run_openssl([*base, "-inform", "PEM", "-out", recovered, *( ["-content", content_path] if content_path else [])])
            except CryptoError:
                raise der_error
        staged = output.with_name(output.name + ".new-" + uuid.uuid4().hex)
        try:
            shutil.copyfile(recovered, staged)
            os.replace(staged, output)
        finally:
            staged.unlink(missing_ok=True)
        return output, "CMS-Inhalt erfolgreich geprüft. Die Zertifikats-Vertrauenskette wurde dabei bewusst nicht als vertrauenswürdig vorausgesetzt."


def inspect_certificate(path: Path, password: Optional[str] = None) -> str:
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise CryptoError("Die Zertifikatsdatei wurde nicht gefunden.")
    notes = []
    with _safe_temp(DATA_DIR, "inspect-") as temp:
        cert = source
        if source.suffix.lower() in (".p12", ".pfx"):
            if password is None:
                raise CryptoError("Für eine .p12/.pfx-Datei wird das Passwort benötigt.")
            cert, key = extract_identity(source, password, temp)
            notes.append("PKCS#12: privater Schlüssel vorhanden; Zertifikat und Schlüssel stimmen überein.")
        args = ["x509", "-in", cert, "-noout", "-subject", "-issuer", "-serial", "-dates", "-fingerprint", "-sha256"]
        try:
            detail = run_openssl(args).decode("utf-8", errors="replace")
        except CryptoError:
            detail = run_openssl(["x509", "-inform", "DER", "-in", cert, "-noout", "-subject", "-issuer", "-serial", "-dates", "-fingerprint", "-sha256"]).decode("utf-8", errors="replace")
            notes.append("Öffentliches DER-Zertifikat: Es enthält keinen privaten Schlüssel und kann nicht allein signieren.")
        try:
            run_openssl(["x509", "-in", cert, "-checkend", "0", "-noout"])
            notes.append("Gültigkeitszeitraum: nicht abgelaufen (lokale Zeitprüfung).")
        except CryptoError:
            notes.append("WARNUNG: Zertifikat ist abgelaufen oder beginnt erst in der Zukunft.")
        return f"Datei: {source}\nGröße: {source.stat().st_size:,} Bytes\n\n{detail}\n" + "\n".join(notes)


def make_mobileconfig(
    output_path: Path,
    profile_name: str,
    identifier: str,
    organization: str = "sl4m3d",
    webclip_label: Optional[str] = None,
    webclip_url: Optional[str] = None,
    wifi_ssid: Optional[str] = None,
    wifi_password: Optional[str] = None,
    overwrite: bool = False,
) -> Path:
    """Create an unsigned Apple configuration profile as an XML plist."""
    profile_name = profile_name.strip()
    identifier = identifier.strip()
    organization = organization.strip() or "sl4m3d"
    if not profile_name or not identifier:
        raise CryptoError("Profilname und eindeutige Kennung sind erforderlich.")
    if any(ord(c) < 32 for c in profile_name + identifier + organization):
        raise CryptoError("Metadaten dürfen keine Steuerzeichen enthalten.")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", identifier):
        raise CryptoError("Die Profilkennung muss eine Kennung im Reverse-DNS-Format sein, z. B. is.example.profile.")
    payloads = []
    if webclip_url or webclip_label:
        if not webclip_url or not webclip_label:
            raise CryptoError("Für einen Web Clip müssen Titel und URL ausgefüllt werden.")
        from urllib.parse import urlparse
        parsed = urlparse(webclip_url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise CryptoError("Die Web-Clip-URL muss mit http:// oder https:// beginnen und einen Host enthalten.")
        payloads.append({
            "PayloadType": "com.apple.webClip.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": identifier + ".webclip",
            "PayloadUUID": str(uuid.uuid4()).upper(),
            "PayloadDisplayName": "Web Clip",
            "Label": webclip_label,
            "URL": webclip_url,
            "IsRemovable": True,
            "FullScreen": False,
        })
    if wifi_ssid:
        if "\x00" in wifi_ssid or len(wifi_ssid.encode("utf-8")) > 32:
            raise CryptoError("Die WLAN-SSID darf höchstens 32 UTF-8-Bytes enthalten.")
        if not wifi_password or not 8 <= len(wifi_password.encode("utf-8")) <= 63:
            raise CryptoError("Für WPA/WPA2-WLAN-Profile muss das Passwort 8 bis 63 Bytes lang sein.")
        payloads.append({
            "PayloadType": "com.apple.wifi.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": identifier + ".wifi",
            "PayloadUUID": str(uuid.uuid4()).upper(),
            "PayloadDisplayName": "WLAN",
            "SSID_STR": wifi_ssid,
            "HIDDEN_NETWORK": False,
            "AutoJoin": True,
            "EncryptionType": "WPA",
            "Password": wifi_password,
        })
    profile = {
        "PayloadContent": payloads,
        "PayloadDescription": "Lokal erstelltes Konfigurationsprofil.",
        "PayloadDisplayName": profile_name,
        "PayloadIdentifier": identifier,
        "PayloadOrganization": organization,
        "PayloadRemovalDisallowed": False,
        "PayloadType": "Configuration",
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadVersion": 1,
    }
    target = Path(output_path).expanduser().absolute()
    if target.exists() and not overwrite:
        raise CryptoError("Die Profildatei existiert bereits. Bestätige das Überschreiben ausdrücklich.")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=False)
    # Verify our own serialization before committing the file.
    parsed = plistlib.loads(raw)
    if parsed.get("PayloadType") != "Configuration" or parsed.get("PayloadUUID") != profile["PayloadUUID"]:
        raise CryptoError("Interne Profilprüfung fehlgeschlagen.")
    staged = target.with_name(target.name + ".new-" + uuid.uuid4().hex)
    try:
        staged.write_bytes(raw)
        if os.name != "nt":
            os.chmod(staged, 0o600)
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)
    return target


def openssl_version() -> str:
    return run_openssl(["version"]).decode("utf-8", errors="replace").strip()

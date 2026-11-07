#!/usr/bin/env python3
"""sl4m3d Signer v1.2 - offline-first desktop application."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import crypto_core as core
import stats_client

APP_NAME = "sl4m3d Signer"
APP_VERSION = core.APP_VERSION

BG = "#0a0e12"
PANEL = "#111920"
PANEL2 = "#151f27"
BORDER = "#26343d"
FG = "#d8e3e8"
MUTED = "#84929a"
ACCENT = "#ffb454"
GREEN = "#8bd5a5"

CHANGELOG = [
    ("1.2.0", "07.11.2026", "Stability & Release Update", [
        "Alle Seiten sind jetzt vertikal scrollbar; Maus, Trackpad, Touch und Tastatur werden unterstützt.",
        "CER-only-Export ergänzt: öffentliches DER-Zertifikat ohne gespeicherten privaten Schlüssel; optional weiterhin CER + P12.",
        "Update-Log und Diagnose sind über die scrollbare Navigation zuverlässig erreichbar.",
        "Anonyme Signaturzählung ist standardmäßig deaktiviert und nur nach ausdrücklicher Zustimmung aktiv.",
        "Offline-Warteschlange sendet ausschließlich Eventtyp und App-Version, niemals Dateiinhalte oder Schlüsselmaterial.",
    ]),
    ("1.1.0", "06.11.2026", "Mega-Update", [
        "Komplett offline: Telemetrie, Supabase-Aufrufe und Netzwerkabhängigkeiten entfernt.",
        "Neuer .cer- und .p12-Zertifikatsgenerator mit RSA 2048/3072/4096 und EC P-256/P-384.",
        "Neuer .mobileconfig-Generator für Profil-Metadaten, Web Clips und WPA/WPA2-WLAN-Profile.",
        "CMS/PKCS#7-Signaturen nach dem Signieren automatisch geprüft; separater Signatur-Prüfer ergänzt.",
        "Integrierter Dateimanager, Stapel-Signierung, Zertifikatsprüfung, Diagnosen und Update-Log.",
        "Verbesserte temporäre Dateisicherheit, atomare Ausgaben, P12-Legacy-Import und große Dateien.",
    ]),
]


def open_path(path: Path) -> None:
    path = Path(path).expanduser()
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], close_fds=True)
        else:
            command = shutil.which("xdg-open")
            if not command:
                raise RuntimeError("xdg-open wurde nicht gefunden.")
            subprocess.Popen([command, str(path)], close_fds=True)
    except Exception as exc:
        messagebox.showerror("Öffnen fehlgeschlagen", str(exc))


class SignerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1100x790")
        self.root.minsize(860, 650)
        self.root.configure(bg=BG)
        self.current_dir = Path.home()
        self.sign_source_var = tk.StringVar()
        self.sign_p12_var = tk.StringVar()
        self.make_name_var = tk.StringVar(value="sl4m3d local certificate")
        self.make_days_var = tk.StringVar(value="365")
        self.make_password_var = tk.StringVar()
        self.make_identity_var = tk.BooleanVar(value=True)
        self.make_algorithm_var = tk.StringVar(value="RSA 3072")
        self.make_ca_var = tk.BooleanVar(value=False)
        self.mobile_name_var = tk.StringVar(value="sl4m3d Configuration")
        self.mobile_identifier_var = tk.StringVar(value="is.great.sl4m3d.profile")
        self.mobile_org_var = tk.StringVar(value="sl4m3d")
        self.mobile_webclip_var = tk.BooleanVar(value=False)
        self.mobile_webclip_label_var = tk.StringVar(value="sl4m3d")
        self.mobile_webclip_url_var = tk.StringVar(value="https://sl4m3d.xo.je")
        self.mobile_wifi_var = tk.BooleanVar(value=False)
        self.mobile_wifi_ssid_var = tk.StringVar()
        self.mobile_wifi_password_var = tk.StringVar()
        self.mobile_sign_var = tk.BooleanVar(value=False)
        self.mobile_p12_var = tk.StringVar()
        self.mobile_output_var = tk.StringVar()
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._configure_style()
        icon_roots = [HERE.parent, Path(getattr(sys, "_MEIPASS", HERE)), Path(sys.executable).resolve().parent]
        if sys.platform == "darwin":
            icon_roots.append(Path(sys.executable).resolve().parent.parent / "Resources")
        icon_path = next((root / "assets" / "icon.png" for root in icon_roots if (root / "assets" / "icon.png").is_file()), None)
        try:
            self.icon_image = tk.PhotoImage(file=str(icon_path)) if icon_path else None
            if self.icon_image:
                self.root.iconphoto(True, self.icon_image)
        except Exception:
            self.icon_image = None
        # One scrollable document surface is shared by every screen.
        self.shell = ttk.Frame(root, style="Root.TFrame")
        self.shell.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.shell, bg=BG, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self.shell, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.container = ttk.Frame(self.canvas, padding=28, style="Root.TFrame")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.container, anchor="nw")
        self.container.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._sync_canvas_width)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_mousewheel, add="+")
        self.root.bind_all("<Prior>", lambda event: self._scroll_key(event, -1), add="+")
        self.root.bind_all("<Next>", lambda event: self._scroll_key(event, 1), add="+")
        self.root.bind_all("<Home>", self._scroll_home, add="+")
        self.root.bind_all("<End>", self._scroll_end, add="+")
        self.show_home()

    def _configure_style(self):
        self.style.configure("Root.TFrame", background=BG)
        self.style.configure("TFrame", background=BG)
        self.style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        self.style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        self.style.configure("Title.TLabel", background=BG, foreground=FG, font=("Segoe UI", 25, "bold"))
        self.style.configure("Section.TLabel", background=BG, foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        self.style.configure("TEntry", fieldbackground=PANEL2, foreground=FG, insertcolor=FG, bordercolor=BORDER, padding=8)
        self.style.configure("TCombobox", fieldbackground=PANEL2, foreground=FG, background=PANEL2, arrowcolor=FG, padding=7)
        self.style.configure("TCheckbutton", background=BG, foreground=FG)
        self.style.map("TCheckbutton", background=[("active", BG)], foreground=[("active", FG)])
        self.style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=28, bordercolor=BORDER)
        self.style.configure("Treeview.Heading", background=PANEL2, foreground=ACCENT, relief="flat")
        self.style.configure("Accent.TButton", background=ACCENT, foreground="#101418", padding=(17, 10), borderwidth=0, font=("Segoe UI", 9, "bold"))
        self.style.map("Accent.TButton", background=[("active", "#ffc477"), ("disabled", "#6f604c")])
        self.style.configure("Dark.TButton", background=PANEL2, foreground=FG, padding=(12, 9), borderwidth=1, relief="flat")
        self.style.map("Dark.TButton", background=[("active", "#202d36")])

    def _update_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_canvas_width(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=max(1, event.width))
        self._update_scrollregion()

    def _pointer_inside(self, widget):
        current = widget
        while current is not None:
            if current == self.shell or current == self.canvas:
                return True
            try:
                current = current.master
            except Exception:
                return False
        return False

    def _on_mousewheel(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget is None or not self._pointer_inside(widget):
            return
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = getattr(event, "delta", 0)
            units = -int(delta / 120) if abs(delta) >= 120 else -int(delta)
        if not units:
            units = -1 if getattr(event, "delta", 0) > 0 else 1
        # Nested text/tree widgets keep their own scroll behavior when they have content.
        try:
            if widget.winfo_class() in ("Text", "Treeview") and hasattr(widget, "yview_scroll"):
                first, last = widget.yview()
                if (units < 0 and first > 0.0) or (units > 0 and last < 1.0):
                    widget.yview_scroll(units, "units")
                    return "break"
        except Exception:
            pass
        self.canvas.yview_scroll(units, "units")
        return "break"

    def _scroll_key(self, event, direction):
        if event.widget.winfo_class() in ("Entry", "TEntry", "Text", "TCombobox"):
            return
        self.canvas.yview_scroll(direction * 8, "units")
        return "break"

    def _scroll_home(self, event):
        if event.widget.winfo_class() in ("Entry", "TEntry", "Text", "TCombobox"):
            return
        self.canvas.yview_moveto(0)
        return "break"

    def _scroll_end(self, event):
        if event.widget.winfo_class() in ("Entry", "TEntry", "Text", "TCombobox"):
            return
        self.canvas.yview_moveto(1)
        return "break"

    def clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()
        self.canvas.yview_moveto(0)
        self.root.after_idle(self._update_scrollregion)

    def _record_signature_event(self):
        if stats_client.is_enabled():
            threading.Thread(target=stats_client.record_successful_signature, daemon=True).start()

    def header(self, title: str, subtitle: str, back: bool = True):
        top = ttk.Frame(self.container)
        top.pack(fill="x", pady=(0, 18))
        if back:
            ttk.Button(top, text="←  Übersicht", style="Dark.TButton", command=self.show_home).pack(anchor="w", pady=(0, 14))
        ttk.Label(top, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text=subtitle, style="Muted.TLabel", wraplength=940).pack(anchor="w", pady=(5, 0))

    def card(self, parent, title, description, command):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=15, cursor="hand2")
        frame.pack(fill="x", pady=5)
        tk.Label(frame, text=title, bg=PANEL, fg=FG, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(frame, text=description, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=900, justify="left").pack(anchor="w", pady=(4, 0))
        for widget in (frame, *frame.winfo_children()):
            widget.bind("<Button-1>", lambda _event, action=command: action())

    def footer(self, text="PRIVATE DATA STAYS ON THIS DEVICE"):
        foot = ttk.Frame(self.container)
        foot.pack(side="bottom", fill="x", pady=(16, 0))
        ttk.Label(foot, text=f"v{APP_VERSION}   ·   developed by sl4m3d", style="Muted.TLabel").pack(side="left")
        ttk.Label(foot, text=text, style="Muted.TLabel").pack(side="right")

    def show_home(self):
        self.clear()
        top = ttk.Frame(self.container)
        top.pack(fill="x", pady=(4, 18))
        ttk.Label(top, text="sl4m3d", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="SIGNER  /  CERTIFICATES  /  CMS  /  LOCAL FILES", style="Muted.TLabel").pack(anchor="w", pady=(5, 0))
        self.card(self.container, "01  /  Dateien signieren", "CMS/PKCS#7-Signatur mit passender .p12/.pfx-Identität. Die Signatur wird direkt danach geprüft.", self.show_sign)
        self.card(self.container, "02  /  Signatur prüfen", "CMS-/PKCS#7-Dateien prüfen und den enthaltenen Originalinhalt lokal extrahieren.", self.show_verify)
        self.card(self.container, "03  /  Zertifikat erstellen", "Eigenes X.509-Zertifikat als öffentliche .cer-Datei und passende passwortgeschützte .p12-Identität erstellen.", self.show_make)
        self.card(self.container, "04  /  .mobileconfig erstellen", "Apple-Konfigurationsprofile mit Profil-Metadaten, Web Clip und WLAN-Payload erzeugen; optional direkt signieren.", self.show_mobileconfig)
        self.card(self.container, "05  /  Stapel-Signierung", "Mehrere ausgewählte Dateien nacheinander mit derselben lokalen Identität signieren.", self.show_batch)
        self.card(self.container, "06  /  Dateimanager", "Lokale Ordner durchsuchen und Dateien direkt für Signatur, Prüfung oder Export auswählen.", self.show_file_manager)
        self.card(self.container, "07  /  Bibliothek", "Lokal gespeicherte signierte Dateien und eigene Exportdateien verwalten.", self.show_library)
        lower = ttk.Frame(self.container)
        lower.pack(fill="x", pady=(10, 0))
        ttk.Button(lower, text="UPDATE-LOG", style="Dark.TButton", command=self.show_changelog).pack(side="left")
        ttk.Button(lower, text="DIAGNOSE", style="Dark.TButton", command=self.show_diagnostics).pack(side="left", padx=8)
        ttk.Button(lower, text="EINSTELLUNGEN", style="Dark.TButton", command=self.show_settings).pack(side="left", padx=8)
        ttk.Label(lower, text="OFFLINE FIRST  /  STATISTIK NUR MIT OPT-IN", style="Muted.TLabel").pack(side="right")
        self.footer()

    def field(self, parent, label, variable, hint="", browse=None, show=None):
        ttk.Label(parent, text=label, style="Section.TLabel").pack(anchor="w", pady=(9, 5))
        row = ttk.Frame(parent)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=variable, show=show).pack(side="left", fill="x", expand=True)
        if browse:
            ttk.Button(row, text="Dateimanager", style="Dark.TButton", command=browse).pack(side="left", padx=(8, 0))
        if hint:
            ttk.Label(parent, text=hint, style="Muted.TLabel", wraplength=900).pack(anchor="w", pady=(4, 0))

    def choose_file(self, title="Datei auswählen", types=None):
        return filedialog.askopenfilename(title=title, filetypes=types or [("Alle Dateien", "*.*")])

    def choose_output(self, title, initial, extension, types=None):
        return filedialog.asksaveasfilename(title=title, initialfile=initial, defaultextension=extension, filetypes=types or [("Alle Dateien", "*.*")])

    def ask_password(self, title="P12-Passwort", require_min=False):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG)
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        ttk.Label(win, text="Passwort der PKCS#12-Identität", padding=(18, 16)).pack()
        value = tk.StringVar()
        entry = ttk.Entry(win, textvariable=value, show="•", width=42)
        entry.pack(padx=18, pady=8)
        entry.focus_set()
        result = {"value": None}
        def finish(ok):
            candidate = value.get()
            if ok and require_min and len(candidate) < 8:
                messagebox.showwarning("Passwort zu kurz", "Das Passwort muss mindestens 8 Zeichen lang sein.", parent=win)
                return
            result["value"] = candidate if ok else None
            win.destroy()
        buttons = ttk.Frame(win, padding=14)
        buttons.pack()
        ttk.Button(buttons, text="Abbrechen", style="Dark.TButton", command=lambda: finish(False)).pack(side="left", padx=4)
        ttk.Button(buttons, text="Weiter", style="Accent.TButton", command=lambda: finish(True)).pack(side="left", padx=4)
        win.bind("<Return>", lambda _event: finish(True))
        win.bind("<Escape>", lambda _event: finish(False))
        win.wait_window()
        return result["value"]

    def _choose_and_set(self, variable, title="Datei auswählen"):
        path = self.choose_file(title)
        if path:
            variable.set(path)

    def show_sign(self):
        self.clear()
        self.header("Dateien signieren", "Erstellt eine angehängte CMS/PKCS#7-Signatur. Private Schlüssel werden nur kurzzeitig in einem geschützten lokalen Temp-Ordner verwendet.")
        self.field(self.container, "DATEI ZUM SIGNIEREN", self.sign_source_var, "Unterstützt beliebige Dateitypen, auch .mobileconfig.", lambda: self.show_file_manager(mode="source"))
        self.field(self.container, "SIGNATURIDENTITÄT (.P12 / .PFX)", self.sign_p12_var, "Eine .cer-Datei enthält nur das öffentliche Zertifikat und kann nicht allein signieren.", lambda: self.show_file_manager(mode="identity"))
        ttk.Label(self.container, text="Signaturen werden nach dem Erstellen kryptografisch geprüft. Die Zertifikats-Vertrauenskette ist eine separate Betriebssystementscheidung.", style="Muted.TLabel", wraplength=900).pack(anchor="w", pady=18)
        row = ttk.Frame(self.container)
        row.pack(anchor="w", pady=8)
        ttk.Button(row, text="DATEI SIGNIEREN  →", style="Accent.TButton", command=self.do_sign).pack(side="left")
        ttk.Button(row, text="DATEIMANAGER", style="Dark.TButton", command=self.show_file_manager).pack(side="left", padx=8)
        self.footer()

    def do_sign(self):
        source_text, p12_text = self.sign_source_var.get().strip(), self.sign_p12_var.get().strip()
        if not source_text or not p12_text:
            return messagebox.showwarning("Dateien fehlen", "Wähle sowohl eine Datei als auch eine .p12/.pfx-Identität.")
        source, p12 = Path(source_text).expanduser(), Path(p12_text).expanduser()
        if not source.is_file() or not p12.is_file():
            return messagebox.showerror("Datei nicht gefunden", "Die ausgewählte Datei oder Identität existiert nicht.")
        password = self.ask_password()
        if password is None:
            return
        if source.suffix.lower() == ".mobileconfig":
            name, ext, types = source.stem + ".signed.mobileconfig", ".mobileconfig", [("Signiertes Profil", "*.mobileconfig"), ("Alle Dateien", "*.*")]
        else:
            name, ext, types = source.name + ".signed.p7m", ".p7m", [("CMS / PKCS#7", "*.p7m *.der"), ("Alle Dateien", "*.*")]
        target_text = self.choose_output("Signatur speichern", name, ext, types)
        if not target_text:
            return
        target_path = Path(target_text)
        if target_path.exists() and not messagebox.askyesno("Datei überschreiben?", f"Diese Datei existiert bereits:\n{target_path}\n\nÜberschreiben?"):
            return
        try:
            target = core.sign_file(source, p12, password, target_path, overwrite=target_path.exists())
            self._record_signature_event()
            try:
                library_target = core.LIBRARY_DIR / target.name
                index = 1
                while library_target.exists():
                    library_target = core.LIBRARY_DIR / f"{target.name}.{index}"
                    index += 1
                shutil.copy2(target, library_target)
            except OSError:
                pass
            messagebox.showinfo("Signatur geprüft", f"CMS-Signatur erstellt und erfolgreich rückgeprüft.\n\nGespeichert: {target}\n\nEs wurde keine Datei hochgeladen.")
        except Exception as exc:
            messagebox.showerror("Signieren fehlgeschlagen", str(exc))

    def show_verify(self):
        self.clear()
        self.header("Signatur prüfen", "Prüft die kryptografische CMS-Integrität und extrahiert den enthaltenen Dateiinhalt. Dies ist keine automatische Zertifikatsvertrauensprüfung.")
        sig_var = tk.StringVar()
        detached_var = tk.StringVar()
        self.field(self.container, "SIGNATURDATEI (.P7M / .DER / .PEM)", sig_var, "Unterstützt angehängte CMS-Signaturen im DER- und PEM-Format.", lambda: self._choose_and_set(sig_var, "Signaturdatei auswählen"))
        self.field(self.container, "OPTIONALE ORIGINALDATEI (DETACHED CMS)", detached_var, "Nur erforderlich, wenn die Signatur den Dateiinhalt nicht eingebettet enthält.", lambda: self._choose_and_set(detached_var, "Originaldatei auswählen"))
        def verify():
            if not sig_var.get().strip():
                return messagebox.showwarning("Signatur fehlt", "Wähle eine Signaturdatei aus.")
            sig = Path(sig_var.get()).expanduser()
            name = sig.stem + ".verified" + (".bin")
            output = self.choose_output("Verifizierten Inhalt speichern", name, ".bin")
            if not output:
                return
            if Path(output).exists() and not messagebox.askyesno("Datei überschreiben?", f"Die Datei existiert bereits:\n{output}\n\nÜberschreiben?"):
                return
            try:
                detached = Path(detached_var.get()) if detached_var.get().strip() else None
                out, note = core.verify_cms(sig, Path(output), detached, overwrite=Path(output).exists())
                messagebox.showinfo("Signatur gültig", f"CMS-Integritätsprüfung erfolgreich.\n\nInhalt: {out}\n\n{note}")
            except Exception as exc:
                messagebox.showerror("Signatur ungültig", str(exc))
        ttk.Button(self.container, text="SIGNATUR PRÜFEN  →", style="Accent.TButton", command=verify).pack(anchor="w", pady=18)
        self.footer()

    def show_make(self):
        self.clear()
        self.header("Zertifikat erstellen", "Erzeugt ein selbstsigniertes X.509-Zertifikat (.cer) und eine dazu passende, passwortgeschützte .p12-Datei mit privatem Schlüssel.")
        self.field(self.container, "COMMON NAME", self.make_name_var, "Zum Beispiel: sl4m3d local identity")
        self.field(self.container, "GÜLTIGKEIT IN TAGEN", self.make_days_var, "Erlaubter Bereich: 1 bis 3650 Tage.")
        ttk.Label(self.container, text="SCHLÜSSELALGORITHMUS", style="Section.TLabel").pack(anchor="w", pady=(9, 5))
        ttk.Combobox(self.container, textvariable=self.make_algorithm_var, values=("RSA 2048", "RSA 3072", "RSA 4096", "EC P-256", "EC P-384"), state="readonly", width=22).pack(anchor="w")
        ttk.Checkbutton(self.container, text="Als lokale CA ausstellen (nur für eigene Test-/Lab-Umgebungen)", variable=self.make_ca_var).pack(anchor="w", pady=(12, 0))
        ttk.Checkbutton(self.container, text="Zusätzlich passwortgeschützte .p12-Identität erstellen (mit privatem Schlüssel)", variable=self.make_identity_var, command=self._toggle_p12_fields).pack(anchor="w", pady=(12, 0))
        self.make_password_frame = ttk.Frame(self.container)
        ttk.Label(self.make_password_frame, text="P12-EXPORT-PASSWORT", style="Section.TLabel").pack(anchor="w", pady=(9, 5))
        ttk.Entry(self.make_password_frame, textvariable=self.make_password_var, show="•").pack(fill="x")
        ttk.Label(self.make_password_frame, text="Mindestens 8 Zeichen. Wird nicht gespeichert.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(self.container, text="Zielordner auswählen", style="Section.TLabel").pack(anchor="w", pady=(12, 5))
        out_row = ttk.Frame(self.container)
        out_row.pack(fill="x")
        self.make_out_row = out_row
        self._toggle_p12_fields()
        out_dir = tk.StringVar(value=str(Path.home()))
        ttk.Entry(out_row, textvariable=out_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(out_row, text="Ordner wählen", style="Dark.TButton", command=lambda: out_dir.set(filedialog.askdirectory() or out_dir.get())).pack(side="left", padx=(8, 0))
        def make():
            try:
                days = int(self.make_days_var.get().strip())
                directory = Path(out_dir.get()).expanduser().resolve(strict=True)
                include_p12 = self.make_identity_var.get()
                cert_exists = directory / (core._safe_stem(self.make_name_var.get()) + ".cer")
                p12_exists = directory / (core._safe_stem(self.make_name_var.get()) + ".p12")
                outputs_exist = cert_exists.exists() or (include_p12 and p12_exists.exists())
                overwrite = False
                if outputs_exist:
                    names = ".cer und .p12" if include_p12 else ".cer"
                    overwrite = messagebox.askyesno("Dateien überschreiben?", f"Mindestens eine Zieldatei ({names}) existiert bereits in:\n{directory}\n\nVorhandene Ziel-Dateien ersetzen?")
                    if not overwrite:
                        return
                cert, p12 = core.create_certificate(
                    self.make_name_var.get(), days, self.make_algorithm_var.get(), directory,
                    self.make_password_var.get() if include_p12 else "", self.make_ca_var.get(), overwrite,
                    export_identity=include_p12,
                )
                self.make_password_var.set("")
                details = f"Öffentliches DER-Zertifikat (.cer):\n{cert}"
                if p12 is not None:
                    details += f"\n\nPasswortgeschützte Identität (.p12):\n{p12}\n\nZertifikat und privater Schlüssel wurden geprüft."
                else:
                    details += "\n\nCER-only: Der private Schlüssel wurde nur temporär genutzt und nicht exportiert."
                messagebox.showinfo("Zertifikat erstellt", details)
            except Exception as exc:
                messagebox.showerror("Erstellen fehlgeschlagen", str(exc))
        ttk.Button(self.container, text="ZERTIFIKAT ERSTELLEN  →", style="Accent.TButton", command=make).pack(anchor="w", pady=18)
        self.footer()

    def _toggle_p12_fields(self):
        if self.make_identity_var.get():
            # Keep password controls directly above the export-directory section.
            anchor = getattr(self, "make_out_row", None)
            if anchor is not None:
                self.make_password_frame.pack(fill="x", before=anchor)
            else:
                self.make_password_frame.pack(fill="x")
        else:
            self.make_password_var.set("")
            self.make_password_frame.pack_forget()

    def show_mobileconfig(self):
        self.clear()
        self.header(".mobileconfig erstellen", "Erstellt ein Apple-Konfigurationsprofil als XML-Plist. Das Profil wird lokal erstellt und kann optional direkt mit einer .p12-Identität signiert werden.")
        self.field(self.container, "PROFILNAME", self.mobile_name_var)
        self.field(self.container, "EINDEUTIGE IDENTIFIER-KENNUNG", self.mobile_identifier_var, "Zum Beispiel: is.great.sl4m3d.profile")
        self.field(self.container, "ORGANISATION", self.mobile_org_var)
        ttk.Separator(self.container).pack(fill="x", pady=12)
        ttk.Checkbutton(self.container, text="Web Clip hinzufügen", variable=self.mobile_webclip_var).pack(anchor="w")
        self.field(self.container, "WEB-CLIP-TITEL", self.mobile_webclip_label_var)
        self.field(self.container, "WEB-CLIP-URL", self.mobile_webclip_url_var, "HTTP oder HTTPS.")
        ttk.Separator(self.container).pack(fill="x", pady=12)
        ttk.Checkbutton(self.container, text="WLAN-Payload hinzufügen (WPA/WPA2 Personal)", variable=self.mobile_wifi_var).pack(anchor="w")
        self.field(self.container, "WLAN-SSID", self.mobile_wifi_ssid_var)
        self.field(self.container, "WLAN-PASSWORT", self.mobile_wifi_password_var, "Mindestens 8 Zeichen. Das Passwort wird im Profil gespeichert, das du exportierst.", show="•")
        ttk.Separator(self.container).pack(fill="x", pady=12)
        ttk.Checkbutton(self.container, text="Nach dem Erstellen mit einer .p12-Datei signieren", variable=self.mobile_sign_var).pack(anchor="w")
        self.field(self.container, "SIGNATURIDENTITÄT (.P12 / .PFX)", self.mobile_p12_var, "Wird nur verwendet, wenn die Option aktiviert ist.", lambda: self._choose_and_set(self.mobile_p12_var, "P12-Identität auswählen"))
        ttk.Button(self.container, text="PROFIL ERSTELLEN  →", style="Accent.TButton", command=self.do_mobileconfig).pack(anchor="w", pady=18)
        self.footer()

    def do_mobileconfig(self):
        try:
            name = self.mobile_name_var.get().strip()
            default = (core._safe_stem(name) or "profile") + ".mobileconfig"
            out = self.choose_output("Profil speichern", default, ".mobileconfig", [("Apple-Konfigurationsprofil", "*.mobileconfig"), ("Alle Dateien", "*.*")])
            if not out:
                return
            if self.mobile_wifi_var.get() and not self.mobile_wifi_ssid_var.get().strip():
                raise core.CryptoError("Für den WLAN-Payload muss eine SSID eingetragen werden.")
            if self.mobile_sign_var.get() and not self.mobile_p12_var.get().strip():
                raise core.CryptoError("Für die Profilsignatur muss eine .p12/.pfx-Identität ausgewählt werden.")
            web_label = self.mobile_webclip_label_var.get() if self.mobile_webclip_var.get() else None
            web_url = self.mobile_webclip_url_var.get() if self.mobile_webclip_var.get() else None
            wifi_ssid = self.mobile_wifi_ssid_var.get() if self.mobile_wifi_var.get() else None
            wifi_pass = self.mobile_wifi_password_var.get() if self.mobile_wifi_var.get() else None
            output_path = Path(out)
            overwrite = output_path.exists()
            if overwrite and not messagebox.askyesno("Profil überschreiben?", f"Diese Datei existiert bereits:\n{output_path}\n\nÜberschreiben?"):
                return
            profile = core.make_mobileconfig(output_path, name, self.mobile_identifier_var.get(), self.mobile_org_var.get(), web_label, web_url, wifi_ssid, wifi_pass, overwrite=overwrite)
            if self.mobile_sign_var.get():
                p12_text = self.mobile_p12_var.get().strip()
                password = self.ask_password("P12-Passwort für Signatur")
                if password is None:
                    return
                signed = profile.with_name(profile.stem + ".signed.mobileconfig")
                if signed.exists() and not messagebox.askyesno("Signatur überschreiben?", f"Diese Datei existiert bereits:\n{signed}\n\nÜberschreiben?"):
                    return
                core.sign_file(profile, Path(p12_text), password, signed, overwrite=signed.exists())
                self._record_signature_event()
                self.mobile_wifi_password_var.set("")
                messagebox.showinfo("Profil erstellt", f"Unsigniertes Profil:\n{profile}\n\nSigniertes Profil (CMS geprüft):\n{signed}")
            else:
                self.mobile_wifi_password_var.set("")
                messagebox.showinfo("Profil erstellt", f"Profil erstellt und XML geprüft:\n{profile}\n\nHinweis: Das Profil ist noch nicht CMS-signiert.")
        except Exception as exc:
            messagebox.showerror("Profil-Erstellung fehlgeschlagen", str(exc))

    def show_batch(self):
        self.clear()
        self.header("Stapel-Signierung", "Mehrere Dateien lokal mit derselben PKCS#12-Identität signieren. Jede Signatur wird einzeln rückgeprüft.")
        files = {"paths": []}
        p12_var = tk.StringVar()
        ttk.Button(self.container, text="DATEIEN AUSWÄHLEN", style="Dark.TButton", command=lambda: self._pick_batch_files(files, count_label)).pack(anchor="w", pady=(5, 4))
        count_label = ttk.Label(self.container, text="Noch keine Dateien ausgewählt.", style="Muted.TLabel")
        count_label.pack(anchor="w", pady=(0, 12))
        self.field(self.container, "SIGNATURIDENTITÄT (.P12 / .PFX)", p12_var, "Eine Identität wird für alle ausgewählten Dateien verwendet.", lambda: self._choose_and_set(p12_var, "P12-Datei auswählen"))
        def execute():
            if not files["paths"] or not p12_var.get().strip():
                return messagebox.showwarning("Eingaben fehlen", "Wähle mindestens eine Datei und eine P12-Identität aus.")
            password = self.ask_password()
            if password is None:
                return
            out_dir = filedialog.askdirectory(title="Zielordner für Signaturen auswählen")
            if not out_dir:
                return
            results, errors = [], []
            for src in files["paths"]:
                try:
                    name = src.name + ".signed.p7m"
                    target = Path(out_dir) / name
                    suffix = 1
                    while target.exists():
                        target = Path(out_dir) / f"{name}.{suffix}"
                        suffix += 1
                    result = core.sign_file(src, Path(p12_var.get()), password, target)
                    results.append(str(result))
                    self._record_signature_event()
                except Exception as exc:
                    errors.append(f"{src.name}: {exc}")
            message = f"Erfolgreich signiert: {len(results)} von {len(files['paths'])} Datei(en)."
            if errors:
                message += "\n\nFehler:\n" + "\n".join(errors[:10])
            messagebox.showinfo("Stapel-Signierung abgeschlossen", message)
        ttk.Button(self.container, text="ALLE DATEIEN SIGNIEREN  →", style="Accent.TButton", command=execute).pack(anchor="w", pady=18)
        self.footer()

    def _pick_batch_files(self, files, label):
        chosen = filedialog.askopenfilenames(title="Mehrere Dateien auswählen", filetypes=[("Alle Dateien", "*.*")])
        if chosen:
            files["paths"] = [Path(p) for p in chosen]
            label.configure(text=f"{len(files['paths'])} Datei(en) ausgewählt.")

    def show_file_manager(self, mode="browse"):
        self.clear()
        self.header("Dateimanager", "Lokale Ordner durchsuchen. Dateien werden nicht hochgeladen oder in einen Cloud-Speicher kopiert.")
        toolbar = ttk.Frame(self.container)
        toolbar.pack(fill="x", pady=(0, 10))
        path_var = tk.StringVar(value=str(self.current_dir))
        ttk.Entry(toolbar, textvariable=path_var).pack(side="left", fill="x", expand=True)
        tree = ttk.Treeview(self.container, columns=("kind", "size", "modified"), show="tree headings", selectmode="browse")
        tree.heading("#0", text="NAME")
        tree.heading("kind", text="TYP")
        tree.heading("size", text="GRÖSSE")
        tree.heading("modified", text="GEÄNDERT")
        tree.column("#0", width=420)
        tree.column("kind", width=110)
        tree.column("size", width=120, anchor="e")
        tree.column("modified", width=170)
        tree.pack(fill="both", expand=True, pady=(0, 10))
        status = ttk.Label(self.container, text="Ordner öffnen oder eine Datei auswählen.", style="Muted.TLabel")
        status.pack(anchor="w", pady=(0, 8))
        entries = {}
        def refresh():
            raw = path_var.get().strip()
            try:
                folder = Path(raw).expanduser().resolve(strict=True)
                if not folder.is_dir():
                    raise NotADirectoryError(str(folder))
                listing = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
            except Exception as exc:
                return messagebox.showerror("Ordner nicht erreichbar", str(exc))
            self.current_dir = folder
            path_var.set(str(folder))
            tree.delete(*tree.get_children())
            entries.clear()
            status.configure(text=f"{len(listing)} Einträge in {folder}")
            for index, item in enumerate(listing):
                try:
                    st = item.stat()
                    directory = item.is_dir()
                    size = "—" if directory else f"{st.st_size:,} B"
                    import datetime
                    changed = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                    iid = str(index)
                    entries[iid] = item
                    tree.insert("", "end", iid=iid, text=item.name + ("/" if directory else ""), values=("Ordner" if directory else (item.suffix.lower() or "Datei"), size, changed))
                except OSError:
                    continue
        def current_selection():
            selection = tree.selection()
            return entries.get(selection[0]) if selection else None
        def open_selected(_event=None):
            item = current_selection()
            if item and item.is_dir():
                path_var.set(str(item)); refresh()
            elif item:
                if mode == "source": self.sign_source_var.set(str(item)); self.show_sign()
                elif mode == "identity":
                    if item.suffix.lower() not in (".p12", ".pfx"):
                        return messagebox.showwarning("P12 erforderlich", "Wähle eine .p12/.pfx-Datei mit privatem Schlüssel aus.")
                    self.sign_p12_var.set(str(item)); self.show_sign()
                elif mode == "inspect": self.show_inspect(str(item))
                elif mode == "browse": status.configure(text=f"Ausgewählt: {item}")
        def go_up():
            path_var.set(str(self.current_dir.parent)); refresh()
        ttk.Button(toolbar, text="Hoch", style="Dark.TButton", command=go_up).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Start", style="Dark.TButton", command=lambda: (path_var.set(str(Path.home())), refresh())).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Öffnen", style="Dark.TButton", command=refresh).pack(side="left", padx=(6, 0))
        path_var_entry = toolbar.winfo_children()[0]
        path_var_entry.bind("<Return>", lambda _event: refresh())
        tree.bind("<Double-1>", open_selected)
        actions = ttk.Frame(self.container)
        actions.pack(fill="x")
        def use_folder():
            item = current_selection()
            chosen = item if item and item.is_dir() else self.current_dir
            self.make_export_dir_var.set(str(chosen))
            self.show_make()
        ttk.Button(actions, text="Als Dokument verwenden", style="Accent.TButton", command=lambda: (self._use_selected_path(tree, entries, "source"))).pack(side="left")
        ttk.Button(actions, text="Als P12 verwenden", style="Dark.TButton", command=lambda: self._use_selected_path(tree, entries, "identity")).pack(side="left", padx=6)
        ttk.Button(actions, text="Zertifikat prüfen", style="Dark.TButton", command=lambda: self._use_selected_path(tree, entries, "inspect")).pack(side="left", padx=6)
        ttk.Button(actions, text="Ordner öffnen", style="Dark.TButton", command=lambda: open_path(current_selection() if current_selection() and current_selection().is_dir() else self.current_dir)).pack(side="right")
        if mode in ("source", "identity", "inspect"):
            ttk.Button(actions, text="Auswahl übernehmen", style="Accent.TButton", command=open_selected).pack(side="left", padx=6)
        refresh()
        self.footer()

    def _use_selected_path(self, tree, entries, action):
        selection = tree.selection()
        path = entries.get(selection[0]) if selection else None
        if not path or not path.is_file():
            return messagebox.showwarning("Datei auswählen", "Wähle zuerst eine Datei aus.")
        if action == "source": self.sign_source_var.set(str(path)); self.show_sign()
        elif action == "identity":
            if path.suffix.lower() not in (".p12", ".pfx"):
                return messagebox.showwarning("P12 erforderlich", "Eine .cer-Datei enthält keinen privaten Schlüssel.")
            self.sign_p12_var.set(str(path)); self.show_sign()
        elif action == "inspect": self.show_inspect(str(path))

    def show_inspect(self, selected_path=None):
        self.clear()
        self.header("Zertifikat prüfen", "Unterstützt PEM, DER, CER, CRT, P12 und PFX. Der private Schlüssel wird bei P12-Dateien nur temporär extrahiert.")
        controls = ttk.Frame(self.container)
        controls.pack(fill="x", pady=(5, 12))
        ttk.Button(controls, text="DATEI AUSWÄHLEN", style="Accent.TButton", command=self.inspect_dialog).pack(side="left")
        self.info = tk.Text(self.container, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", wrap="word", font=("Consolas", 10), padx=15, pady=13)
        self.info.pack(fill="both", expand=True, pady=8)
        self.info.insert("1.0", "Noch kein Zertifikat ausgewählt.")
        self.info.configure(state="disabled")
        if selected_path:
            self.inspect_file(Path(selected_path))
        self.footer()

    def inspect_dialog(self):
        path = self.choose_file("Zertifikat oder Identität auswählen", [("Zertifikate und Identitäten", "*.cer *.crt *.pem *.der *.p12 *.pfx"), ("Alle Dateien", "*.*")])
        if path:
            self.inspect_file(Path(path))

    def inspect_file(self, path):
        password = None
        if path.suffix.lower() in (".p12", ".pfx"):
            password = self.ask_password("P12-Inspektionspasswort")
            if password is None:
                return
        try:
            detail = core.inspect_certificate(path, password)
            self.info.configure(state="normal")
            self.info.delete("1.0", "end")
            self.info.insert("1.0", detail)
            self.info.configure(state="disabled")
        except Exception as exc:
            messagebox.showerror("Prüfung fehlgeschlagen", str(exc))

    def show_library(self):
        self.clear()
        self.header("Lokale Bibliothek", "Signierte Dateien, die du bewusst in der Signer-Bibliothek abgelegt hast. Private Schlüssel und P12-Passwörter werden nicht automatisch hier gespeichert.")
        tree = ttk.Treeview(self.container, columns=("size", "type"), show="tree headings", selectmode="browse")
        tree.heading("#0", text="DATEI")
        tree.heading("size", text="GRÖSSE")
        tree.heading("type", text="TYP")
        tree.pack(fill="both", expand=True, pady=(0, 12))
        def refresh():
            tree.delete(*tree.get_children())
            try:
                items = sorted(core.LIBRARY_DIR.iterdir(), key=lambda p: p.name.casefold())
            except OSError as exc:
                return messagebox.showerror("Bibliothek nicht lesbar", str(exc))
            for index, item in enumerate(items):
                if item.is_file():
                    try:
                        tree.insert("", "end", iid=str(index), text=item.name, values=(f"{item.stat().st_size:,} Bytes", item.suffix.lower() or "Datei"))
                    except OSError:
                        pass
        def open_selected():
            selected = tree.selection()
            if not selected:
                return open_path(core.LIBRARY_DIR)
            try:
                index = int(selected[0])
                items = [p for p in sorted(core.LIBRARY_DIR.iterdir(), key=lambda p: p.name.casefold()) if p.is_file()]
                if 0 <= index < len(items):
                    open_path(items[index])
            except Exception as exc:
                messagebox.showerror("Datei konnte nicht geöffnet werden", str(exc))
        buttons = ttk.Frame(self.container)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="DATEI ÖFFNEN", style="Accent.TButton", command=open_selected).pack(side="left")
        ttk.Button(buttons, text="ORDNER ÖFFNEN", style="Dark.TButton", command=lambda: open_path(core.LIBRARY_DIR)).pack(side="left", padx=7)
        ttk.Button(buttons, text="AKTUALISIEREN", style="Dark.TButton", command=refresh).pack(side="right")
        refresh()
        self.footer()

    def show_changelog(self):
        self.clear()
        self.header("Update-Log", "Änderungshistorie der lokalen Anwendung.")
        box = tk.Text(self.container, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", wrap="word", font=("Segoe UI", 10), padx=16, pady=14)
        box.pack(fill="both", expand=True)
        for version, date, title, items in CHANGELOG:
            box.insert("end", f"v{version}  ·  {date}\n", "heading")
            box.insert("end", title + "\n", "subheading")
            for item in items:
                box.insert("end", "  •  " + item + "\n")
            box.insert("end", "\n")
        box.tag_configure("heading", foreground=ACCENT, font=("Segoe UI", 13, "bold"))
        box.tag_configure("subheading", foreground=GREEN, font=("Segoe UI", 10, "bold"))
        box.configure(state="disabled")
        self.footer()

    def show_settings(self):
        self.clear()
        self.header("Einstellungen", "Optionale anonyme Gesamtstatistik. Der Signer arbeitet ansonsten vollständig lokal und offline.")
        enabled = tk.BooleanVar(value=stats_client.is_enabled())
        ttk.Checkbutton(
            self.container,
            text="Anonyme Anzahl erfolgreich signierter Dateien teilen",
            variable=enabled,
        ).pack(anchor="w", pady=(8, 6))
        ttk.Label(
            self.container,
            text=("Nur nach Aktivierung sendet die App pro erfolgreich geprüfter Signatur genau zwei Werte: "
                  "event=cms_sign und die App-Version. Keine Datei, kein Dateiname, kein Pfad, kein Zertifikat, "
                  "kein privater Schlüssel, kein Passwort und keine Geräte-ID werden übertragen. "
                  "Nicht gesendete Ereignisse bleiben lokal in einer kleinen Warteschlange."),
            style="Muted.TLabel", wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 16))
        status = ttk.Label(self.container, text=f"Noch ausstehende Ereignisse: {stats_client.pending_count()}", style="Muted.TLabel")
        status.pack(anchor="w", pady=(0, 10))
        def save():
            stats_client.set_enabled(enabled.get())
            status.configure(text=("Anonyme Statistik aktiviert." if enabled.get() else "Anonyme Statistik deaktiviert; lokale Warteschlange gelöscht.") + f" Ausstehend: {stats_client.pending_count()}")
        def sync():
            if not enabled.get():
                messagebox.showinfo("Statistik deaktiviert", "Aktiviere zuerst die optionale Statistik.")
                return
            status.configure(text="Warteschlange wird im Hintergrund synchronisiert …")
            def worker():
                count = stats_client.flush_pending()
                remaining = stats_client.pending_count()
                try:
                    self.root.after(0, lambda: status.configure(text=f"Übertragen: {count}. Noch ausstehend: {remaining}"))
                except tk.TclError:
                    pass
            threading.Thread(target=worker, daemon=True).start()
        actions = ttk.Frame(self.container)
        actions.pack(anchor="w", pady=12)
        ttk.Button(actions, text="EINSTELLUNG SPEICHERN", style="Accent.TButton", command=save).pack(side="left")
        ttk.Button(actions, text="WARTESCHLANGE SYNCHRONISIEREN", style="Dark.TButton", command=sync).pack(side="left", padx=8)
        self.footer()

    def show_diagnostics(self):
        self.clear()
        self.header("Diagnose", "Lokale Komponenten prüfen. Dieser Bereich benötigt keine Internetverbindung.")
        box = tk.Text(self.container, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", wrap="word", font=("Consolas", 10), padx=15, pady=13)
        box.pack(fill="both", expand=True, pady=8)
        details = [
            f"Application: {APP_NAME} {APP_VERSION}",
            f"OS: {platform.platform()}",
            f"Python: {platform.python_version()}",
            f"OpenSSL: {core.openssl_version()}",
            f"Data directory: {core.DATA_DIR}",
            f"Library directory: {core.LIBRARY_DIR}",
            f"Anonymous aggregate stats: {'OPTED IN' if stats_client.is_enabled() else 'DISABLED'}",
            f"Pending aggregate events: {stats_client.pending_count()}",
            "No file, path, certificate, key, password or device ID is sent.",
            "Private key handling: local temporary files only",
            "",
            "Self-test: not yet executed",
        ]
        box.insert("1.0", "\n".join(details))
        box.configure(state="disabled")
        def test():
            from selftest import run_self_tests
            try:
                results = run_self_tests()
                box.configure(state="normal")
                box.delete("1.0", "end")
                box.insert("1.0", "\n".join(details[:-2] + ["", "SELF-TEST RESULTS:", *[f"PASS  {x}" for x in results], "", "All local self-tests passed."]))
                box.configure(state="disabled")
                messagebox.showinfo("Selbsttest erfolgreich", f"{len(results)} lokale Tests bestanden.")
            except Exception as exc:
                box.configure(state="normal")
                box.insert("end", f"\n\nFAIL  {exc}")
                box.configure(state="disabled")
                messagebox.showerror("Selbsttest fehlgeschlagen", str(exc))
        ttk.Button(self.container, text="LOKALEN SELBSTTEST STARTEN", style="Accent.TButton", command=test).pack(anchor="w", pady=8)
        self.footer()


def main():
    try:
        core.openssl_path()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("OpenSSL fehlt", str(exc))
        root.destroy()
        return 2
    root = tk.Tk()
    SignerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

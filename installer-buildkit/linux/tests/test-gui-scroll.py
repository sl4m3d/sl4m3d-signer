#!/usr/bin/env python3
"""Requires an X server; e.g. xvfb-run -a python3 test-gui-scroll.py."""
import tkinter as tk
from types import SimpleNamespace
from signer import SignerApp

root = tk.Tk()
app = SignerApp(root)
root.geometry("860x650+0+0")
root.update_idletasks(); root.update()
pages = ["show_home", "show_sign", "show_verify", "show_make", "show_mobileconfig", "show_batch", "show_file_manager", "show_library", "show_inspect", "show_changelog", "show_diagnostics", "show_settings"]
for name in pages:
    getattr(app, name)()
    root.update_idletasks(); root.update()
    box = app.canvas.bbox("all")
    assert box and app.canvas.winfo_width() <= root.winfo_width()
    assert app.scrollbar.winfo_ismapped()
    if box[3] - box[1] > app.canvas.winfo_height() + 2:
        x, y = app.canvas.winfo_rootx() + 20, app.canvas.winfo_rooty() + 20
        before = app.canvas.yview()
        app._on_mousewheel(SimpleNamespace(x_root=x, y_root=y, num=5, delta=0))
        root.update_idletasks(); root.update()
        assert app.canvas.yview()[0] > before[0], name
app.show_make(); root.update_idletasks()
assert app.make_password_frame.winfo_manager() == "pack"
app.make_identity_var.set(False); app._toggle_p12_fields(); assert app.make_password_frame.winfo_manager() == ""
app.make_identity_var.set(True); app._toggle_p12_fields(); assert app.make_password_frame.winfo_manager() == "pack"
print("PASS: all GUI screens build, canvas scrolls, width stays within viewport, CER/P12 toggle works")
root.destroy()

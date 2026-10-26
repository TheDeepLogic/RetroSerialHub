"""Tkinter GUI window for configuring email settings on the host desktop."""

from rsh_storage import settings_dir, settings_path
import json
import os
import pathlib
import sys
import tkinter as tk
from tkinter import messagebox, ttk


def load_config(path: pathlib.Path) -> dict:
    default_config = {
        "default_mode": "hub",
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_pass": "",
        "smtp_tls": True,
        "smtp_ssl": False,
        "from_addr": "",
        "imap_host": "",
        "imap_port": 993,
        "imap_user": "",
        "imap_pass": "",
        "imap_ssl": True,
    }
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config


def save_config(path: pathlib.Path, config: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def run_gui(config_path_str: str):
    config_path = pathlib.Path(config_path_str)
    config = load_config(config_path)

    root = tk.Tk()
    root.title("Retro Serial Hub - Electronic Mail Setup")
    root.geometry("480x560")
    root.resizable(False, False)

    # Style
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    padding_opts = {"padx": 10, "pady": 4}

    # Header
    header_frame = ttk.Frame(root, padding=10)
    header_frame.pack(fill="x")
    ttk.Label(
        header_frame,
        text="Retro Serial Hub Mail Setup",
        font=("Helvetica", 13, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        header_frame,
        text="Configure Integrated Hub Mail or Internet Email (IMAP/SMTP).",
        font=("Helvetica", 9),
    ).pack(anchor="w")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=5)

    # Tab 1: General & Hub Mail
    tab_gen = ttk.Frame(notebook, padding=10)
    notebook.add(tab_gen, text="Mailbox Mode")

    mode_var = tk.StringVar(value=config.get("default_mode", "hub"))
    ttk.Label(tab_gen, text="Default Mail System:", font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(5, 5))
    ttk.Radiobutton(
        tab_gen,
        text="Integrated Hub Mailbox (Inter-terminal / Local Hub)",
        variable=mode_var,
        value="hub",
    ).pack(anchor="w", padx=15, pady=2)
    ttk.Label(
        tab_gen,
        text="Messages are stored centrally on the hub. Terminal machines\n"
             "are automatically identified (e.g. 'APPLE2 [Serial COM2]').\n"
             "No external internet account required.",
        font=("Helvetica", 8, "italic"),
        foreground="#555",
    ).pack(anchor="w", padx=30, pady=(0, 10))

    ttk.Radiobutton(
        tab_gen,
        text="Internet Email (External IMAP & SMTP)",
        variable=mode_var,
        value="internet",
    ).pack(anchor="w", padx=15, pady=2)
    ttk.Label(
        tab_gen,
        text="Connects to modern mail accounts (Gmail, Outlook, Yahoo,\netc.) using IMAP for inbox reading and SMTP for sending.",
        font=("Helvetica", 8, "italic"),
        foreground="#555",
    ).pack(anchor="w", padx=30, pady=(0, 10))

    # Tab 2: IMAP Settings
    tab_imap = ttk.Frame(notebook, padding=10)
    notebook.add(tab_imap, text="Incoming (IMAP)")

    ttk.Label(tab_imap, text="IMAP Server Host:").grid(row=0, column=0, sticky="w", **padding_opts)
    imap_host_entry = ttk.Entry(tab_imap, width=28)
    imap_host_entry.insert(0, config.get("imap_host", ""))
    imap_host_entry.grid(row=0, column=1, sticky="e", **padding_opts)

    ttk.Label(tab_imap, text="IMAP Port:").grid(row=1, column=0, sticky="w", **padding_opts)
    imap_port_entry = ttk.Entry(tab_imap, width=10)
    imap_port_entry.insert(0, str(config.get("imap_port", 993)))
    imap_port_entry.grid(row=1, column=1, sticky="w", **padding_opts)

    imap_ssl_var = tk.BooleanVar(value=config.get("imap_ssl", True))
    ttk.Checkbutton(tab_imap, text="Use SSL/TLS", variable=imap_ssl_var).grid(row=2, column=1, sticky="w", **padding_opts)

    ttk.Label(tab_imap, text="Username / Email:").grid(row=3, column=0, sticky="w", **padding_opts)
    imap_user_entry = ttk.Entry(tab_imap, width=28)
    imap_user_entry.insert(0, config.get("imap_user", ""))
    imap_user_entry.grid(row=3, column=1, sticky="e", **padding_opts)

    ttk.Label(tab_imap, text="Password / App Pass:").grid(row=4, column=0, sticky="w", **padding_opts)
    imap_pass_entry = ttk.Entry(tab_imap, width=28, show="*")
    imap_pass_entry.insert(0, config.get("imap_pass", ""))
    imap_pass_entry.grid(row=4, column=1, sticky="e", **padding_opts)

    # Tab 3: SMTP Settings
    tab_smtp = ttk.Frame(notebook, padding=10)
    notebook.add(tab_smtp, text="Outgoing (SMTP)")

    ttk.Label(tab_smtp, text="SMTP Server Host:").grid(row=0, column=0, sticky="w", **padding_opts)
    smtp_host_entry = ttk.Entry(tab_smtp, width=28)
    smtp_host_entry.insert(0, config.get("smtp_host", ""))
    smtp_host_entry.grid(row=0, column=1, sticky="e", **padding_opts)

    ttk.Label(tab_smtp, text="SMTP Port:").grid(row=1, column=0, sticky="w", **padding_opts)
    smtp_port_entry = ttk.Entry(tab_smtp, width=10)
    smtp_port_entry.insert(0, str(config.get("smtp_port", 587)))
    smtp_port_entry.grid(row=1, column=1, sticky="w", **padding_opts)

    smtp_tls_var = tk.BooleanVar(value=config.get("smtp_tls", True))
    ttk.Checkbutton(tab_smtp, text="Use STARTTLS", variable=smtp_tls_var).grid(row=2, column=1, sticky="w", **padding_opts)

    ttk.Label(tab_smtp, text="From Address:").grid(row=3, column=0, sticky="w", **padding_opts)
    smtp_from_entry = ttk.Entry(tab_smtp, width=28)
    smtp_from_entry.insert(0, config.get("from_addr", ""))
    smtp_from_entry.grid(row=3, column=1, sticky="e", **padding_opts)

    ttk.Label(tab_smtp, text="SMTP Username:").grid(row=4, column=0, sticky="w", **padding_opts)
    smtp_user_entry = ttk.Entry(tab_smtp, width=28)
    smtp_user_entry.insert(0, config.get("smtp_user", ""))
    smtp_user_entry.grid(row=4, column=1, sticky="e", **padding_opts)

    ttk.Label(tab_smtp, text="SMTP Password:").grid(row=5, column=0, sticky="w", **padding_opts)
    smtp_pass_entry = ttk.Entry(tab_smtp, width=28, show="*")
    smtp_pass_entry.insert(0, config.get("smtp_pass", ""))
    smtp_pass_entry.grid(row=5, column=1, sticky="e", **padding_opts)

    # Buttons frame
    btn_frame = ttk.Frame(root, padding=10)
    btn_frame.pack(fill="x", side="bottom")

    def on_test():
        ihost = imap_host_entry.get().strip()
        iuser = imap_user_entry.get().strip()
        ipass = imap_pass_entry.get().strip()
        if not ihost:
            messagebox.showinfo("Test Connection", "Please enter an IMAP host to test.")
            return
        import imaplib
        try:
            port = int(imap_port_entry.get().strip() or "993")
            if imap_ssl_var.get():
                server = imaplib.IMAP4_SSL(ihost, port, timeout=6)
            else:
                server = imaplib.IMAP4(ihost, port, timeout=6)
            if iuser and ipass:
                server.login(iuser, ipass)
                server.select("INBOX", readonly=True)
                server.logout()
                messagebox.showinfo("Test Successful", f"Successfully connected and logged into {ihost}!")
            else:
                server.logout()
                messagebox.showinfo("Test Successful", f"Successfully reached {ihost}:{port} (login skipped).")
        except Exception as exc:
            messagebox.showerror("Connection Failed", f"IMAP Test Failed:\n{exc}")

    def on_save():
        try:
            i_port = int(imap_port_entry.get().strip() or "993")
        except ValueError:
            i_port = 993
        try:
            s_port = int(smtp_port_entry.get().strip() or "587")
        except ValueError:
            s_port = 587

        updated = {
            "default_mode": mode_var.get(),
            "imap_host": imap_host_entry.get().strip(),
            "imap_port": i_port,
            "imap_ssl": imap_ssl_var.get(),
            "imap_user": imap_user_entry.get().strip(),
            "imap_pass": imap_pass_entry.get().strip(),
            "smtp_host": smtp_host_entry.get().strip(),
            "smtp_port": s_port,
            "smtp_tls": smtp_tls_var.get(),
            "smtp_ssl": False,
            "from_addr": smtp_from_entry.get().strip(),
            "smtp_user": smtp_user_entry.get().strip(),
            "smtp_pass": smtp_pass_entry.get().strip(),
        }
        save_config(config_path, updated)
        messagebox.showinfo("Saved", "Mail settings successfully saved!")
        root.destroy()

    ttk.Button(btn_frame, text="Test IMAP", command=on_test).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save Settings", command=on_save).pack(side="right", padx=5)
    ttk.Button(btn_frame, text="Cancel", command=root.destroy).pack(side="right", padx=5)

    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_gui(sys.argv[1])
    else:
        cfg = settings_path("mail_config.json")
        run_gui(str(cfg))

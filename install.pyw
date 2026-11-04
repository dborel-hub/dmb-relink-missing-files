"""
DMB Relink Missing Files for Nuke - installer / updater
by Daniel Marinho Borel  (danielmborel@gmail.com)

Double-click this file (needs Python 3 from python.org - tkinter comes with it).

  Install / Update     copies the "DMB Relink Missing Files" folder next to
                       this file into ~/.nuke/DMB Relink Missing Files
  Update from GitHub   downloads ONLY the files that changed on GitHub
  Uninstall            removes the plugin and its menu entry

Always kept: your settings (data/ - window size, last folder used).
menu.py: a "DMB Tools" entry is added once (backup first); an older
DMB Relink Missing Files block is replaced. Nothing else in .nuke is
touched. Other DMB plugins (Asset Manager, etc.) share the same
"DMB Tools" menu without conflict.
"""

import os
import re
import sys
import glob
import queue
import shutil
import threading
import datetime
import importlib.util

APP_NAME = "DMB Relink Missing Files"
AUTHOR = "Daniel Marinho Borel"
CONTACT = "danielmborel@gmail.com"

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, APP_NAME)
NUKE_DIR = os.path.join(os.path.expanduser("~"), ".nuke")
DEST = os.path.join(NUKE_DIR, APP_NAME)
MENU_PY = os.path.join(NUKE_DIR, "menu.py")

KEEP_ON_UPDATE = ("data",)                # never deleted / overwritten
SKIP_ON_COPY = ("data", "__pycache__")

IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------- menu.py block
BLOCK_START = "# ---- DMB Relink Missing Files: START (added by install.pyw) ----"
BLOCK_END = "# ---- DMB Relink Missing Files: END ----"
MENU_BLOCK = BLOCK_START + '''
# DMB Relink Missing Files by Daniel Marinho Borel - loaded only when a menu item is used.
def _dmb_relink_load():
    import os, sys, importlib.util
    if 'dmb_relink_missing_files' not in sys.modules:
        root = os.path.join(os.path.expanduser('~'), '.nuke', 'DMB Relink Missing Files')
        spec = importlib.util.spec_from_file_location(
            'dmb_relink_missing_files', os.path.join(root, '__init__.py'),
            submodule_search_locations=[root])
        module = importlib.util.module_from_spec(spec)
        sys.modules['dmb_relink_missing_files'] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            del sys.modules['dmb_relink_missing_files']
            raise
    return sys.modules['dmb_relink_missing_files']

def _dmb_relink_open():
    _dmb_relink_load()
    from dmb_relink_missing_files.nuke_integration import show_relink_missing
    show_relink_missing()

try:
    import nuke
    _dmb_tools = nuke.menu('Nuke').addMenu('DMB Tools')
    _dmb_tools.addCommand('Relink Missing Files', _dmb_relink_open)
    nuke.menu('Nodes').addCommand('DMB Tools/Relink Missing Files', _dmb_relink_open)
except Exception as _e:
    print('[DMB Relink Missing Files] menu entry failed: %s' % _e)
''' + BLOCK_END + "\n"

INSTALLER_BLOCK_RE = re.compile(r"\n*" + re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n?", re.S)
LEGACY_SIGNS = ("dmb_relink_missing",)   # hand-pasted versions from before this installer
                                          # (not "dmb_startup_picker" - that's an unrelated,
                                          # shared startup checklist used by other plugins too)
OLD_VERSION_SIGNS = ()

OK, WARN, MISSING, INFO = "ok", "warn", "missing", "info"


# ======================================================================
# Helpers
# ======================================================================

def read_text(path):
    for enc in ("utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def backup_menu(log):
    if os.path.exists(MENU_PY):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = MENU_PY + f".backup_{stamp}"
        shutil.copy2(MENU_PY, backup)
        log(f"Backup: {backup}")


def version_of(folder):
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', read_text(os.path.join(folder, "config.py")), re.M)
    return m.group(1) if m else None


def load_updater():
    """updater.py from the package next to this file, else the installed one."""
    for root in (SOURCE, DEST):
        path = os.path.join(root, "updater.py")
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("dmb_relink_updater", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError("updater.py not found - extract the whole ZIP")


def menu_state():
    """
    'current'  installer block, up to date
    'outdated' installer block from an older version (will be replaced)
    'manual'   hand-made loader we can't safely replace
    None       nothing
    """
    text = read_text(MENU_PY)
    if BLOCK_START in text:
        m = INSTALLER_BLOCK_RE.search(text)
        return "current" if m and MENU_BLOCK.strip() in m.group(0) else "outdated"
    if any(s in text for s in LEGACY_SIGNS):
        return "manual"
    if any(s in text for s in OLD_VERSION_SIGNS):
        return "old"
    return None


# ======================================================================
# Checks
# ======================================================================

def run_checks():
    """List of (status, title, detail)."""
    rows = []
    v = sys.version_info
    rows.append((OK if v >= (3, 6) else MISSING, "Python",
                 f"{v.major}.{v.minor}.{v.micro}" + ("" if v >= (3, 6) else " - needs 3.6+")))

    if os.path.exists(os.path.join(SOURCE, "__init__.py")):
        rows.append((OK, "Package", f"version {version_of(SOURCE) or '?'} next to this installer"))
    else:
        rows.append((WARN, "Package", f'no "{APP_NAME}" folder here - use "Update from GitHub" '
                                      'or extract the whole ZIP'))

    rows.append((OK if os.path.isdir(NUKE_DIR) else INFO, ".nuke folder",
                 NUKE_DIR if os.path.isdir(NUKE_DIR) else f"{NUKE_DIR} (will be created)"))

    if IS_WINDOWS:
        nukes = sorted(glob.glob(r"C:\Program Files\Nuke*"))
        rows.append((OK if nukes else INFO, "Nuke",
                     ", ".join(os.path.basename(n) for n in nukes) if nukes
                     else "not found in C:\\Program Files (fine if installed elsewhere)"))

    if os.path.exists(os.path.join(DEST, "__init__.py")):
        detail = f"version {version_of(DEST) or '?'} installed"
        if os.path.isdir(os.path.join(DEST, "data")):
            detail += " (your settings in data/ are kept on update)"
        rows.append((OK, "Installed", detail))
    else:
        rows.append((INFO, "Installed", "not installed yet"))

    state = menu_state()
    detail = {
        "current": (OK, "DMB Tools > Relink Missing Files entry is there"),
        "outdated": (INFO, "older entry - will be updated"),
        "manual": (WARN, "a hand-made relink loader exists (from before this installer) - "
                         "left as is, remove it by hand from menu.py if you want this installer to manage it"),
        "old": (WARN, "old loader found - remove it by hand; new entry will be added"),
        None: (INFO, "entry will be added" + ("" if os.path.exists(MENU_PY) else " (menu.py will be created)")),
    }[state]
    rows.append((detail[0], "menu.py", detail[1]))

    return rows


# ======================================================================
# Actions
# ======================================================================

def install_files(log):
    if not os.path.exists(os.path.join(SOURCE, "__init__.py")):
        raise RuntimeError(f'"{APP_NAME}" folder not found next to install.pyw')
    os.makedirs(DEST, exist_ok=True)
    for name in os.listdir(DEST):                  # old code out, keep data
        if name in KEEP_ON_UPDATE:
            continue
        path = os.path.join(DEST, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    for name in os.listdir(SOURCE):
        if name in SKIP_ON_COPY:
            continue
        src, dst = os.path.join(SOURCE, name), os.path.join(DEST, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)
    log(f"Plugin {version_of(DEST) or ''} copied to {DEST}")


def add_menu_entry(log):
    """Make menu.py contain exactly one, current DMB Relink Missing Files block."""
    state = menu_state()
    if state == "current":
        log("menu.py: DMB Tools entry already there - not changed")
        return False
    if state == "manual":
        log("menu.py: a hand-made relink loader exists - not changed (edit by hand)")
        return False
    os.makedirs(NUKE_DIR, exist_ok=True)
    text = read_text(MENU_PY) if os.path.exists(MENU_PY) else ""
    backup_menu(log)

    if state == "outdated":
        text = INSTALLER_BLOCK_RE.sub("\n", text)
        log("menu.py: older entry removed")

    text = text.rstrip("\n")
    text = (text + "\n\n\n" if text else "") + MENU_BLOCK
    write_text(MENU_PY, text)
    log("menu.py: entry added  ->  DMB Tools > Relink Missing Files")
    if state == "old":
        log("NOTE: menu.py still has the OLD loader block - delete it by hand")
    return True


def remove_menu_entry(log):
    text = read_text(MENU_PY)
    if BLOCK_START not in text:
        log("No installer block in menu.py")
        return False
    backup_menu(log)
    write_text(MENU_PY, INSTALLER_BLOCK_RE.sub("\n", text).rstrip("\n") + "\n")
    log("menu.py: entry removed")
    return True


def uninstall(log, keep_settings=True):
    remove_menu_entry(log)
    if os.path.isdir(DEST):
        for name in os.listdir(DEST):
            if keep_settings and name == "data":
                continue
            path = os.path.join(DEST, name)
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        if not os.listdir(DEST):
            os.rmdir(DEST)
        log("Plugin removed" + (" (settings kept in data/)" if os.path.isdir(DEST) else ""))


def update_from_github(log, progress):
    """Download only the files that differ from GitHub (also works as a fresh install)."""
    upd = load_updater()
    repo, branch = upd.repo_settings(SOURCE, DEST)
    log(f"Checking github.com/{repo} ({branch}) ...")
    plan = upd.check(DEST, repo, branch)
    log(f"Installed: {plan['local_version'] or 'none'}   GitHub: {plan['remote_version'] or '?'}")
    if not plan["update_available"]:
        log("Already up to date - nothing to download")
    else:
        log(f"{len(plan['changed'])} file(s) to download, {len(plan['removed'])} to remove")
        for rel in plan["changed"]:
            log("  + " + rel)
        for rel in plan["removed"]:
            log("  - " + rel)
        upd.apply(DEST, plan, progress=lambda d, t, p: progress(d, t))
        log("Files updated")
    add_menu_entry(log)
    return plan


def remote_version():
    upd = load_updater()
    repo, branch = upd.repo_settings(SOURCE, DEST)
    return upd.remote_version(repo, branch), repo


# ======================================================================
# GUI (tkinter - ships with Python, no pip install needed)
# ======================================================================

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    BG, PANEL, FG, DIM, ACCENT = "#14161a", "#1b1f25", "#d7dce2", "#8a93a0", "#3fb7d9"
    COLORS = {OK: "#5fd38d", WARN: "#e5c07b", MISSING: "#e06c75", INFO: DIM}
    ICONS = {OK: "\u2713", WARN: "!", MISSING: "\u2717", INFO: "\u2022"}

    root = tk.Tk()
    root.title("DMB Relink Missing Files - Installer")
    root.configure(bg=BG)
    root.geometry("800x600")
    root.minsize(680, 480)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TProgressbar", troughcolor=PANEL, background=ACCENT, bordercolor=PANEL,
                    lightcolor=ACCENT, darkcolor=ACCENT)

    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=18, pady=(16, 0))
    tk.Label(head, text="DMB Relink Missing Files for Nuke", bg=BG, fg=FG,
             font=("Segoe UI", 15, "bold")).pack(side="left")
    tk.Label(head, text=f"{AUTHOR}  \u00b7  {CONTACT}", bg=BG, fg=DIM,
             font=("Segoe UI", 9)).pack(side="right", pady=(6, 0))
    tk.Label(root, text=f"Installs into {DEST}", bg=BG, fg=DIM,
             font=("Segoe UI", 9)).pack(anchor="w", padx=18)

    checks_frame = tk.Frame(root, bg=PANEL)
    checks_frame.pack(fill="x", padx=18, pady=12)

    btns = tk.Frame(root, bg=BG)
    btns.pack(fill="x", padx=18)

    def make_button(text, cmd, primary=False):
        return tk.Button(btns, text=text, command=cmd, relief="flat", cursor="hand2",
                         bg=ACCENT if primary else PANEL, fg="#0b1a1f" if primary else FG,
                         activebackground="#56c4e3" if primary else "#262b33",
                         activeforeground="#0b1a1f" if primary else FG,
                         font=("Segoe UI", 10, "bold" if primary else "normal"),
                         padx=14, pady=6, bd=0, highlightthickness=0)

    install_btn = make_button("Install / Update", lambda: start(do_install), primary=True)
    github_btn = make_button("Update from GitHub", lambda: start(do_github))
    uninstall_btn = make_button("Uninstall", lambda: confirm_uninstall())
    close_btn = make_button("Close", root.destroy)
    install_btn.pack(side="left")
    github_btn.pack(side="left", padx=8)
    close_btn.pack(side="right")
    uninstall_btn.pack(side="right", padx=8)

    bar = ttk.Progressbar(root, mode="determinate", style="TProgressbar")
    bar.pack(fill="x", padx=18, pady=(12, 0))

    log_box = tk.Text(root, bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                      font=("Consolas", 9), height=12, wrap="word", bd=0, padx=8, pady=6)
    log_box.pack(fill="both", expand=True, padx=18, pady=12)

    events = queue.Queue()
    state = {"busy": False, "remote": None}

    def log(msg):
        events.put(("log", msg))

    def progress(done, total):
        events.put(("progress", (done, total)))

    def refresh_checks():
        for w in checks_frame.winfo_children():
            w.destroy()
        rows = run_checks()
        remote = state["remote"]
        if remote:
            installed = version_of(DEST)
            newer = installed and remote[0] and _vt(remote[0]) > _vt(installed)
            rows.insert(4, (WARN if newer else OK, "GitHub",
                            f"version {remote[0] or '?'} on github.com/{remote[1]}"
                            + ("  - newer, use 'Update from GitHub'" if newer else "")))
        for status, title, detail in rows:
            row = tk.Frame(checks_frame, bg=PANEL)
            row.pack(fill="x", padx=10, pady=3)
            tk.Label(row, text=ICONS[status], width=2, bg=PANEL, fg=COLORS[status],
                     font=("Segoe UI", 11, "bold")).pack(side="left")
            tk.Label(row, text=title, width=12, anchor="w", bg=PANEL, fg=FG,
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(row, text=detail, anchor="w", justify="left", bg=PANEL, fg=DIM,
                     font=("Segoe UI", 9), wraplength=540).pack(side="left", fill="x", expand=True)
        package_ok = os.path.exists(os.path.join(SOURCE, "__init__.py"))
        idle = not state["busy"]
        install_btn.configure(state="normal" if package_ok and idle else "disabled")
        github_btn.configure(state="normal" if idle else "disabled")

    def _vt(v):
        return tuple(int(x) for x in re.findall(r"\d+", v or "0"))

    def pump():
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == "log":
                    log_box.insert("end", payload + "\n")
                    log_box.see("end")
                elif kind == "progress":
                    done, total = payload
                    if total:
                        bar.configure(mode="determinate", maximum=total, value=done)
                    else:
                        bar.configure(mode="indeterminate")
                        bar.step(5)
                elif kind == "remote":
                    state["remote"] = payload
                    refresh_checks()
                elif kind == "done":
                    state["busy"] = False
                    bar.configure(mode="determinate", value=0)
                    refresh_checks()
                    if payload:
                        messagebox.showinfo("DMB Relink Missing Files", payload)
        except queue.Empty:
            pass
        root.after(80, pump)

    def start(job):
        if state["busy"]:
            return
        state["busy"] = True
        for b in (install_btn, github_btn):
            b.configure(state="disabled")

        def runner():
            message = None
            try:
                message = job()
            except Exception as e:
                log(f"ERROR: {e}")
            events.put(("done", message))

        threading.Thread(target=runner, daemon=True).start()

    def do_install():
        log("---- Install / Update (from this folder) ----")
        install_files(log)
        add_menu_entry(log)
        log("Done. Restart Nuke, then open:  DMB Tools > Relink Missing Files")
        return "Installed.\n\nRestart Nuke and open  DMB Tools > Relink Missing Files."

    def do_github():
        log("---- Update from GitHub ----")
        plan = update_from_github(log, progress)
        if plan["update_available"]:
            log("Done. Restart Nuke to load the new version.")
            return f"Updated to {plan['remote_version'] or 'the latest version'}.\n\nRestart Nuke."
        return None

    def confirm_uninstall():
        if state["busy"]:
            return
        answer = messagebox.askyesnocancel(
            "Uninstall DMB Relink Missing Files",
            "Remove the plugin and its menu entry?\n\n"
            "Yes = keep your settings (data folder)\nNo = remove everything\nCancel = do nothing")
        if answer is None:
            return

        def job():
            log("---- Uninstall ----")
            uninstall(log, keep_settings=answer)
            return "Uninstalled. Restart Nuke."
        start(job)

    def fetch_remote():
        try:
            events.put(("remote", remote_version()))
        except Exception as e:
            log(f"GitHub not reachable right now ({e})")

    refresh_checks()
    log("Checked this machine - see the list above.")
    threading.Thread(target=fetch_remote, daemon=True).start()
    pump()
    root.mainloop()


if __name__ == "__main__":
    run_gui()

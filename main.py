"""
Twinclers Guard - Main Entry Point.
Provides wxPython GUI interface and command line (CLI) options.

CLI arguments (used by Windows Explorer Context Menu):
  --add PATH        Add path to watch list, then open GUI
  --protect PATH    Protect path (anti_delete default), then open GUI
  --unprotect PATH  Unprotect path, then open GUI
  --mode MODE       Protection mode: anti_delete, read_only, full_lock
  --test PATH       Test protection and show result in GUI
  --list            List all items (CLI only, does not open GUI)
"""

import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.acl_manager import acl_engine
from core.storage import storage
from core.nvda_speaker import speaker



def run_gui(app=None, cli_args=None):
    """Runs the native wxPython graphical user interface."""
    import wx
    from gui.main_window import MainWindow

    if not app:
        app = wx.App(False)

    frame = MainWindow()
    frame.Show()

    if cli_args:
        wx.CallAfter(frame.process_ipc_args, cli_args)

    app.MainLoop()


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Catches application crashes and saves them to AppData."""
    import traceback
    import datetime
    from core.storage import storage
    from core.i18n import _

    log_dir = os.path.dirname(storage.db_path)
    crash_file = os.path.join(log_dir, "crash.log")

    try:
        with open(crash_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- CRASH: {datetime.datetime.now().isoformat()} ---\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    except OSError:
        pass

    import wx
    app = wx.GetApp()
    if not app:
        app = wx.App(False)

    msg = _("CRASH_MESSAGE", default="A critical error has occurred.", path=crash_file)
    title = _("CRASH_TITLE", default="Twinclers Guard - Fatal Error")
    wx.MessageBox(msg, title, wx.OK | wx.ICON_ERROR)
    sys.exit(1)


def main():
    sys.excepthook = global_exception_handler

    parser = argparse.ArgumentParser(
        description="Twinclers Guard - Folder & File Protector (Windows NTFS ACL)"
    )
    parser.add_argument("--add",       help="Add path to watch list")
    parser.add_argument("--protect",   help="Lock protection on path")
    parser.add_argument("--unprotect", help="Unlock protection on path")
    parser.add_argument("--mode",
                        choices=["anti_delete", "anti_rename_delete",
                                 "append_only", "read_only", "full_lock"],
                        default="anti_delete",
                        help="Protection mode")
    parser.add_argument("--test",  help="Test anti-delete protection on path")
    parser.add_argument("--list",  action="store_true", help="Show item list (CLI only)")
    parser.add_argument("--gui",   action="store_true", help="Force open GUI mode (default)")
    parser.add_argument("--uninstall-cleanup", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # --- Uninstaller Mode ---
    # Called by Inno Setup during the uninstall process
    if args.uninstall_cleanup:
        acl_engine.register_explorer_context_menu(enable=False)
        sys.exit(0)

    # --- Pure CLI Mode ---
    if args.list:
        items = storage.get_all()
        print(f"\n--- TWINCLERS GUARD ITEM LIST ({len(items)}) ---")
        for it in items:
            print(f"* [{it.get('status', 'unprotected').upper()}] ({it.get('mode', 'anti_delete')}) {it['path']}")
        print("--------------------------------------------------\n")
        sys.exit(0)

    # --- Single Instance & IPC ---
    import wx
    app = wx.App(False)
    
    # Use wx.SingleInstanceChecker to prevent double window opening
    checker = wx.SingleInstanceChecker("TwinclersGuard-v1-" + wx.GetUserId())
    
    if checker.IsAnotherRunning():
        # If another instance is already running, send CLI arguments to it (IPC)
        if len(sys.argv) > 1:
            import socket
            import json
            import os
            
            token = ""
            token_file = os.path.join(os.getenv('APPDATA'), 'TwinclersGuard', '.ipc_auth')
            try:
                if os.path.exists(token_file):
                    with open(token_file, 'r', encoding='utf-8') as f:
                        token = f.read().strip()
            except OSError:
                pass

            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect(('127.0.0.1', 49152))
                    payload = {"token": token, "args": sys.argv[1:]}
                    s.sendall(json.dumps(payload).encode('utf-8'))
            except OSError:
                pass
        sys.exit(0)

    # --- Main Instance ---
    # Do not process --protect / --unprotect here as it bypasses the password prompt (Security Flaw)!
    # We pass all arguments to MainWindow to be processed securely through the GUI.
    run_gui(app=app, cli_args=sys.argv[1:])

if __name__ == "__main__":
    main()

import os, re

with open(r'D:/Twinclers/audit_reports.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# Pattern for file citations like: gui/main_window.py:91-109, core/storage.py:84-96, etc.
citations = re.findall(r'([a-zA-Z0-9_\-/\\.]+\.py(?::[0-9,\- ]+)?)', text)
print(f'Total citation matches: {len(citations)}')

files_checked = set()
for c in citations:
    parts = c.split(':')
    rel_path = parts[0].replace('\\', '/').strip()
    full_path = os.path.join(r'D:/Twinclers', rel_path)
    exists = os.path.exists(full_path)
    lines_info = parts[1] if len(parts) > 1 else 'ALL'
    if rel_path not in files_checked:
        files_checked.add(rel_path)
        print(f'File: {rel_path} -> Exists: {exists}')
        if exists:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as src_f:
                src_lines = src_f.readlines()
            print(f'  Total lines in source: {len(src_lines)}')

print('\nDetailed Citation Line Checks:')
# Check specific reported lines
reported_checks = [
    ('gui/main_window.py', 91, 109, 'start_ipc_server / socket'),
    ('gui/main_window.py', 134, 153, 'process_ipc_args / unprotect'),
    ('main.py', 118, 128, 'send_ipc_args'),
    ('core/vault_manager.py', 184, 193, 'aes256_vault lock_item without password'),
    ('core/explorer_monitor.py', 85, 92, 'lock_item call and speech announcement'),
    ('core/storage.py', 84, 103, 'stored_hmac check and fallback'),
    ('core/storage.py', 19, 35, '_get_machine_guid winreg'),
    ('core/vault_crypto.py', 122, 130, 'encrypt_file f.read()'),
    ('core/acl_manager.py', 33, 40, 'get_acl_sddl ps_script interpolation'),
    ('core/acl_manager.py', 82, 154, 'protect method / Deny ACE'),
    ('core/acl_manager.py', 123, 127, 'Full Lock *S-1-1-0:(OI)(CI)(F)'),
    ('core/vault_crypto.py', 38, 57, '_secure_delete 3 passes r+b'),
    ('gui/tray_icon.py', 102, 109, 'on_unprotect_all loop'),
    ('core/explorer_monitor.py', 45, 114, 'run COM Shell.Application loop'),
    ('core/vault_crypto.py', 75, 84, 'hash_password PBKDF2'),
    ('core/vault_crypto.py', 97, 105, '_derive_aes_key PBKDF2'),
    ('core/vault_crypto.py', 27, 28, '_HEADER_PREFIX'),
    ('core/vault_crypto.py', 59, 69, '_obfuscate_header'),
    ('core/vault_crypto.py', 31, 36, '_wipe_buffer ctypes.memset'),
    ('core/storage.py', 125, 130, 'save() open w'),
    ('gui/main_window.py', 521, 644, 'protect/unprotect handlers'),
    ('gui/tray_icon.py', 94, 109, 'tray protect/unprotect handlers'),
    ('main.py', 83, 86, 'argparse mode choices'),
    ('core/acl_manager.py', 216, 305, 'shell context menu / registry repair'),
    ('core/storage.py', 158, 168, 'add_item default dict'),
    ('core/storage.py', 182, 192, 'update_item default dict'),
    ('core/nvda_speaker.py', 33, 34, 'except Exception: pass in speak'),
    ('gui/main_window.py', 164, 178, 'select_path_in_list GetItemText column 2 vs 0')
]

for rel_path, s_line, e_line, desc in reported_checks:
    full_path = os.path.join(r'D:/Twinclers', rel_path)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as sf:
            slines = sf.readlines()
        sample = ''.join(slines[max(0, s_line-1):min(len(slines), e_line)])
        print(f'=== CHECK {rel_path}:{s_line}-{e_line} ({desc}) ===')
        print(sample[:300] + ('...' if len(sample) > 300 else ''))
    else:
        print(f'ERROR: File not found: {rel_path}')

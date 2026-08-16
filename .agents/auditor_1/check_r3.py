import os, re

with open(r'D:/Twinclers/audit_reports.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

r3_pattern = r'\b([a-zA-Z0-9_\-]+),\s+([a-zA-Z0-9_\-]+),\s+(?:dan|serta|atau)\s+([a-zA-Z0-9_\-]+)\b'
for idx, l in enumerate(lines, 1):
    m = re.findall(r3_pattern, l, re.IGNORECASE)
    if m:
        print(f'Line {idx}: {m} => {l.strip()[:100]}')

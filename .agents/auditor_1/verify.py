import os, re, json

with open(r'D:/Twinclers/audit_reports.txt', 'r', encoding='utf-8') as f:
    text = f.read()
    lines = text.splitlines()

print('=== 1. AI Buzzwords ===')
buzzwords = ['delve', 'tapestry', 'testament', 'symphony', 'realm', 'landscape', 'intricate', 'meticulous', 'pivotal', 'renowned', 'dynamic', 'leverage', 'underscore', 'paramount', 'notable', 'crucial', 'vital']
bw_matches = []
for bw in buzzwords:
    for idx, l in enumerate(lines, 1):
        if re.search(r'\b' + bw + r'\b', l, re.IGNORECASE):
            bw_matches.append((bw, idx, l.strip()))
print(f'Total buzzwords found: {len(bw_matches)}')
for m in bw_matches:
    print(m)

print('\n=== 2. Robotic Transitions ===')
transitions = [
    'in conclusion', 'it is important to note', 'ultimately', 'it is worth mentioning',
    'perlu dicatat bahwa', 'kesimpulannya', 'pada akhirnya', 'penting untuk dicatat',
    'secara keseluruhan', 'tidak kalah penting', 'perlu diperhatikan bahwa', 'dapat disimpulkan',
    'oleh karena itu dapat', 'sebagai kesimpulan'
]
tr_matches = []
for tr in transitions:
    for idx, l in enumerate(lines, 1):
        if re.search(r'\b' + tr + r'\b', l, re.IGNORECASE):
            tr_matches.append((tr, idx, l.strip()))
print(f'Total robotic transitions found: {len(tr_matches)}')
for m in tr_matches:
    print(m)

print('\n=== 3. Negative Parallel Syntax ===')
neg_patterns = [
    r'bukan\s+(?:hanya|cuma)\s+.*?tapi\s+(?:juga)?',
    r'bukan\s+(?:hanya|cuma)\s+.*?melainkan\s+(?:juga)?',
    r'not\s+only\b.*?but\s+(?:also)?',
    r'\b(?:daripada|rather\s+than)\b'
]
neg_matches = []
for np in neg_patterns:
    for idx, l in enumerate(lines, 1):
        if re.search(np, l, re.IGNORECASE):
            neg_matches.append((np, idx, l.strip()))
print(f'Total negative syntax found: {len(neg_matches)}')
for m in neg_matches:
    print(m)

import os
import re
import sys

REPORT_PATH = r'd:/Twinclers/audit_reports.txt'
ROOT_DIR = r'd:/Twinclers'
RULES_PATH = r'D:\Twinclers\.agents\rules\agent_rules.md'

print('=== VICTORY AUDITOR INDEPENDENT VERIFICATION ===')

# Check 1: Existence & Non-empty
if not os.path.exists(REPORT_PATH):
    print('[FAIL] audit_reports.txt does not exist!')
    sys.exit(1)

size = os.path.getsize(REPORT_PATH)
if size == 0:
    print('[FAIL] audit_reports.txt is empty!')
    sys.exit(1)

print(f'[PASS] audit_reports.txt exists, size: {size} bytes')

with open(REPORT_PATH, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.splitlines()

print(f'Total lines in report: {len(lines)}')

# Check 2: Forbidden Buzzwords in Report Text
forbidden_buzzwords = [
    'delve', 'tapestry', 'testament', 'symphony', 'realm', 'landscape',
    'intricate', 'meticulous', 'pivotal', 'renowned', 'dynamic', 'leverage',
    'underscore', 'paramount', 'notable', 'crucial', 'vital'
]

# We should be careful to check outside of code snippets or literal mentions
buzzword_hits = []
for idx, line in enumerate(lines, 1):
    lower_line = line.lower()
    for word in forbidden_buzzwords:
        # Match whole word
        pattern = r'\b' + re.escape(word) + r'\b'
        matches = re.finditer(pattern, lower_line)
        for m in matches:
            # Check if it is merely quoting the rule
            if 'agent_rules' in lower_line or 'dilarang' in lower_line or 'buzzword' in lower_line or 'kata terlarang' in lower_line:
                continue
            buzzword_hits.append((idx, word, line.strip()))

if buzzword_hits:
    print(f'[FAIL] Found {len(buzzword_hits)} forbidden buzzwords:')
    for lno, word, text in buzzword_hits:
        print(f'  Line {lno}: [{word}] in: {text[:80]}')
else:
    print('[PASS] Zero forbidden AI buzzwords in report text')

# Check 3: Robotic Transition Phrases
robotic_phrases = [
    r'\bit is important to note\b',
    r'\bin conclusion\b',
    r'\bultimately\b',
    r'\bit is worth mentioning\b',
    r'\bpenting untuk dicatat\b',
    r'\bkesimpulannya\b',
    r'\bpada akhirnya\b',
    r'\bperlu disebutkan\b',
    r'\bperlu dicatat bahwa\b'
]

robotic_hits = []
for idx, line in enumerate(lines, 1):
    lower_line = line.lower()
    for pat in robotic_phrases:
        if re.search(pat, lower_line):
            if 'agent_rules' in lower_line or 'dilarang' in lower_line:
                continue
            robotic_hits.append((idx, pat, line.strip()))

if robotic_hits:
    print(f'[FAIL] Found {len(robotic_hits)} robotic transition phrases:')
    for lno, pat, text in robotic_hits:
        print(f'  Line {lno}: [{pat}] in: {text[:80]}')
else:
    print('[PASS] Zero robotic transition phrases in report text')

# Check 4: Negative Parallel Syntax ( Not just X but also Y / tidak hanya X tetapi juga Y)
neg_parallel_patterns = [
    r'tidak hanya\b.*?\btetapi juga\b',
    r'tidak hanya\b.*?\bnamun juga\b',
    r'bukan hanya\b.*?\btetapi juga\b',
    r'bukan hanya\b.*?\bmelainkan juga\b',
    r'not only\b.*?\bbut also\b',
    r'not just\b.*?\bbut also\b',
]

neg_parallel_hits = []
for idx, line in enumerate(lines, 1):
    lower_line = line.lower()
    for pat in neg_parallel_patterns:
        if re.search(pat, lower_line):
            if 'agent_rules' in lower_line or 'dilarang' in lower_line:
                continue
            neg_parallel_hits.append((idx, pat, line.strip()))

if neg_parallel_hits:
    print(f'[FAIL] Found {len(neg_parallel_hits)} negative parallel syntax occurrences:')
    for lno, pat, text in neg_parallel_hits:
        print(f'  Line {lno}: in: {text[:80]}')
else:
    print('[PASS] Zero negative parallel syntax occurrences')

# Check 5: Severity Extraction & Remediation Check
# Let us find all issues and their severities
issue_sections = []
current_issue = None

issue_pattern = re.compile(r'^(?:###|\d+\.)\s+(?:\[(CRITICAL|HIGH|MEDIUM|LOW)\]|Temuan\s+\d+|[\w\s]+-\s*(CRITICAL|HIGH|MEDIUM|LOW))', re.IGNORECASE)

severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
for line in lines:
    for sev in severity_counts.keys():
        if f'[{sev}]' in line or f'Tingkat Keparahan: {sev}' in line or f'Severity: {sev}' in line or f'Keparahan: {sev}' in line or f'**Severity**: {sev}' in line or f'**Tingkat Keparahan**: {sev}' in line:
            severity_counts[sev] += 1

print(f'Severity count indications: {severity_counts}')

# Check 6: File & Line Citation Verification
# Search for patterns like core/foo.py:123, core\foo.py, line references
citation_patterns = [
    r'((?:core|gui|libs|locales|build_scripts|main\.py)[/\\a-zA-Z0-9_\.]*\.py|\.json|\.txt|\.bat|\.iss)(?:[:,]\s*(?:baris\s*)?(\d+)(?:-(\d+))?)?',
    r'((?:core|gui|libs|locales|build_scripts|main\.py)[/\\a-zA-Z0-9_\.]*).*?(?:baris|line)\s*(\d+)(?:-(\d+))?'
]

citations_found = []
for idx, line in enumerate(lines, 1):
    # match patterns like core/vault_crypto.py:45 or core/vault_crypto.py baris 45
    matches = re.finditer(r'([a-zA-Z0-9_\/\\]+\.(?:py|json|txt|bat|iss))(?::(\d+)(?:-(\d+))?|\s+baris\s+(\d+)(?:-(\d+))?)?', line)
    for m in matches:
        filepath = m.group(1).replace('\\', '/')
        # check if it starts with valid project folder/file
        if filepath.startswith(('core/', 'gui/', 'libs/', 'locales/', 'build_scripts/', 'main.py', 'help.txt', 'run.bat', 'README.md', 'scratch_wiki.txt')):
            start_line = m.group(2) or m.group(4)
            end_line = m.group(3) or m.group(5)
            citations_found.append((idx, filepath, start_line, end_line, line.strip()))

print(f'Total citations extracted: {len(citations_found)}')

# Verify each cited file exists and check line ranges
invalid_files = []
invalid_lines = []
valid_citations = 0

for rep_lno, rel_path, s_line, e_line, src_text in citations_found:
    full_path = os.path.join(ROOT_DIR, rel_path)
    if not os.path.exists(full_path):
        invalid_files.append((rep_lno, rel_path))
        continue
    
    if s_line:
        s_val = int(s_line)
        e_val = int(e_line) if e_line else s_val
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            target_lines = f.readlines()
            total_target_lines = len(target_lines)
            if s_val > total_target_lines or e_val > total_target_lines or s_val < 1:
                invalid_lines.append((rep_lno, rel_path, s_val, e_val, total_target_lines))
            else:
                valid_citations += 1
    else:
        valid_citations += 1

print(f'Valid citations: {valid_citations}')
if invalid_files:
    print(f'[FAIL] Invalid file paths cited ({len(invalid_files)}): {invalid_files[:5]}')
else:
    print('[PASS] All cited file paths exist on disk.')

if invalid_lines:
    print(f'[FAIL] Invalid line numbers cited ({len(invalid_lines)}): {invalid_lines[:5]}')
else:
    print('[PASS] All cited line numbers are within valid ranges.')


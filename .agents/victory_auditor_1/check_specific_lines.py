with open(r'd:/Twinclers/audit_reports.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line_idx in [121, 333, 690, 702, 715]:
    start = max(0, line_idx - 5)
    end = min(len(lines), line_idx + 5)
    print(f'=== Context around line {line_idx} ===')
    for i in range(start, end):
        print(f'{i+1:3d}: {lines[i].rstrip()}')
    print()


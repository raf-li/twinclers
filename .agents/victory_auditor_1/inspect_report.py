with open(r'd:/Twinclers/audit_reports.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('First 60 lines:')
for i in range(min(60, len(lines))):
    print(f'{i+1:3d}: {lines[i].rstrip()}')


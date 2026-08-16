import os

# 1. Check help_parser.py:77-82
with open(r'D:/Twinclers/core/help_parser.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print('=== help_parser.py:75-85 ===')
print(''.join(lines[74:85]))

# 2. Check nvda_speaker.py exception lines
with open(r'D:/Twinclers/core/nvda_speaker.py', 'r', encoding='utf-8') as f:
    nvda_lines = f.readlines()
print('=== nvda_speaker.py total lines ===', len(nvda_lines))
nvda_targets = [33, 49, 60, 69, 88, 101, 111, 121, 129, 137]
for lno in nvda_targets:
    if lno <= len(nvda_lines):
        print(f'Line {lno}: {nvda_lines[lno-1].strip()}')

# 3. Check help.txt vs locales/help_en.txt
h1 = os.path.getsize(r'D:/Twinclers/help.txt') if os.path.exists(r'D:/Twinclers/help.txt') else -1
h2 = os.path.getsize(r'D:/Twinclers/locales/help_en.txt') if os.path.exists(r'D:/Twinclers/locales/help_en.txt') else -1
print(f'help.txt size: {h1}, locales/help_en.txt size: {h2}')

# 4. Check scratch_wiki.txt
sw = os.path.getsize(r'D:/Twinclers/scratch_wiki.txt') if os.path.exists(r'D:/Twinclers/scratch_wiki.txt') else -1
print(f'scratch_wiki.txt size: {sw}')

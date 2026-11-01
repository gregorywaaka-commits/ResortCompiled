#!/usr/bin/env python3
"""Configure the checked-in WSR runtime/map for a build from your own disc.

The edition comes from the game ID of the extracted disc (projects/editions.json): PAL RZTP01 or USA SP2E01.
No Mario Kart Wii reference or re-keying is required for release builds.
"""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'scripts'))
import editions  # noqa: E402

extracted = editions.data_root()
game_id, edition = editions.check(extracted)
project = root / edition['project']
runtime = editions.runtime(extracted)
text = (project / 'recomp.yml').read_text()
replacements = {
    r'(?m)^(    path: ).*\.dol$': str(extracted / edition['program']),
    r'(?m)^(    path: ).*MAP\.txt$': str(project / 'MAP.txt'),
    r'(?m)^(  native_registration_root: ).*$': str(runtime / 'src'),
    r'(?m)^(  root: ).*$': str(root / 'work/generated'),
}
for pattern, value in replacements.items():
    text, count = re.subn(pattern, lambda match: match[1] + value, text)
    if count != 1: raise SystemExit('Unsupported project template layout.')
if not (root / 'external/wiicompiled/translator').is_dir():
    raise SystemExit('Run bash setup.sh before configuring the project.')
destination = root / 'external/wiicompiled/projects' / project.name / 'recomp.yml'
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(text)
(root / 'work/edition.txt').write_text(game_id + '\n')
print(f'Configured {destination} for {game_id} ({edition["name"]}) from the checked-in map/runtime.')

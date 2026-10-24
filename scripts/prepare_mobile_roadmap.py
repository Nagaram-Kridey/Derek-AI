"""Prepare public static assets only. Never reads owner DB, .env or runtime state."""
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
target = root / 'web_dashboard/dist-roadmap'
catalog = json.loads((root / 'backend/assistant/roadmap_seed.json').read_text(encoding='utf-8'))
for block in catalog:
    block.update(evidence='', notes='', owner_action='Review setup requirements in your private local roadmap.',
                 next_step='Review implementation and record acceptance evidence.',
                 description=f"{block['title']}. {block['origin']} feature in {block['phase']}.")
(target / 'catalog.json').write_text(json.dumps(catalog, indent=2), encoding='utf-8')
(target / '.nojekyll').touch()
shutil.copyfile(target / 'roadmap.html', target / 'index.html')
shutil.copyfile(root / 'docs/roadmap.svg', target / 'roadmap.svg')
print('Prepared public catalog and assets. No live or owner data included.')

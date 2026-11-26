"""Location configuration; production locations stay outside the source repo."""

import json
import os
from pathlib import Path


def load_beaches(path=None):
    path = Path(path or os.environ.get('BEACH_CONFIG_FILE') or Path(__file__).with_name('beaches.example.json'))
    values = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(values, list) or not 1 <= len(values) <= 50:
        raise ValueError('Configure between one and fifty beach locations')
    result = []
    names = set()
    for value in values:
        item = dict(value)
        if not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('Each location needs a name')
        if item['name'] in names:
            raise ValueError('Location names must be unique')
        names.add(item['name'])
        if item.get('type') not in ['sea', 'douro', 'lake', 'limens']:
            raise ValueError('Unsupported regional data source type')
        item['lat'], item['lon'] = float(item['lat']), float(item['lon'])
        if not -90 <= item['lat'] <= 90 or not -180 <= item['lon'] <= 180:
            raise ValueError('Invalid location coordinates')
        result.append(item)
    return result

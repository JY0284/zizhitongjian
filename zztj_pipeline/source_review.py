"""Aligned classical-source evidence and narrowly reviewed translation repairs.

The paid extraction and translated book are never modified. Corrections affect
the derived view only, and require the reviewed passage and source quotation.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ZISI_PASSAGES = {'1-23-1', '1-23-2', '1-23-3', '2-26-2', '2-26-3'}
REVIEWED_PLACE_ALIASES = {'蜀国': '蜀', '蜀地': '蜀', '安邑城': '安邑', '阳翟城': '阳翟'}


def apply_reviewed_place_aliases(extraction):
    """Reviewed first-five-volume geographical spellings, not entity aliases.

    State/person entities retain their own types and names. These broad place
    labels do not establish an ancient boundary or a verified coordinate.
    """
    if not 1 <= extraction['juan_index'] <= 5:
        return extraction
    result = deepcopy(extraction)
    for location in result.get('locations', []):
        original = location['name']
        if original in REVIEWED_PLACE_ALIASES:
            location['name'] = REVIEWED_PLACE_ALIASES[original]
            location['alias'] = list(dict.fromkeys([*location.get('alias', []), original]))
    for field in ('events', 'relations'):
        for item in result.get(field, []):
            if item.get('location') in REVIEWED_PLACE_ALIASES:
                item['location'] = REVIEWED_PLACE_ALIASES[item['location']]
    return result


def aligned_sources(store_dir, source_path=ROOT / 'data.json'):
    source = json.loads(Path(source_path).read_text(encoding='utf-8'))
    chapters = {int(chapter['index']): chapter for chapter in source['chapters']}
    result = {}
    for path in Path(store_dir).glob('juan_*.json'):
        for key, chunk in json.loads(path.read_text(encoding='utf-8')).items():
            chapter = chapters.get(chunk['juan_index'])
            if chapter is None:
                continue
            try:
                paired = chapter['segments'][chunk['segment_index'] - 1]['sentences'][chunk['chunk_start_index']]
            except IndexError:
                continue
            translated = paired['translated'].strip()
            normalize = lambda text: re.sub(r'^\[\d+\]\s*', '', text).strip()
            if [normalize(text) for text in chunk['source_sentences']] != [normalize(translated)]:
                continue  # Never attach evidence to a misaligned translation.
            result[key] = {'original': paired['original'], 'translated': translated}
    return result


def apply_reviewed_identity(extraction, original):
    key = f"{extraction['juan_index']}-{extraction['segment_index']}-{extraction['chunk_start_index']}"
    if key not in ZISI_PASSAGES or '子思' not in original or '孔子' in original:
        return extraction
    if not any(e['name'] == '孔' and e.get('entity_type') in (None, 'person') for e in extraction.get('entities', [])):
        return extraction
    result = deepcopy(extraction)
    for entity in result['entities']:
        if entity['name'] == '孔' and entity.get('entity_type') in (None, 'person'):
            entity['name'] = '子思'
            entity['alias'] = list(dict.fromkeys([*entity.get('alias', []), '孔']))
    for field, refs in [('events', ['participants']), ('locations', ['related_entities']),
                        ('relations', ['from_roles', 'to_roles'])]:
        for item in result.get(field, []):
            for ref in refs:
                item[ref] = ['子思' if name == '孔' else name for name in item.get(ref, [])]
    # Keep the derived titles and their references consistent with the reviewed
    # identity. Verbatim quotations and source_sentences remain untouched.
    for field, texts in [('events', ['name', 'description', 'background', 'significance']),
                         ('relations', ['event_name', 'context', 'result'])]:
        for item in result.get(field, []):
            for text in texts:
                if isinstance(item.get(text), str):
                    item[text] = re.sub(r'孔(?!子)', '子思', item[text])
    return result

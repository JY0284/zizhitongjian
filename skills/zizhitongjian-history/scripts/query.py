"""Read-only, dependency-free JSON queries for a local zizhitongjian checkout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import quote

COLLECTIONS = {
    'role': 'roles', 'location': 'locations', 'polity': 'polities',
    'organization': 'organizations', 'school': 'schools',
    'event': 'events', 'relation': 'relations',
}
READER = 'https://jy0284.github.io/zizhitongjian/'
SOURCE = 'https://github.com/JY0284/zizhitongjian/blob/main/'


def page(items: list, limit: int, offset: int) -> dict:
    return {'items': items[offset:offset + limit], 'total': len(items),
            'offset': offset, 'limit': limit, 'has_more': offset + limit < len(items)}


class History:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.chapters = {}
        for path in sorted((self.root / 'chapters').glob('[0-9][0-9][0-9]_*.md')):
            self.chapters[int(path.name.split('_', 1)[0])] = path
        if not self.chapters:
            raise ValueError('No chapters found; pass --repo with the cloned repository path')
        snapshot = self.root / 'visualization/snapshot/unified_knowledge.json'
        self.kb = json.loads(snapshot.read_text(encoding='utf-8'))
        self.passages = self.kb.get('source_passages', {})

    def coverage(self) -> dict:
        return {'text_volumes': sorted(self.chapters),
                'structured_coverage': self.kb.get('data_coverage', []),
                'models': self.kb.get('extraction_models', []),
                'notice': self.kb.get('data_notice', ''),
                'counts': {kind: len(self.kb.get(name, {})) for kind, name in COLLECTIONS.items()}}

    def chapter_path(self, juan: int) -> Path:
        if juan not in self.chapters:
            raise ValueError(f'Unknown volume: {juan}')
        return self.chapters[juan]

    def citation(self, juan: int, line: int | None = None) -> dict:
        relative = self.chapter_path(juan).relative_to(self.root).as_posix()
        return {'juan': juan, 'path': relative,
                'source_url': SOURCE + quote(relative) + (f'#L{line}' if line else ''),
                'reader_url': READER + quote(relative.removesuffix('.md') + '.html')}

    def chapter(self, juan: int, start: int, limit: int) -> dict:
        lines = self.chapter_path(juan).read_text(encoding='utf-8-sig').splitlines()
        if start > len(lines):
            raise ValueError(f'start-line exceeds chapter length ({len(lines)})')
        return {**self.citation(juan, start), 'total_lines': len(lines),
                'lines': [{'line': i + 1, 'text': lines[i]}
                          for i in range(start - 1, min(start - 1 + limit, len(lines)))],
                'has_more': start - 1 + limit < len(lines)}

    def passage(self, passage_id: str) -> dict:
        if passage_id not in self.passages:
            raise ValueError('Unknown passage ID; paired extracted passages cover only the published volumes')
        juan, segment, chunk = map(int, passage_id.split('-'))
        return {'id': passage_id, **self.citation(juan), 'segment': segment,
                'chunk_index': chunk, **self.passages[passage_id]}

    @staticmethod
    def summary(kind: str, item: dict) -> dict:
        keys = ('id', 'canonical_name', 'name', 'all_names', 'primary_power',
                'juans_appeared', 'source_juans', 'from_entity', 'to_entity',
                'primary_action', 'time_start', 'time_end',
                'first_interaction_year', 'last_interaction_year')
        result = {'kind': kind, **{key: item[key] for key in keys if key in item}}
        description = item.get('description', '')
        result.update(description=description[:400], description_truncated=len(description) > 400)
        return result

    def search(self, query: str, kind: str, juan: int | None, limit: int, offset: int) -> dict:
        if not query.strip():
            raise ValueError('Search query must not be blank')
        if juan is not None:
            self.chapter_path(juan)
        needle, results = query.casefold(), []
        if kind == 'text':
            for number, path in self.chapters.items():
                if juan is not None and number != juan:
                    continue
                for line, text in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
                    at = text.casefold().find(needle)
                    if at < 0:
                        continue
                    start, end = max(0, at - 120), min(len(text), at + len(query) + 200)
                    results.append({**self.citation(number, line), 'line': line,
                                    'text': text[start:end], 'truncated': start > 0 or end < len(text)})
        else:
            kinds = ['event'] if kind == 'event' else list(COLLECTIONS)[:5]
            for entity_kind in kinds:
                for item_id, raw in self.kb.get(COLLECTIONS[entity_kind], {}).items():
                    item = {**raw, 'id': item_id}
                    volumes = item.get('juans_appeared', item.get('source_juans', []))
                    if juan is not None and juan not in volumes:
                        continue
                    names = [item_id, item.get('canonical_name', ''), item.get('name', ''),
                             *item.get('all_names', [])]
                    if kind == 'event':
                        names += [item.get('description', ''), item.get('location') or '',
                                  *item.get('participants', [])]
                    if any(needle in name.casefold() for name in names):
                        results.append(self.summary(entity_kind, item))
        return {'query': query, 'kind': kind, 'juan': juan, **page(results, limit, offset)}

    def source_refs(self, item: dict) -> list:
        # Entity occurrences carry a chunk index; event/relation evidence often
        # only identifies a segment. Do not pretend those are exact quotations.
        matches = {}
        for occurrence in item.get('occurrences', []):
            juan, segment = occurrence.get('juan_index'), occurrence.get('segment_index')
            if juan is None or segment is None:
                continue
            chunk = occurrence.get('chunk_index')
            if chunk is not None:
                key = f'{juan}-{segment}-{chunk}'
                if key in self.passages:
                    matches[key] = 'chunk'
            else:
                for key in self.passages:
                    if key.startswith(f'{juan}-{segment}-'):
                        matches.setdefault(key, 'segment')
        for segment in item.get('source_segments', []):
            for key in self.passages:
                if key.startswith(f'{segment}-'):
                    matches.setdefault(key, 'segment')
        return [{'id': key, 'match_granularity': matches[key]}
                for key in sorted(matches, key=lambda value: tuple(map(int, value.split('-'))))]

    def get(self, kind: str, item_id: str, limit: int, offset: int) -> dict:
        collection = self.kb.get(COLLECTIONS[kind], {})
        if item_id not in collection:
            raise ValueError(f'Unknown {kind} ID; use search to find an exact ID')
        item = collection[item_id]
        detail, lists = {}, {}
        for key, value in item.items():
            if isinstance(value, list) and key != 'coordinates':
                if key == 'occurrences':
                    value = [{k: v for k, v in row.items() if k != 'source_sentence'} for row in value]
                lists[key] = page(value, limit, offset)
            else:
                detail[key] = value
        return {'kind': kind, 'id': item_id, 'detail': detail, 'lists': lists,
                'sources': page(self.source_refs(item), limit, offset)}

    def neighbors(self, item_id: str, limit: int, offset: int) -> dict:
        entity_kinds = [kind for kind, name in list(COLLECTIONS.items())[:5]
                        if item_id in self.kb.get(name, {})]
        if not entity_kinds:
            raise ValueError('Unknown entity ID; use search to find an exact ID')
        relations = [self.summary('relation', {**item, 'id': key})
                     for key, item in self.kb.get('relations', {}).items()
                     if item_id in (item.get('from_entity'), item.get('to_entity'))]
        return {'entity_id': item_id, 'entity_kinds': entity_kinds,
                'ambiguous_entity_id': len(entity_kinds) > 1, **page(relations, limit, offset)}


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def nonnegative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError('must be nonnegative')
    return number


def bounded_limit(value: str) -> int:
    number = positive(value)
    if number > 200:
        raise argparse.ArgumentTypeError('maximum limit is 200')
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3],
                        help='Checkout root; required when the skill has been copied elsewhere')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('coverage')
    search = commands.add_parser('search')
    search.add_argument('query')
    search.add_argument('--kind', choices=['text', 'entity', 'event'], default='text')
    search.add_argument('--juan', type=positive)
    get = commands.add_parser('get')
    get.add_argument('kind', choices=COLLECTIONS)
    get.add_argument('id')
    neighbors = commands.add_parser('neighbors')
    neighbors.add_argument('id')
    for command in [search, get, neighbors]:
        command.add_argument('--limit', type=bounded_limit, default=5)
        command.add_argument('--offset', type=nonnegative, default=0)
    passage = commands.add_parser('passage')
    passage.add_argument('id')
    chapter = commands.add_parser('chapter')
    chapter.add_argument('juan', type=positive)
    chapter.add_argument('--start-line', type=positive, default=1)
    chapter.add_argument('--limit', type=bounded_limit, default=80)
    args = parser.parse_args(argv)
    try:
        history = History(args.repo)
        if args.command == 'coverage':
            result = history.coverage()
        elif args.command == 'search':
            result = history.search(args.query, args.kind, args.juan, args.limit, args.offset)
        elif args.command == 'get':
            result = history.get(args.kind, args.id, args.limit, args.offset)
        elif args.command == 'neighbors':
            result = history.neighbors(args.id, args.limit, args.offset)
        elif args.command == 'chapter':
            result = history.chapter(args.juan, args.start_line, args.limit)
        else:
            result = history.passage(args.id)
        output = {'command': args.command,
                  'structured_juans': [row['juan'] for row in history.kb.get('data_coverage', [])],
                  'notice': '模型抽取仅作检索线索；请核对原文。未检索到不等于历史上不存在。',
                  'result': result}
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())

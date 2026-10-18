"""Behavioral regression checks for the distributable history skill (stdlib only)."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/zizhitongjian-history/scripts/query.py'
SPEC = importlib.util.spec_from_file_location('history_query', SCRIPT)
QUERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUERY)


class AgentQueryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'checkout'
        (self.root / 'chapters').mkdir(parents=True)
        (self.root / 'chapters/003_周纪.md').write_text(
            '第三卷\n\n秦王使甘茂诛蜀相壮。\n秦王派甘茂诛杀陈庄。\n', encoding='utf-8')
        (self.root / 'chapters/006_秦纪.md').write_text('第六卷\n荆轲入秦。\n', encoding='utf-8')
        role = {'id': '陈庄', 'canonical_name': '陈庄', 'all_names': ['陈庄', '蜀相壮'],
                'description': '蜀相', 'juans_appeared': [3], 'occurrences': [
                    {'juan_index': 3, 'segment_index': 11, 'chunk_index': 0, 'source_sentence': '原句'},
                    {'juan_index': 3, 'segment_index': 11, 'chunk_index': 1}]}
        self.kb = {'roles': {'陈庄': role, '甘茂': {'id': '甘茂', 'juans_appeared': [3]}},
                   'locations': {'蜀': {'id': '蜀', 'all_names': ['蜀国'], 'coordinates': [104.1, 30.6]}},
                   'polities': {'蜀': {'id': '蜀', 'all_names': ['蜀国']}},
                   'events': {'杀陈庄': {'id': '杀陈庄', 'name': '诛杀陈庄', 'participants': ['甘茂'],
                                       'source_juans': [3], 'source_segments': ['3-11'], 'time_start': None}},
                   'relations': {
                       '甘茂->陈庄': {'from_entity': '甘茂', 'to_entity': '陈庄', 'primary_action': '诛杀',
                                     'first_interaction_year': None, 'occurrences': [
                                         {'juan_index': 3, 'segment_index': 11}]},
                       '秦->蜀': {'from_entity': '秦', 'to_entity': '蜀'}},
                   'data_coverage': [{'juan': 3, 'complete': True, 'processed': 2, 'total': 2}],
                   'extraction_models': ['test-model'],
                   'source_passages': {
                       '3-11-0': {'original': '秦王使甘茂诛蜀相壮。', 'translated': '秦王派甘茂诛杀陈庄。'},
                       '3-11-1': {'original': '其他上下文', 'translated': '其他上下文'},
                       '3-110-0': {'original': '另一段', 'translated': '另一段'}}}
        snapshot = self.root / 'visualization/snapshot'
        snapshot.mkdir(parents=True)
        (snapshot / 'unified_knowledge.json').write_text(json.dumps(self.kb, ensure_ascii=False), encoding='utf-8')
        self.history = QUERY.History(self.root)

    def test_full_text_beyond_structured_coverage_and_line_citation(self):
        result = self.history.search('荆轲', 'text', None, 5, 0)
        self.assertEqual(result['total'], 1)
        hit = result['items'][0]
        self.assertEqual((hit['juan'], hit['line']), (6, 2))
        self.assertTrue(hit['source_url'].endswith('#L2'))
        self.assertEqual(self.history.chapter(6, 2, 1)['lines'][0]['text'], '荆轲入秦。')
        self.assertEqual(self.history.search('荆轲', 'entity', 6, 5, 0)['total'], 0)
        self.assertEqual([x['juan'] for x in self.history.coverage()['structured_coverage']], [3])

    def test_aliases_preserve_entity_kinds(self):
        result = self.history.search('蜀国', 'entity', None, 5, 0)
        self.assertEqual({x['kind'] for x in result['items']}, {'location', 'polity'})
        result = self.history.search('蜀相壮', 'entity', 3, 5, 0)
        self.assertEqual(result['items'][0]['id'], '陈庄')
        self.assertTrue(self.history.neighbors('蜀', 5, 0)['ambiguous_entity_id'])

    def test_zero_based_chunk_exactness_and_pagination(self):
        first = self.history.get('role', '陈庄', 1, 0)
        self.assertEqual(first['sources']['items'], [{'id': '3-11-0', 'match_granularity': 'chunk'}])
        self.assertTrue(first['sources']['has_more'])
        second = self.history.get('role', '陈庄', 1, 1)
        self.assertEqual(second['sources']['items'][0]['id'], '3-11-1')
        self.assertFalse(second['sources']['has_more'])
        passage = self.history.passage(first['sources']['items'][0]['id'])
        self.assertEqual(passage['original'], '秦王使甘茂诛蜀相壮。')
        self.assertNotEqual(passage['original'], passage['translated'])

    def test_segment_sources_are_candidates_not_false_exact_matches(self):
        for kind, item_id in [('event', '杀陈庄'), ('relation', '甘茂->陈庄')]:
            sources = self.history.get(kind, item_id, 5, 0)['sources']['items']
            self.assertEqual({x['id'] for x in sources}, {'3-11-0', '3-11-1'})
            self.assertEqual({x['match_granularity'] for x in sources}, {'segment'})

    def test_relation_direction_and_unknown_date_are_preserved(self):
        relations = self.history.neighbors('陈庄', 5, 0)
        self.assertEqual(relations['total'], 1)
        edge = relations['items'][0]
        self.assertEqual((edge['from_entity'], edge['to_entity']), ('甘茂', '陈庄'))
        self.assertIsNone(edge['first_interaction_year'])
        self.assertFalse(relations['ambiguous_entity_id'])

    def test_event_participant_search_and_filter(self):
        self.assertEqual(self.history.search('甘茂', 'event', 3, 5, 0)['total'], 1)
        self.assertEqual(self.history.search('甘茂', 'event', 6, 5, 0)['total'], 0)

    def test_coordinates_remain_a_pair_at_any_page_offset(self):
        self.assertEqual(self.history.get('location', '蜀', 1, 10)['detail']['coordinates'], [104.1, 30.6])

    def test_unknown_ids_and_out_of_range_lines_do_not_fall_back(self):
        for call in [lambda: self.history.get('role', '../陈庄', 5, 0),
                     lambda: self.history.passage('6-1-0'),
                     lambda: self.history.neighbors('不存在', 5, 0),
                     lambda: self.history.chapter(3, 9999, 5),
                     lambda: self.history.search(' ', 'text', None, 5, 0)]:
            with self.assertRaises(ValueError):
                call()

    def test_copied_skill_cli_works_outside_checkout_without_dependencies(self):
        copied = self.root.parent / 'installed/skill/scripts/query.py'
        copied.parent.mkdir(parents=True)
        shutil.copy2(SCRIPT, copied)
        result = subprocess.run([sys.executable, '-I', '-S', str(copied), '--repo', str(self.root),
                                 'search', '陈庄', '--kind', 'entity'],
                                cwd=self.root.parent, capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['result']['items'][0]['id'], '陈庄')
        self.assertEqual(payload['structured_juans'], [3])

    def test_cli_rejects_invalid_paging_and_emits_json_for_unknown_passages(self):
        prefix = [sys.executable, '-I', '-S', str(SCRIPT), '--repo', str(self.root)]
        for tail in [['search', '陈庄', '--limit', '0'], ['search', '陈庄', '--limit', '201'],
                     ['search', '陈庄', '--offset', '-1'], ['chapter', '3', '--start-line', '0']]:
            result = subprocess.run(prefix + tail, capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 2)
        result = subprocess.run(prefix + ['passage', '6-1-0'], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertIn('error', json.loads(result.stderr))


if __name__ == '__main__':
    unittest.main()

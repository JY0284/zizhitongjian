import test from 'node:test';
import assert from 'node:assert/strict';
import { unifiedNetworkGraphData, unifiedLocationsToList } from '../src/utils/unifiedDataProcessing.ts';

const role = id => ({ id, canonical_name: id, all_names: [id], total_mentions: 2, juans_appeared: [1, 3], related_entities: [] });
const kb = { roles: { A: role('A'), B: role('B') }, name_to_role_id: { A: 'A', B: 'B' }, relations: {
  ab: { from_entity: 'A', to_entity: 'B', source_juans: [1, 3], first_interaction_year: -400, last_interaction_year: -300,
    occurrences: [
      { juan_index: 1, year: -400, time: '前400年', action: '会盟', context: '第一次互动' },
      { juan_index: 3, year: -300, time: '前300年', action: '战争', context: '第二次互动' },
    ] }
} };

test('relationship spans do not invent interactions in the intervening years', () => {
  assert.equal(unifiedNetworkGraphData(kb, [1, 3], [-350, -350]).links.length, 0);
  assert.equal(unifiedNetworkGraphData(kb, [1, 1], [-300, -300]).links.length, 0);
  const graph = unifiedNetworkGraphData(kb, [3, 3], [-300, -300]);
  assert.equal(graph.links.length, 1);
  assert.equal(graph.links[0].weight, 1);
  assert.deepEqual(graph.links[0].contexts, ['第二次互动']);
  assert.deepEqual(graph.links[0].sourceJuans, [3]);
});

test('places mentioned in a dated source remain visible without a named event', () => {
  const location = { id: '晋阳', juans_appeared: [1], total_mentions: 1,
    occurrences: [{ juan_index: 1, year: -400 }] };
  const book = { locations: { 晋阳: location }, events: {} };
  assert.equal(unifiedLocationsToList(book, [1, 1], [-403, -369]).length, 1);
  assert.equal(unifiedLocationsToList(book, [1, 1], [-350, -300]).length, 0);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { roleNavigation, relatedEntities } from '../src/utils/roleNavigation.ts';

const kb = {
  roles: {
    chen: { id: 'chen', canonical_name: '陈庄', all_names: ['陈庄'], juans_appeared: [3] },
    sima: { id: 'sima', canonical_name: '司马错', all_names: ['司马错', '司马将军'], juans_appeared: [3, 4] },
  },
  name_to_role_id: { '司马将军': 'sima' },
  polities: { shu: { id: 'shu', canonical_name: '蜀国', all_names: ['蜀', '蜀国'] } },
};

test('cross-volume link resolves the person and removes the old year restriction', () => {
  assert.deepEqual(roleNavigation(kb, '陈庄', [1, 1], [-403, -369], new Set()),
    { id: 'chen', juanRange: [3, 3], yearRange: [null, null] });
  assert.deepEqual(roleNavigation(kb, '司马将军', [1, 1], [null, null], new Set()),
    { id: 'sima', juanRange: [3, 4], yearRange: [null, null] });
});

test('visible people keep filters; isolated people still open a detail; non-people do not navigate', () => {
  assert.deepEqual(roleNavigation(kb, '陈庄', [1, 5], [-400, -200], new Set(['chen'])),
    { id: 'chen', juanRange: [1, 5], yearRange: [-400, -200] });
  assert.equal(roleNavigation(kb, '陈庄', [3, 3], [null, null], new Set()).id, 'chen');
  assert.equal(roleNavigation(kb, '蜀国', [1, 1], [null, null], new Set()), null);
});

test('related people and polities are separated and aliases deduplicated', () => {
  assert.deepEqual(relatedEntities(kb, ['蜀', '陈庄', '蜀国', '司马将军', '司马错']), {
    people: ['陈庄', '司马错'], others: [{ name: '蜀国', kind: '国家' }],
  });
});

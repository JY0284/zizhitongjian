import test from 'node:test';
import assert from 'node:assert/strict';
import { juanYearRange, juansOverlappingYears } from '../src/utils/yearRanges.ts';

const index = { juan_start_year: { 1: -403, 2: -368, 3: -320 }, juan_end_year: { 1: -369, 2: -321, 3: -298 } };
test('one volume includes its final year, and a middle year selects its containing volume', () => {
  assert.deepEqual(juanYearRange(index, [1, 1]), [-403, -369]);
  assert.deepEqual(juansOverlappingYears(index, [-380, -380]), [1, 1]);
  assert.deepEqual(juansOverlappingYears(index, [-370, -350]), [1, 2]);
  assert.equal(juansOverlappingYears(index, [100, 101]), null);
});
test('legacy index does not mistake the last volume start for its end', () => {
  const legacy = { juan_start_year: { 1: -403, 2: -368 } };
  assert.deepEqual(juanYearRange(legacy, [1, 1]), [-403, -368]);
  assert.deepEqual(juanYearRange(legacy, [2, 2]), [-368, null]);
});

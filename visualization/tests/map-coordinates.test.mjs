import test from 'node:test';
import assert from 'node:assert/strict';
import { referenceCoordinates, hasMapPosition } from '../src/utils/mapCoordinates.ts';

test('only a single, finite, modern-name match can open a reference map', () => {
  const loc = { coordinates: null, geocoding: { status: 'needs_review', modern_reference: true,
    candidate_count: 1, candidate_coordinates: [110, 35], match_level: '区县' } };
  assert.deepEqual(referenceCoordinates(loc), [110, 35]);
  assert.equal(hasMapPosition(loc), true);
  for (const change of [{ candidate_count: 2 }, { match_level: '省' }, { modern_reference: false },
    { candidate_coordinates: [NaN, 35] }, { candidate_coordinates: [110, 95] }]) {
    assert.equal(hasMapPosition({ ...loc, geocoding: { ...loc.geocoding, ...change } }), false);
  }
  assert.equal(loc.coordinates, null); // Showing a reference never certifies an ancient site.
});

import type { UnifiedLocation } from '../types/unified';

export function referenceCoordinates(location: UnifiedLocation): [number, number] | null {
  const geo = location.geocoding;
  const coords = geo?.candidate_coordinates;
  return !location.coordinates && geo?.status === 'needs_review' && geo.modern_reference
    && geo.candidate_count === 1 && coords && geo.match_level !== '省' && geo.match_level !== '国家'
    && Number.isFinite(coords[0]) && Number.isFinite(coords[1])
    && Math.abs(coords[0]) <= 180 && Math.abs(coords[1]) <= 90 ? coords : null;
}

export function hasMapPosition(location: UnifiedLocation) {
  return Boolean(location.coordinates || referenceCoordinates(location));
}

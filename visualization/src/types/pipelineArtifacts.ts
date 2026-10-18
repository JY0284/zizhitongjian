// Pipeline artifact types (JSON files under `data/`)

export interface SegmentYearIndexEntry {
  juan_index: number;
  segment_index: number;
  segment_start_time_raw: string | null;
  year: number | null;
  parse_method: string | null;
  confidence: number;
}

export interface SegmentYearIndex {
  version: string;
  cutoff_year: number;
  generated_at: string;
  segments: Record<string, SegmentYearIndexEntry>; // key: `${juan_index}-${segment_index}`
}

export interface SegmentYearOverrideEntry {
  year: number | null;
  reason?: string;
}

export interface SegmentYearOverrides {
  version: string;
  notes?: string;
  overrides: Record<string, SegmentYearOverrideEntry | number | null>; // accepts historical formats
}

export interface JuanYearIndex {
  version: string;
  generated_at: string;
  juan_start_year: Record<string, number | null>; // key is juan_index serialized as string
  juan_end_year?: Record<string, number | null>;
}

export interface LocationGeocodingEntry {
  location_id: string;
  canonical_name: string;
  modern_name: string;
  query: string;
  coordinates: [number, number] | null; // WGS84 [lng, lat] when needs_review=false
  candidate_coordinates?: [number, number] | null;
  candidate_count?: number | null;
  confidence: number;
  source: string;
  evidence: string;
  info?: string;
  infocode?: string;
  needs_review: boolean;
  attempts?: number;
  updated_at: string;
}

export interface LocationGeocodingOverridesEntry {
  coordinates: [number, number];
  notes?: string;
}

export interface LocationGeocodingCache {
  version: string;
  provider: string;
  generated_at: string;
  locations: Record<string, LocationGeocodingEntry>;
  overrides: Record<string, LocationGeocodingOverridesEntry>;
}

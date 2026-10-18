// Unified Knowledge Base Types
// These types mirror the Python unified models for the resolved/merged entities

export interface EntityOccurrence {
  year?: number | null;
  juan_index: number;
  segment_index: number;
  chunk_index: number;
  sentence_indexes: number[];
  original_description: string;
  source_sentence: string;
}

export interface UnifiedRole {
  id: string;
  canonical_name: string;
  all_names: string[];
  description: string;
  original_descriptions: string[];
  powers: string[];
  primary_power: string | null;
  first_appearance_juan: number;
  last_appearance_juan: number;
  active_period: string | null;
  occurrences: EntityOccurrence[];
  total_mentions: number;
  juans_appeared: number[];
  related_entities: string[];
  created_at: string;
  updated_at: string;
}

export interface UnifiedLocation {
  id: string;
  canonical_name: string;
  all_names: string[];
  location_type: string;
  description: string;
  modern_name: string;
  coordinates: [number, number] | null;
  geocoding?: {
    status: string;
    modern_reference?: boolean;
    candidate_count?: number | null;
    candidate_coordinates?: [number, number] | null;
    matched_address?: string | null;
    match_level?: string | null;
    evidence?: string | null;
  };
  associated_entities: string[];
  associated_events: string[];
  occurrences: EntityOccurrence[];
  total_mentions: number;
  juans_appeared: number[];
  created_at: string;
  updated_at: string;
}

export interface UnifiedEvent {
  id: string;
  name: string;
  time: string | null;
  time_start: number | null;
  time_end: number | null;
  imputed_time_start: number | null;
  imputed_time_end: number | null;
  location: string | null;
  participants: string[];
  description: string;
  background: string;
  significance: string;
  source_juans: number[];
  source_segments: string[];
  action_count: number;
  created_at: string;
  updated_at: string;
}

export interface UnifiedRelation {
  occurrences?: Array<{ juan_index: number; segment_index: number; sentence_indexes: number[];
    year: number | null; time: string | null; action: string; context: string }>;
  id: string;
  from_entity: string;
  to_entity: string;
  action_types: string[];
  primary_action: string;
  interaction_count: number;
  first_interaction_time: string | null;
  last_interaction_time: string | null;
  first_interaction_year: number | null;
  last_interaction_year: number | null;
  contexts: string[];
  source_juans: number[];
  created_at: string;
  updated_at: string;
}

export interface UnifiedPolity {
  id: string;
  canonical_name: string;
  all_names: string[];
  description: string;
  original_descriptions: string[];
  occurrences: EntityOccurrence[];
  total_mentions: number;
  juans_appeared: number[];
  created_at: string;
  updated_at: string;
}

export interface UnifiedOrganization {
  id: string;
  canonical_name: string;
  all_names: string[];
  description: string;
  original_descriptions: string[];
  occurrences: EntityOccurrence[];
  total_mentions: number;
  juans_appeared: number[];
  created_at: string;
  updated_at: string;
}

export interface UnifiedSchool {
  id: string;
  canonical_name: string;
  all_names: string[];
  description: string;
  original_descriptions: string[];
  occurrences: EntityOccurrence[];
  total_mentions: number;
  juans_appeared: number[];
  created_at: string;
  updated_at: string;
}

export interface UnifiedKnowledgeBase {
  data_mode?: 'demo';
  data_source?: string;
  data_notice?: string;
  data_coverage?: Array<{ juan: number; processed: number; total: number; complete: boolean }>;
  extraction_models?: string[];
  source_passages?: Record<string, { original: string; translated: string; review_note?: string }>;
  roles: Record<string, UnifiedRole>;
  locations: Record<string, UnifiedLocation>;
  events: Record<string, UnifiedEvent>;
  relations: Record<string, UnifiedRelation>;

  // Non-human entities
  polities: Record<string, UnifiedPolity>;
  organizations: Record<string, UnifiedOrganization>;
  schools: Record<string, UnifiedSchool>;
  
  // Indexes
  name_to_role_id: Record<string, string>;
  name_to_location_id: Record<string, string>;
  name_to_polity_id: Record<string, string>;
  name_to_organization_id: Record<string, string>;
  name_to_school_id: Record<string, string>;
  power_to_roles: Record<string, string[]>;
  juan_to_roles: Record<number, string[]>;
  juan_to_events: Record<number, string[]>;

  juan_to_polities: Record<number, string[]>;
  juan_to_organizations: Record<number, string[]>;
  juan_to_schools: Record<number, string[]>;
  
  // Statistics
  total_roles: number;
  total_locations: number;
  total_events: number;
  total_relations: number;
  total_polities: number;
  total_organizations: number;
  total_schools: number;
  juans_processed: number[];
  last_updated: string;
}

// Adapted types for visualization (compatible with existing components)
export interface RoleNodeUnified {
  id: string;
  name: string;
  power: string | null;
  description: string;
  appearances: number;
  juans: number[];
  aliases: string[];
  relatedEntities: string[];
}

export interface RoleLinkUnified {
  source: string;
  target: string;
  action: string;
  weight: number;
  time: string | null;
  actionTypes: string[];
  contexts: string[];
  sourceJuans: number[];
}

export interface TimelineEventUnified {
  id: string;
  name: string;
  time: string | null;
  timeNumeric: number | null;
  location: string | null;
  participants: string[];
  description: string;
  juan_index: number;
  type: 'event';
  significance: string;
  background: string;
}

export interface PowerDistributionUnified {
  power: string;
  count: number;
  roles: string[];
}

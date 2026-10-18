"""
Unified Entity Models: Canonical representations that merge multiple occurrences.

These models aggregate information from multiple extractions across 294 卷,
providing a single source of truth for each entity, location, and event.
"""

from typing import List, Dict, Set, Optional
from pydantic import BaseModel, Field, computed_field
from datetime import datetime


class EntityOccurrence(BaseModel):
    """Record of where an entity was mentioned."""
    juan_index: int
    segment_index: int
    chunk_index: int
    sentence_indexes: List[int] = Field(default_factory=list)
    original_description: str = ""
    source_sentence: str = ""
    year: Optional[int] = None  # Year of the source segment, not a life-date claim.


class UnifiedRole(BaseModel):
    """
    Canonical entity that merges all occurrences of the same person/organization.
    
    This is the "resolved" version of Role, aggregating information from
    multiple extractions across the entire 资治通鉴.
    """
    
    # Unique identifier (canonical name)
    id: str = Field(description="Unique identifier, typically the most common name")
    
    # Names and aliases
    canonical_name: str = Field(description="The authoritative name for this entity")
    all_names: Set[str] = Field(
        default_factory=set,
        description="All names and aliases found across all occurrences"
    )
    
    # Merged description (best quality)
    description: str = Field(
        default="",
        description="Best description, selected from the most detailed occurrence"
    )
    
    # All original descriptions for reference
    original_descriptions: List[str] = Field(
        default_factory=list,
        description="All unique original descriptions from the book"
    )
    
    # Power/faction affiliations (may change over time)
    powers: List[str] = Field(
        default_factory=list,
        description="All power affiliations, in chronological order if known"
    )
    primary_power: Optional[str] = Field(
        default=None,
        description="Most common or significant power affiliation"
    )
    
    # Temporal information
    first_appearance_juan: int = Field(default=0)
    last_appearance_juan: int = Field(default=0)
    active_period: Optional[str] = Field(
        default=None,
        description="Time period when this entity was active, e.g., '前453年-前403年'"
    )
    
    # Occurrence tracking
    occurrences: List[EntityOccurrence] = Field(
        default_factory=list,
        description="All places where this entity was mentioned"
    )
    
    # Statistics
    total_mentions: int = Field(default=0)
    juans_appeared: Set[int] = Field(default_factory=set)
    
    # Relationships summary
    related_entities: Set[str] = Field(
        default_factory=set,
        description="Other entities this one has relationships with"
    )
    
    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    @computed_field
    @property
    def appearance_count(self) -> int:
        return len(self.occurrences)
    
    @computed_field
    @property
    def juan_span(self) -> int:
        """How many 卷s this entity spans."""
        return len(self.juans_appeared)
    


class UnifiedPolity(BaseModel):
    """Canonical non-human entity (state/dynasty/polity) merged across occurrences."""

    id: str
    canonical_name: str
    all_names: Set[str] = Field(default_factory=set)

    description: str = Field(default="")
    original_descriptions: List[str] = Field(default_factory=list)

    occurrences: List[EntityOccurrence] = Field(default_factory=list)
    total_mentions: int = Field(default=0)
    juans_appeared: Set[int] = Field(default_factory=set)

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())



class UnifiedSchool(BaseModel):
    """Canonical school/ideology entity (e.g. 儒家/法家) merged across occurrences."""

    id: str
    canonical_name: str
    all_names: Set[str] = Field(default_factory=set)

    description: str = Field(default="")
    original_descriptions: List[str] = Field(default_factory=list)

    occurrences: List[EntityOccurrence] = Field(default_factory=list)
    total_mentions: int = Field(default=0)
    juans_appeared: Set[int] = Field(default_factory=set)

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())



class UnifiedOrganization(BaseModel):
    """Canonical organization/official-title/group entity merged across occurrences."""

    id: str
    canonical_name: str
    all_names: Set[str] = Field(default_factory=set)

    description: str = Field(default="")
    original_descriptions: List[str] = Field(default_factory=list)

    occurrences: List[EntityOccurrence] = Field(default_factory=list)
    total_mentions: int = Field(default=0)
    juans_appeared: Set[int] = Field(default_factory=set)

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())



class UnifiedLocation(BaseModel):
    """
    Canonical location that merges all occurrences of the same place.
    """
    
    id: str
    canonical_name: str
    all_names: Set[str] = Field(default_factory=set)
    
    location_type: str = Field(default="", description="国家、城市、地区、山川等")
    description: str = ""
    modern_name: str = ""
    coordinates: Optional[tuple[float, float]] = None
    
    # Related entities that were associated with this location
    associated_entities: Set[str] = Field(default_factory=set)
    
    # Events that occurred at this location
    associated_events: List[str] = Field(default_factory=list)
    
    occurrences: List[EntityOccurrence] = Field(default_factory=list)
    total_mentions: int = Field(default=0)
    juans_appeared: Set[int] = Field(default_factory=set)
    
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    


class UnifiedEvent(BaseModel):
    """
    Canonical event that may span multiple segments/chunks.
    """
    
    id: str
    name: str
    
    time: Optional[str] = None
    time_start: Optional[int] = Field(default=None, description="Numeric year, negative for BC")
    time_end: Optional[int] = Field(default=None, description="Numeric year, negative for BC")

    # Derived from reading context / segment-year index when time_start is missing
    imputed_time_start: Optional[int] = Field(
        default=None,
        description="Imputed numeric year (earliest), derived from segment-year index"
    )
    imputed_time_end: Optional[int] = Field(
        default=None,
        description="Imputed numeric year (latest), derived from segment-year index"
    )
    
    location: Optional[str] = None
    
    # All participants across all mentions
    participants: Set[str] = Field(default_factory=set)
    
    description: str = ""
    background: str = ""
    significance: str = ""
    
    # Source tracking
    source_juans: Set[int] = Field(default_factory=set)
    source_segments: List[str] = Field(
        default_factory=list,
        description="List of 'juan-segment' keys"
    )
    
    # Related actions that compose this event
    action_count: int = Field(default=0)
    
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    


class RelationOccurrence(BaseModel):
    juan_index: int
    segment_index: int
    sentence_indexes: List[int] = Field(default_factory=list)
    year: Optional[int] = None
    time: Optional[str] = None
    action: str = ""
    context: str = ""


class UnifiedRelation(BaseModel):
    """
    Aggregated relationship between two entities.
    
    Combines all interactions between a pair of entities across the entire text.
    """
    
    id: str = Field(description="Format: 'from_entity->to_entity'")
    
    from_entity: str
    to_entity: str
    
    # All action types between these entities
    action_types: List[str] = Field(default_factory=list)
    primary_action: str = Field(default="", description="Most common action type")
    
    # Interaction count
    interaction_count: int = Field(default=0)
    
    # Time span of interactions
    first_interaction_time: Optional[str] = None
    last_interaction_time: Optional[str] = None

    # Numeric year span of interactions (year-based; negative for BCE)
    first_interaction_year: Optional[int] = Field(
        default=None,
        description="Earliest interaction year (numeric), negative for BCE"
    )
    last_interaction_year: Optional[int] = Field(
        default=None,
        description="Latest interaction year (numeric), negative for BCE"
    )
    
    # Contexts from each interaction
    contexts: List[str] = Field(default_factory=list)
    occurrences: List[RelationOccurrence] = Field(default_factory=list)
    
    # Source tracking
    source_juans: Set[int] = Field(default_factory=set)
    
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    


class UnifiedKnowledgeBase(BaseModel):
    """
    The complete unified knowledge base for 资治通鉴.
    
    This is the "gold standard" data structure that visualization
    and search should use.
    """
    
    # Entity registries
    roles: Dict[str, UnifiedRole] = Field(default_factory=dict)
    polities: Dict[str, UnifiedPolity] = Field(default_factory=dict)
    schools: Dict[str, UnifiedSchool] = Field(default_factory=dict)
    organizations: Dict[str, UnifiedOrganization] = Field(default_factory=dict)
    locations: Dict[str, UnifiedLocation] = Field(default_factory=dict)
    events: Dict[str, UnifiedEvent] = Field(default_factory=dict)
    relations: Dict[str, UnifiedRelation] = Field(default_factory=dict)
    
    # Name resolution index: maps any name/alias to canonical ID
    name_to_role_id: Dict[str, str] = Field(default_factory=dict)
    name_to_polity_id: Dict[str, str] = Field(default_factory=dict)
    name_to_school_id: Dict[str, str] = Field(default_factory=dict)
    name_to_organization_id: Dict[str, str] = Field(default_factory=dict)
    name_to_location_id: Dict[str, str] = Field(default_factory=dict)
    
    # Power/faction index
    power_to_roles: Dict[str, List[str]] = Field(default_factory=dict)
    
    # Temporal index (juan -> entities active in that juan)
    juan_to_roles: Dict[int, List[str]] = Field(default_factory=dict)
    juan_to_polities: Dict[int, List[str]] = Field(default_factory=dict)
    juan_to_schools: Dict[int, List[str]] = Field(default_factory=dict)
    juan_to_organizations: Dict[int, List[str]] = Field(default_factory=dict)
    juan_to_events: Dict[int, List[str]] = Field(default_factory=dict)
    
    # Statistics
    total_roles: int = Field(default=0)
    total_polities: int = Field(default=0)
    total_schools: int = Field(default=0)
    total_organizations: int = Field(default=0)
    total_locations: int = Field(default=0)
    total_events: int = Field(default=0)
    total_relations: int = Field(default=0)
    
    juans_processed: List[int] = Field(default_factory=list)
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())

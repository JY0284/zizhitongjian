"""
Entity Resolution: Merge duplicate entities across extractions.

This module provides the core logic for:
1. Detecting duplicate entities (by name, alias, context)
2. Merging entity information from multiple occurrences
3. Building a unified knowledge base from raw extractions
"""

import json
import copy
import re
from collections import Counter, defaultdict
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from datetime import datetime

from model.role import Role
from model.polity import Polity
from model.school import School
from model.organization import Organization
from model.location import Location
from model.event import Event
from model.action import Action
from model.unified import (
    UnifiedRole, UnifiedPolity, UnifiedSchool, UnifiedOrganization,
    UnifiedLocation, UnifiedEvent, UnifiedRelation,
    UnifiedKnowledgeBase, EntityOccurrence
)


class EntityResolver:
    """
    Resolves and merges duplicate entities across all extractions.
    
    Strategy:
    1. Build name->aliases mapping from all occurrences
    2. Use Union-Find to group entities that share names/aliases
    3. Merge grouped entities into canonical UnifiedRole/UnifiedLocation
    
    Safeguards against over-merging:
    - Block generic/ambiguous aliases (大王, 王, 臣, etc.)
    - Block ambiguous ruler titles (秦王, 楚王 - refer to multiple people over time)
    - Prevent person-country confusion (赵籍 ≠ 赵国)
    - Cap maximum group size to prevent runaway merging
    """
    
    # Generic terms that should NEVER be used as merge keys
    # These are contextual references, not true aliases
    BLOCKED_ALIASES: Set[str] = {
        # Generic titles/honorifics
        "大王", "王", "臣", "寡人", "君", "君主", "国君", "君王",
        "太子", "世子", "公子", "王子", "皇子",
        "皇帝", "天子", "陛下", "主公", "主上", "主君",
        "将军", "丞相", "相国", "太后", "皇后", "夫人",
        "先帝", "先王", "真人", "始皇", "始皇帝",
        # Family/relationship terms
        "弟弟", "兄弟", "父亲", "母亲", "儿子", "女儿",
        "叔父", "伯父", "舅舅", "侄子", "外甥",
        # Generic role descriptors
        "使者", "使臣", "谋士", "谋臣", "大臣", "臣子",
        "百姓", "老百姓", "人民", "民众", "众人",
        "敌人", "敌军", "我军", "军队", "士兵", "士卒",
        "宾客", "客", "士", "朕",
        # Pronouns and references
        "您", "他", "她", "我", "吾", "余", "予",
        "此人", "其人", "何人", "某人",
        # Other ambiguous terms
        "领导国家提倡礼义者", "治理国家的君主", "发表评论者", "评论者",
        # Ambiguous ruler titles (refer to different people at different times)
        "秦王", "楚王", "齐王", "赵王", "魏王", "韩王", "燕王",
        "周王", "晋王", "宋王", "鲁王",
        "秦君", "楚君", "齐君", "赵君", "魏君", "韩君", "燕君",
    }
    
    # Country/state names - these should not be aliases for persons
    # A person can BELONG to a country (power field), but is not THE country
    COUNTRY_NAMES: Set[str] = {
        # Major states
        "赵", "魏", "韩", "秦", "楚", "齐", "燕",
        "赵国", "魏国", "韩国", "秦国", "楚国", "齐国", "燕国",
        "周", "周朝", "周王朝", "东周", "西周",
        "晋", "晋国", "宋", "宋国", "鲁", "鲁国",
        "卫", "卫国", "郑", "郑国", "陈", "陈国",
        "蔡", "蔡国", "曹", "曹国", "许", "许国",
        "吴", "吴国", "越", "越国",
        # Collective references
        "三晋", "六国", "诸侯", "诸侯国",
        # Other political entities
        "匈奴", "义渠", "中山", "中山国",
    }

    # Common dynasty/state names not covered above (appears later than Warring States)
    POLITY_EXTRA_NAMES: Set[str] = {
        "汉", "唐", "宋", "元", "明", "清",
        "魏", "蜀", "吴", "晋", "隋",
    }

    # School/ideology names (philosophical schools)
    SCHOOL_NAMES: Set[str] = {
        "儒家", "法家", "道家", "墨家", "兵家", "名家", "阴阳家",
        "纵横家", "杂家", "农家", "小说家", "黄老之学", "儒学",
        "儒", "法", "道", "墨", "兵", "名", "阴阳", "纵横",
    }

    # Organization / official-title patterns
    ORGANIZATION_NAMES: Set[str] = {
        "丞相府", "太尉", "太尉府", "御史大夫", "廷尉", "少府",
        "诸侯", "三公", "九卿", "郎中令", "卫尉", "光禄勋",
        "三家",
    }
    
    # Maximum number of names allowed in a single merged group
    # If exceeded, the group is likely incorrectly merged
    MAX_GROUP_SIZE: int = 15
    
    def __init__(self):
        self.segment_year_index: Dict[str, int] = {}
        # Union-Find structure for entity grouping
        self.parent: Dict[str, str] = {}

        # Separate Union-Find for polities
        self.polity_parent: Dict[str, str] = {}
        self.polity_group_size: Dict[str, int] = defaultdict(lambda: 1)
        
        # Track group sizes to prevent runaway merging
        self.group_size: Dict[str, int] = defaultdict(lambda: 1)
        
        # Name -> all occurrences of entities with that name
        self.role_occurrences: Dict[str, List[Tuple[Role, EntityOccurrence]]] = defaultdict(list)
        self.polity_occurrences: Dict[str, List[Tuple[Polity, EntityOccurrence]]] = defaultdict(list)
        self.school_occurrences: Dict[str, List[Tuple[School, EntityOccurrence]]] = defaultdict(list)
        self.organization_occurrences: Dict[str, List[Tuple[Organization, EntityOccurrence]]] = defaultdict(list)
        self.location_occurrences: Dict[str, List[Tuple[Location, EntityOccurrence]]] = defaultdict(list)
        
        # Union-Find for schools and organizations
        self.school_parent: Dict[str, str] = {}
        self.school_group_size: Dict[str, int] = defaultdict(lambda: 1)
        self.organization_parent: Dict[str, str] = {}
        self.organization_group_size: Dict[str, int] = defaultdict(lambda: 1)
        
        # Event merging by name
        self.event_occurrences: Dict[str, List[Tuple[Event, int, int]]] = defaultdict(list)
        
        # Relation aggregation
        self.relation_pairs: Dict[str, List[Action]] = defaultdict(list)

    def set_segment_year_index(self, segment_year_index: Dict[str, int]) -> None:
        """Provide a mapping like {'juan-seg': year} for numeric-year derivation."""
        self.segment_year_index = dict(segment_year_index)
    
    def _find(self, x: str) -> str:
        """Union-Find: find root with path compression."""
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self._find(self.parent[x])
        return self.parent[x]

    def _polity_find(self, x: str) -> str:
        if x not in self.polity_parent:
            self.polity_parent[x] = x
        if self.polity_parent[x] != x:
            self.polity_parent[x] = self._polity_find(self.polity_parent[x])
        return self.polity_parent[x]

    def _polity_union(self, x: str, y: str) -> bool:
        px, py = self._polity_find(x), self._polity_find(y)
        if px != py:
            new_size = self.polity_group_size[px] + self.polity_group_size[py]
            if new_size > self.MAX_GROUP_SIZE:
                return False
            if len(px) <= len(py):
                self.polity_parent[py] = px
                self.polity_group_size[px] = new_size
            else:
                self.polity_parent[px] = py
                self.polity_group_size[py] = new_size
        return True

    def _school_find(self, x: str) -> str:
        if x not in self.school_parent:
            self.school_parent[x] = x
        if self.school_parent[x] != x:
            self.school_parent[x] = self._school_find(self.school_parent[x])
        return self.school_parent[x]

    def _school_union(self, x: str, y: str) -> bool:
        px, py = self._school_find(x), self._school_find(y)
        if px != py:
            new_size = self.school_group_size[px] + self.school_group_size[py]
            if new_size > self.MAX_GROUP_SIZE:
                return False
            if len(px) <= len(py):
                self.school_parent[py] = px
                self.school_group_size[px] = new_size
            else:
                self.school_parent[px] = py
                self.school_group_size[py] = new_size
        return True

    def _organization_find(self, x: str) -> str:
        if x not in self.organization_parent:
            self.organization_parent[x] = x
        if self.organization_parent[x] != x:
            self.organization_parent[x] = self._organization_find(self.organization_parent[x])
        return self.organization_parent[x]

    def _organization_union(self, x: str, y: str) -> bool:
        px, py = self._organization_find(x), self._organization_find(y)
        if px != py:
            new_size = self.organization_group_size[px] + self.organization_group_size[py]
            if new_size > self.MAX_GROUP_SIZE:
                return False
            if len(px) <= len(py):
                self.organization_parent[py] = px
                self.organization_group_size[px] = new_size
            else:
                self.organization_parent[px] = py
                self.organization_group_size[py] = new_size
        return True

    def _is_polity_name(self, name: str) -> bool:
        name_norm = name.strip()
        if not name_norm:
            return False

        if name_norm in self.COUNTRY_NAMES or name_norm in self.POLITY_EXTRA_NAMES:
            return True

        # Strong suffix signals
        if name_norm.endswith("国") and len(name_norm) <= 4:
            return True
        if name_norm.endswith("朝") and len(name_norm) <= 4:
            return True
        if name_norm.endswith("王朝") and len(name_norm) <= 6:
            return True

        return False

    def _is_school_name(self, name: str) -> bool:
        """Check if name represents a school/ideology (e.g. 儒家, 法家)."""
        name_norm = name.strip()
        if not name_norm:
            return False

        if name_norm in self.SCHOOL_NAMES:
            return True

        # Exclude numeric-clan patterns like "晋国三家" / "魏三家" / "三家" etc.
        if re.search(r"[一二三四五六七八九十百千两]家$", name_norm):
            return False

        # Suffix pattern: X家 where X is 1-2 chars (儒家/法家/阴阳家)
        if name_norm.endswith("家") and 2 <= len(name_norm) <= 4:
            return True

        # Suffix pattern: X学 (儒学/黄老之学)
        if name_norm.endswith("学") and len(name_norm) <= 6:
            return True

        return False

    def _is_organization_name(self, name: str) -> bool:
        """Check if name represents an organization/official-title/group."""
        name_norm = name.strip()
        if not name_norm:
            return False

        if name_norm in self.ORGANIZATION_NAMES:
            return True

        # Suffix patterns for organizations
        if name_norm.endswith("府") and len(name_norm) <= 5:
            return True
        if name_norm.endswith("军") and len(name_norm) <= 4:
            return True

        # Numeric-clan patterns like "晋国三家" / "三家"
        if re.search(r"[一二三四五六七八九十百千两]家$", name_norm):
            return True

        return False
    
    def _union(self, x: str, y: str) -> bool:
        """
        Union-Find: merge two sets.
        
        Returns True if merge was successful, False if blocked due to size limit.
        """
        px, py = self._find(x), self._find(y)
        if px != py:
            # Check if merging would exceed group size limit
            new_size = self.group_size[px] + self.group_size[py]
            if new_size > self.MAX_GROUP_SIZE:
                # Don't merge - would create too large a group
                return False
            
            # Prefer shorter/simpler name as root
            if len(px) <= len(py):
                self.parent[py] = px
                self.group_size[px] = new_size
            else:
                self.parent[px] = py
                self.group_size[py] = new_size
        return True
    
    def _is_valid_alias_for_person(self, name: str, alias: str) -> bool:
        """
        Check if an alias is valid for merging with a person entity.
        
        Filters out:
        - Generic/ambiguous terms (大王, 臣, etc.)
        - Country names when the entity appears to be a person
        """
        alias_norm = alias.strip()
        
        # Block generic terms
        if alias_norm in self.BLOCKED_ALIASES:
            return False
        
        # Block country names as person aliases
        # Exception: if the name itself contains the country (e.g., 赵王), allow it
        if alias_norm in self.COUNTRY_NAMES:
            # Check if name clearly indicates this IS a country/state entity
            name_is_country = name in self.COUNTRY_NAMES or name.endswith("国")
            if not name_is_country:
                return False
        
        # Block single-character aliases that are too ambiguous
        # Exception: actual single-character names are fine (e.g., 商鞅's 鞅)
        if len(alias_norm) == 1 and alias_norm in self.COUNTRY_NAMES:
            return False
        
        return True
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for comparison."""
        # Remove common suffixes/prefixes that don't affect identity
        name = name.strip()
        # Could add more normalization rules specific to Chinese historical names
        return name
    
    def add_role(self, role: Role, juan_index: int, segment_index: int, 
                 chunk_index: int, source_sentence: str = "") -> None:
        """Add a role occurrence for later resolution.
        
        Entity type routing priority:
        1. If role.entity_type is explicitly set (by LLM), use that
        2. Otherwise, apply heuristic classification based on name patterns
        """
        occurrence = EntityOccurrence(
            juan_index=juan_index,
            segment_index=segment_index,
            chunk_index=chunk_index,
            sentence_indexes=role.sentence_indexes_in_segment,
            original_description=role.original_description_in_book,
            source_sentence=source_sentence
        )
        
        name = self._normalize_name(role.name)

        # Check entity_type field first (LLM-provided classification)
        entity_type = getattr(role, 'entity_type', 'person')
        
        if entity_type == 'polity':
            polity = Polity(
                name=role.name,
                alias=list(role.alias),
                original_description_in_book=role.original_description_in_book,
                description=role.description,
                sentence_indexes_in_segment=role.sentence_indexes_in_segment,
                juan_index=role.juan_index,
                segment_index=role.segment_index,
            )
            self.add_polity(polity, juan_index, segment_index, chunk_index, source_sentence)
            return
        elif entity_type == 'school':
            school = School(
                name=role.name,
                alias=list(role.alias),
                original_description_in_book=role.original_description_in_book,
                description=role.description,
                sentence_indexes_in_segment=role.sentence_indexes_in_segment,
                juan_index=role.juan_index,
                segment_index=role.segment_index,
            )
            self.add_school(school, juan_index, segment_index, chunk_index, source_sentence)
            return
        elif entity_type == 'organization':
            organization = Organization(
                name=role.name,
                alias=list(role.alias),
                original_description_in_book=role.original_description_in_book,
                description=role.description,
                sentence_indexes_in_segment=role.sentence_indexes_in_segment,
                juan_index=role.juan_index,
                segment_index=role.segment_index,
            )
            self.add_organization(organization, juan_index, segment_index, chunk_index, source_sentence)
            return

        # Fallback heuristics for backward compatibility (when entity_type='person' or unset)
        # Reclassify polity-like extractions (e.g. 秦/秦国/汉/唐) into separate model
        if self._is_polity_name(name):
            polity = Polity(
                name=role.name,
                alias=list(role.alias),
                original_description_in_book=role.original_description_in_book,
                description=role.description,
                sentence_indexes_in_segment=role.sentence_indexes_in_segment,
                juan_index=role.juan_index,
                segment_index=role.segment_index,
            )
            self.add_polity(polity, juan_index, segment_index, chunk_index, source_sentence)
            return

        # Reclassify school-like extractions (e.g. 儒家/法家)
        if self._is_school_name(name):
            school = School(
                name=role.name,
                alias=list(role.alias),
                original_description_in_book=role.original_description_in_book,
                description=role.description,
                sentence_indexes_in_segment=role.sentence_indexes_in_segment,
                juan_index=role.juan_index,
                segment_index=role.segment_index,
            )
            self.add_school(school, juan_index, segment_index, chunk_index, source_sentence)
            return

        # Reclassify organization-like extractions (e.g. 丞相府)
        if self._is_organization_name(name):
            organization = Organization(
                name=role.name,
                alias=list(role.alias),
                original_description_in_book=role.original_description_in_book,
                description=role.description,
                sentence_indexes_in_segment=role.sentence_indexes_in_segment,
                juan_index=role.juan_index,
                segment_index=role.segment_index,
            )
            self.add_organization(organization, juan_index, segment_index, chunk_index, source_sentence)
            return
        
        # Skip if the primary name itself is a blocked/generic term
        # These entities should not participate in merging at all
        if name in self.BLOCKED_ALIASES:
            # Still record the occurrence but don't merge
            self.role_occurrences[name].append((role, occurrence))
            return
        
        self.role_occurrences[name].append((role, occurrence))
        
        # Union name with valid aliases only
        for alias in role.alias:
            alias_norm = self._normalize_name(alias)
            if alias_norm and self._is_valid_alias_for_person(name, alias_norm):
                self._union(name, alias_norm)

    def add_polity(self, polity: Polity, juan_index: int, segment_index: int,
                   chunk_index: int, source_sentence: str = "") -> None:
        occurrence = EntityOccurrence(
            juan_index=juan_index,
            segment_index=segment_index,
            chunk_index=chunk_index,
            sentence_indexes=polity.sentence_indexes_in_segment,
            original_description=polity.original_description_in_book,
            source_sentence=source_sentence,
        )

        name = self._normalize_name(polity.name)
        self.polity_occurrences[name].append((polity, occurrence))
        for alias in polity.alias:
            alias_norm = self._normalize_name(alias)
            if alias_norm:
                self._polity_union(name, alias_norm)

        # Also unify common "X国" -> "X" form
        if name.endswith("国") and len(name) <= 4:
            base = name[:-1]
            if base:
                self._polity_union(name, base)

    def add_school(self, school: School, juan_index: int, segment_index: int,
                   chunk_index: int, source_sentence: str = "") -> None:
        """Add a school/ideology occurrence for later resolution."""
        occurrence = EntityOccurrence(
            juan_index=juan_index,
            segment_index=segment_index,
            chunk_index=chunk_index,
            sentence_indexes=school.sentence_indexes_in_segment,
            original_description=school.original_description_in_book,
            source_sentence=source_sentence,
        )

        name = self._normalize_name(school.name)
        self.school_occurrences[name].append((school, occurrence))
        for alias in school.alias:
            alias_norm = self._normalize_name(alias)
            if alias_norm:
                self._school_union(name, alias_norm)

        # Unify "X家" -> "X" form (e.g. 儒家 -> 儒)
        if name.endswith("家") and len(name) <= 4:
            base = name[:-1]
            if base:
                self._school_union(name, base)

    def add_organization(self, organization: Organization, juan_index: int, segment_index: int,
                         chunk_index: int, source_sentence: str = "") -> None:
        """Add an organization/official-title occurrence for later resolution."""
        occurrence = EntityOccurrence(
            juan_index=juan_index,
            segment_index=segment_index,
            chunk_index=chunk_index,
            sentence_indexes=organization.sentence_indexes_in_segment,
            original_description=organization.original_description_in_book,
            source_sentence=source_sentence,
        )

        name = self._normalize_name(organization.name)
        self.organization_occurrences[name].append((organization, occurrence))
        for alias in organization.alias:
            alias_norm = self._normalize_name(alias)
            if alias_norm:
                self._organization_union(name, alias_norm)
    
    def add_location(self, location: Location, juan_index: int, 
                     segment_index: int, chunk_index: int) -> None:
        """Add a location occurrence for later resolution."""
        occurrence = EntityOccurrence(
            juan_index=juan_index,
            segment_index=segment_index,
            chunk_index=chunk_index,
            sentence_indexes=location.sentence_indexes_in_segment,
            original_description=location.description
        )
        
        name = self._normalize_name(location.name)
        self.location_occurrences[name].append((location, occurrence))
        
        for alias in location.alias:
            alias_norm = self._normalize_name(alias)
            # For locations, we still block generic terms but allow country names
            if alias_norm and alias_norm not in self.BLOCKED_ALIASES:
                self._union(name, alias_norm)
    
    def add_event(self, event: Event, juan_index: int, segment_index: int) -> None:
        """Add an event occurrence for later merging."""
        if event.name:
            self.event_occurrences[event.name].append((event, juan_index, segment_index))
    
    def add_relation(self, action: Action) -> None:
        """Add a relation for later aggregation."""
        if action.is_commentary:
            return
        
        for from_role in action.from_roles:
            for to_role in action.to_roles:
                key = f"{self._normalize_name(from_role)}->{self._normalize_name(to_role)}"
                self.relation_pairs[key].append(action)
    
    def _select_best_description(self, descriptions: List[str]) -> str:
        """Select the most informative description."""
        if not descriptions:
            return ""
        # Prefer longer, more detailed descriptions
        return max(descriptions, key=lambda d: len(d) if d else 0)
    
    def _select_primary_power(self, powers: List[str]) -> Optional[str]:
        """Select the most common power affiliation."""
        if not powers:
            return None
        # Count occurrences
        power_counts = defaultdict(int)
        for p in powers:
            if p:
                power_counts[p] += 1
        if not power_counts:
            return None
        return max(power_counts, key=power_counts.get)
    
    def resolve_roles(self) -> Dict[str, UnifiedRole]:
        """Resolve all roles into unified entities."""
        # Group names by their Union-Find root
        groups: Dict[str, Set[str]] = defaultdict(set)
        for name in self.role_occurrences:
            root = self._find(name)
            groups[root].add(name)
        
        unified_roles: Dict[str, UnifiedRole] = {}
        
        for canonical_name, name_group in groups.items():
            # Collect all occurrences for this entity group
            all_occurrences: List[EntityOccurrence] = []
            all_descriptions: List[str] = []
            all_original_descriptions: List[str] = []
            all_powers: List[str] = []
            all_names: Set[str] = set()
            juans_appeared: Set[int] = set()
            related_entities: Set[str] = set()
            
            for name in sorted(name_group):
                all_names.add(name)
                for role, occurrence in self.role_occurrences[name]:
                    all_occurrences.append(occurrence)
                    if role.description:
                        all_descriptions.append(role.description)
                    if role.original_description_in_book:
                        all_original_descriptions.append(role.original_description_in_book)
                    if role.power:
                        all_powers.append(role.power)
                    juans_appeared.add(occurrence.juan_index)
                    # Add aliases to all_names
                    for alias in role.alias:
                        all_names.add(alias)
            
            # Remove duplicates from original descriptions
            unique_original = list(dict.fromkeys(all_original_descriptions))
            
            # Create unified role
            unified = UnifiedRole(
                id=canonical_name,
                canonical_name=self._display_name(all_names, self.role_occurrences),
                all_names=all_names,
                description=self._select_best_description(all_descriptions),
                original_descriptions=unique_original[:10],  # Keep top 10
                powers=list(dict.fromkeys(all_powers)),  # Unique, preserve order
                primary_power=self._select_primary_power(all_powers),
                first_appearance_juan=min(juans_appeared) if juans_appeared else 0,
                last_appearance_juan=max(juans_appeared) if juans_appeared else 0,
                occurrences=all_occurrences,
                total_mentions=len(all_occurrences),
                juans_appeared=juans_appeared,
                related_entities=related_entities
            )
            
            unified_roles[canonical_name] = unified
        
        return unified_roles

    def _display_name(self, names, occurrences):
        """Choose an attested full name; union roots are only internal IDs."""
        counts = Counter({name: len(occurrences.get(name, [])) for name in names})
        usable = [name for name in counts if name not in self.BLOCKED_ALIASES]
        full_names = [name for name in usable if len(name) > 1 and '〔卷' not in name]
        return min(full_names or usable or list(counts), key=lambda name: (-counts[name], len(name), name))
    
    def resolve_locations(self) -> Dict[str, UnifiedLocation]:
        """Resolve all locations into unified entities."""
        groups: Dict[str, Set[str]] = defaultdict(set)
        for name in self.location_occurrences:
            root = self._find(name)
            groups[root].add(name)
        
        unified_locations: Dict[str, UnifiedLocation] = {}
        
        for canonical_name, name_group in groups.items():
            all_occurrences: List[EntityOccurrence] = []
            all_names: Set[str] = set()
            all_types: List[str] = []
            all_descriptions: List[str] = []
            all_modern_names: List[str] = []
            coordinates = None
            associated_entities: Set[str] = set()
            juans_appeared: Set[int] = set()
            
            for name in name_group:
                all_names.add(name)
                for location, occurrence in self.location_occurrences[name]:
                    all_occurrences.append(occurrence)
                    juans_appeared.add(occurrence.juan_index)
                    if location.type:
                        all_types.append(location.type)
                    if location.description:
                        all_descriptions.append(location.description)
                    if location.modern_name:
                        all_modern_names.append(location.modern_name)
                    if location.coordinates and not coordinates:
                        coordinates = location.coordinates
                    for entity in location.related_entities:
                        associated_entities.add(entity)
                    for alias in location.alias:
                        all_names.add(alias)
            
            # Select most common type
            type_counts = defaultdict(int)
            for t in all_types:
                type_counts[t] += 1
            location_type = max(type_counts, key=type_counts.get) if type_counts else ""
            
            unified = UnifiedLocation(
                id=canonical_name,
                canonical_name=canonical_name,
                all_names=all_names,
                location_type=location_type,
                description=self._select_best_description(all_descriptions),
                modern_name=all_modern_names[0] if all_modern_names else "",
                coordinates=coordinates,
                associated_entities=associated_entities,
                occurrences=all_occurrences,
                total_mentions=len(all_occurrences),
                juans_appeared=juans_appeared
            )
            
            unified_locations[canonical_name] = unified
        
        return unified_locations

    def resolve_polities(self) -> Dict[str, UnifiedPolity]:
        unified_polities: Dict[str, UnifiedPolity] = {}

        # Group occurrences by union-find root
        groups: Dict[str, List[Tuple[Polity, EntityOccurrence]]] = defaultdict(list)
        for name, occurrences in self.polity_occurrences.items():
            root = self._polity_find(name)
            groups[root].extend(occurrences)

        for root_name, occurrences in groups.items():
            all_names: Set[str] = set()
            descriptions: List[str] = []
            original_descriptions: List[str] = []
            juans: Set[int] = set()
            occs: List[EntityOccurrence] = []

            for polity, occ in occurrences:
                all_names.add(self._normalize_name(polity.name))
                for a in polity.alias:
                    if a:
                        all_names.add(self._normalize_name(a))
                if polity.description:
                    descriptions.append(polity.description)
                if polity.original_description_in_book:
                    original_descriptions.append(polity.original_description_in_book)
                juans.add(occ.juan_index)
                occs.append(occ)

            canonical = min(all_names, key=len) if all_names else root_name
            unified_polities[canonical] = UnifiedPolity(
                id=canonical,
                canonical_name=canonical,
                all_names=all_names,
                description=self._select_best_description(descriptions),
                original_descriptions=list(dict.fromkeys(original_descriptions)),
                occurrences=occs,
                total_mentions=len(occs),
                juans_appeared=juans,
            )

        return unified_polities

    def resolve_schools(self) -> Dict[str, UnifiedSchool]:
        """Resolve all schools/ideologies into unified entities."""
        unified_schools: Dict[str, UnifiedSchool] = {}

        # Group occurrences by union-find root
        groups: Dict[str, List[Tuple[School, EntityOccurrence]]] = defaultdict(list)
        for name, occurrences in self.school_occurrences.items():
            root = self._school_find(name)
            groups[root].extend(occurrences)

        for root_name, occurrences in groups.items():
            all_names: Set[str] = set()
            descriptions: List[str] = []
            original_descriptions: List[str] = []
            juans: Set[int] = set()
            occs: List[EntityOccurrence] = []

            for school, occ in occurrences:
                all_names.add(self._normalize_name(school.name))
                for a in school.alias:
                    if a:
                        all_names.add(self._normalize_name(a))
                if school.description:
                    descriptions.append(school.description)
                if school.original_description_in_book:
                    original_descriptions.append(school.original_description_in_book)
                juans.add(occ.juan_index)
                occs.append(occ)

            canonical = min(all_names, key=len) if all_names else root_name
            unified_schools[canonical] = UnifiedSchool(
                id=canonical,
                canonical_name=canonical,
                all_names=all_names,
                description=self._select_best_description(descriptions),
                original_descriptions=list(dict.fromkeys(original_descriptions)),
                occurrences=occs,
                total_mentions=len(occs),
                juans_appeared=juans,
            )

        return unified_schools

    def resolve_organizations(self) -> Dict[str, UnifiedOrganization]:
        """Resolve all organizations/official-titles into unified entities."""
        unified_organizations: Dict[str, UnifiedOrganization] = {}

        # Group occurrences by union-find root
        groups: Dict[str, List[Tuple[Organization, EntityOccurrence]]] = defaultdict(list)
        for name, occurrences in self.organization_occurrences.items():
            root = self._organization_find(name)
            groups[root].extend(occurrences)

        for root_name, occurrences in groups.items():
            all_names: Set[str] = set()
            descriptions: List[str] = []
            original_descriptions: List[str] = []
            juans: Set[int] = set()
            occs: List[EntityOccurrence] = []

            for organization, occ in occurrences:
                all_names.add(self._normalize_name(organization.name))
                for a in organization.alias:
                    if a:
                        all_names.add(self._normalize_name(a))
                if organization.description:
                    descriptions.append(organization.description)
                if organization.original_description_in_book:
                    original_descriptions.append(organization.original_description_in_book)
                juans.add(occ.juan_index)
                occs.append(occ)

            canonical = min(all_names, key=len) if all_names else root_name
            unified_organizations[canonical] = UnifiedOrganization(
                id=canonical,
                canonical_name=canonical,
                all_names=all_names,
                description=self._select_best_description(descriptions),
                original_descriptions=list(dict.fromkeys(original_descriptions)),
                occurrences=occs,
                total_mentions=len(occs),
                juans_appeared=juans,
            )

        return unified_organizations
    
    def resolve_events(self) -> Dict[str, UnifiedEvent]:
        """Merge mentions within the same dated segment, not across history."""
        unified_events: Dict[str, UnifiedEvent] = {}

        grouped = {}
        for name, mentions in self.event_occurrences.items():
            by_segment = defaultdict(list)
            for event, juan, segment in mentions:
                by_segment[(juan, segment)].append((event, juan, segment))
            for (juan, segment), items in sorted(by_segment.items()):
                event_id = name if len(by_segment) == 1 else f"{name}@{juan}-{segment}"
                grouped[event_id] = items
        
        for event_id, occurrences in grouped.items():
            event_name = occurrences[0][0].name
            all_participants: Set[str] = set()
            source_juans: Set[int] = set()
            source_segments: List[str] = []
            descriptions: List[str] = []
            backgrounds: List[str] = []
            significances: List[str] = []
            times: List[str] = []
            locations: List[str] = []
            
            for event, juan_idx, seg_idx in occurrences:
                all_participants.update(event.participants)
                source_juans.add(juan_idx)
                source_segments.append(f"{juan_idx}-{seg_idx}")
                if event.description:
                    descriptions.append(event.description)
                if event.background:
                    backgrounds.append(event.background)
                if event.significance:
                    significances.append(event.significance)
                if event.time:
                    times.append(event.time)
                if event.location:
                    locations.append(event.location)
            
            # Parse numeric time
            time_str = times[0] if times else None
            time_numeric = self._parse_year(time_str)

            # A chapter can quote older events. Its year dates the mention,
            # not necessarily the event; preserve uncertainty instead of guessing.
            
            unified = UnifiedEvent(
                id=event_id,
                name=event_name,
                time=time_str,
                time_start=time_numeric,
                time_end=time_numeric,
                imputed_time_start=None,
                imputed_time_end=None,
                location=locations[0] if locations else None,
                participants=all_participants,
                description=self._select_best_description(descriptions),
                background=self._select_best_description(backgrounds),
                significance=self._select_best_description(significances),
                source_juans=source_juans,
                source_segments=source_segments,
                action_count=len(occurrences)
            )
            
            unified_events[event_id] = unified
        
        return unified_events
    
    def resolve_relations(self) -> Dict[str, UnifiedRelation]:
        """Aggregate relations between entity pairs."""
        unified_relations: Dict[str, UnifiedRelation] = {}
        
        for pair_key, actions in self.relation_pairs.items():
            from_entity, to_entity = pair_key.split("->")
            
            action_types: List[str] = []
            contexts: List[str] = []
            source_juans: Set[int] = set()
            times: List[str] = []
            years: List[int] = []
            occurrences = []
            
            for action in actions:
                if action.action:
                    action_types.append(action.action)
                if action.context:
                    contexts.append(action.context)
                source_juans.add(action.juan_index)
                if action.time:
                    times.append(action.time)

                year = self._parse_year(action.time)
                # A relative date or undated relationship is not an exact year.
                # Source-year filtering must not turn "one year later" into now.
                if year is not None:
                    years.append(int(year))
                occurrences.append({"juan_index": action.juan_index, "segment_index": action.segment_index,
                                    "sentence_indexes": action.sentence_indexes_in_segment,
                                    "year": year, "time": action.time, "action": action.action,
                                    "context": action.context})
            
            # Find most common action type
            action_counts = defaultdict(int)
            for a in action_types:
                action_counts[a] += 1
            primary_action = max(action_counts, key=action_counts.get) if action_counts else ""
            
            unified = UnifiedRelation(
                id=pair_key,
                from_entity=from_entity,
                to_entity=to_entity,
                action_types=list(dict.fromkeys(action_types)),  # Unique, preserve order
                primary_action=primary_action,
                interaction_count=len(actions),
                first_interaction_time=times[0] if times else None,
                last_interaction_time=times[-1] if len(times) > 1 else None,
                first_interaction_year=min(years) if years else None,
                last_interaction_year=max(years) if years else None,
                contexts=contexts[:5],  # Keep top 5 contexts
                occurrences=occurrences,
                source_juans=source_juans
            )
            
            unified_relations[pair_key] = unified
        
        return unified_relations
    
    def _parse_year(self, time_str: Optional[str]) -> Optional[int]:
        """Parse Chinese year format to numeric value."""
        if not time_str:
            return None

        # BCE: "公元前403" or "前403" (including inside parentheses)
        bc_match = re.search(r'公元前\s*(\d+)', time_str)
        if bc_match:
            return -int(bc_match.group(1))

        bc_match = re.search(r'前\s*(\d+)', time_str)
        if bc_match:
            return -int(bc_match.group(1))

        # CE explicit: "公元655年"
        ad_match = re.search(r'公元\s*(\d+)', time_str)
        if ad_match:
            return int(ad_match.group(1))

        # Common dataset format: "（...、3）", "（...、116）" etc
        paren_match = re.search(r'[（(][^）)]*?[、，,]\s*(\d{1,4})\s*(?:年)?\s*[）)]', time_str)
        if paren_match:
            return int(paren_match.group(1))

        return None
    
    def build_knowledge_base(self) -> UnifiedKnowledgeBase:
        """Build the complete unified knowledge base."""
        roles = self.resolve_roles()
        polities = self.resolve_polities()
        schools = self.resolve_schools()
        organizations = self.resolve_organizations()
        locations = self.resolve_locations()
        events = self.resolve_events()
        relations = self.resolve_relations()

        for collection in [roles, polities, schools, organizations, locations]:
            for entity in collection.values():
                for occurrence in entity.occurrences:
                    if "year" in type(occurrence).model_fields:
                        occurrence.year = self.segment_year_index.get(f"{occurrence.juan_index}-{occurrence.segment_index}")
        
        # Build indexes
        name_to_role_id: Dict[str, str] = {}
        for role_id, role in roles.items():
            for name in role.all_names:
                name_to_role_id[name] = role_id
        
        name_to_location_id: Dict[str, str] = {}
        for loc_id, loc in locations.items():
            for name in loc.all_names:
                name_to_location_id[name] = loc_id

        name_to_polity_id: Dict[str, str] = {}
        for polity_id, polity in polities.items():
            for name in polity.all_names:
                name_to_polity_id[name] = polity_id

        name_to_school_id: Dict[str, str] = {}
        for school_id, school in schools.items():
            for name in school.all_names:
                name_to_school_id[name] = school_id

        name_to_organization_id: Dict[str, str] = {}
        for org_id, org in organizations.items():
            for name in org.all_names:
                name_to_organization_id[name] = org_id
        
        # Power index
        power_to_roles: Dict[str, List[str]] = defaultdict(list)
        for role_id, role in roles.items():
            if role.primary_power:
                power_to_roles[role.primary_power].append(role_id)
        
        # Juan index
        juan_to_roles: Dict[int, List[str]] = defaultdict(list)
        for role_id, role in roles.items():
            for juan in role.juans_appeared:
                juan_to_roles[juan].append(role_id)
        
        juan_to_events: Dict[int, List[str]] = defaultdict(list)
        for event_id, event in events.items():
            for juan in event.source_juans:
                juan_to_events[juan].append(event_id)

        juan_to_polities: Dict[int, List[str]] = defaultdict(list)
        for polity_id, polity in polities.items():
            for juan in polity.juans_appeared:
                juan_to_polities[juan].append(polity_id)

        juan_to_schools: Dict[int, List[str]] = defaultdict(list)
        for school_id, school in schools.items():
            for juan in school.juans_appeared:
                juan_to_schools[juan].append(school_id)

        juan_to_organizations: Dict[int, List[str]] = defaultdict(list)
        for org_id, org in organizations.items():
            for juan in org.juans_appeared:
                juan_to_organizations[juan].append(org_id)
        
        # Update related entities based on relations
        for rel in relations.values():
            from_id = name_to_role_id.get(rel.from_entity)
            to_id = name_to_role_id.get(rel.to_entity)
            if from_id and from_id in roles:
                roles[from_id].related_entities.add(rel.to_entity)
            if to_id and to_id in roles:
                roles[to_id].related_entities.add(rel.from_entity)
        
        # Collect all processed juans
        all_juans: Set[int] = set()
        for role in roles.values():
            all_juans.update(role.juans_appeared)
        
        return UnifiedKnowledgeBase(
            roles=roles,
            polities=polities,
            schools=schools,
            organizations=organizations,
            locations=locations,
            events=events,
            relations=relations,
            name_to_role_id=dict(name_to_role_id),
            name_to_polity_id=dict(name_to_polity_id),
            name_to_school_id=dict(name_to_school_id),
            name_to_organization_id=dict(name_to_organization_id),
            name_to_location_id=dict(name_to_location_id),
            power_to_roles=dict(power_to_roles),
            juan_to_roles=dict(juan_to_roles),
            juan_to_polities=dict(juan_to_polities),
            juan_to_schools=dict(juan_to_schools),
            juan_to_organizations=dict(juan_to_organizations),
            juan_to_events=dict(juan_to_events),
            total_roles=len(roles),
            total_polities=len(polities),
            total_schools=len(schools),
            total_organizations=len(organizations),
            total_locations=len(locations),
            total_events=len(events),
            total_relations=len(relations),
            juans_processed=sorted(all_juans)
        )


def scope_ambiguous_people(extraction):
    """Keep unresolved people and generic groups local to their source passage.

    Only changes the derived view; the extraction and source records stay intact.
    """
    titles = EntityResolver.BLOCKED_ALIASES | {"公主", "王太后", "卫侯", "卫君", "燕公", "蜀王",
        "楚太子", "秦太子", "侍从", "军吏", "算卦人", "张仪的手下人"}
    generic_groups = {"群臣", "国中贵族", "各国诸侯", "各国", "诸侯", "诸侯国",
                      "臣下", "众人", "百姓", "人民", "民众", "贵族"}
    result = copy.deepcopy(extraction)
    replacements = {}
    for entity in result.get("entities", []):
        is_person = entity.get("entity_type") in (None, "person")
        for name in [entity['name'], *entity.get('alias', [])]:
            ambiguous_person = is_person and (name in titles or name.endswith(('使者', '使臣'))
                or "未具名" in name or (len(name) == 1 and name not in EntityResolver.COUNTRY_NAMES))
            if ambiguous_person or (not is_person and name in generic_groups):
                replacements[name] = (f"{name}〔卷{result['juan_index']}·段{result['segment_index']}"
                                      f"·片段{result['chunk_start_index'] + 1}〕")
    for entity in result.get("entities", []):
        entity["name"] = replacements.get(entity["name"], entity["name"])
        entity["alias"] = [replacements.get(alias, alias) for alias in entity.get("alias", [])]
    for field, references in [("events", ["participants"]), ("locations", ["related_entities"]),
                              ("relations", ["from_roles", "to_roles"])]:
        for item in result.get(field, []):
            for reference in references:
                item[reference] = [replacements.get(name, name) for name in item.get(reference, [])]
    return result


def load_and_resolve(store_dir: str, segment_year_index_path: Optional[str] = None) -> UnifiedKnowledgeBase:
    """
    Load all juan data files and resolve into unified knowledge base.
    
    Args:
        store_dir: Path to directory containing juan_*.json files
        
    Returns:
        UnifiedKnowledgeBase with all entities resolved
    """
    store_path = Path(store_dir)
    resolver = EntityResolver()
    from zztj_pipeline.source_review import aligned_sources, apply_reviewed_identity, apply_reviewed_place_aliases
    original_sources = aligned_sources(store_path)

    if segment_year_index_path:
        try:
            with open(segment_year_index_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            seg_map: Dict[str, int] = {}
            for key, seg in payload.get('segments', {}).items():
                year = seg.get('year')
                if year is not None:
                    seg_map[key] = int(year)
            resolver.set_segment_year_index(seg_map)
            print(f"Loaded segment year index: {segment_year_index_path} (entries={len(seg_map)})")
        except FileNotFoundError:
            print(f"Segment year index not found: {segment_year_index_path} (skipping)")
    
    # Load all juan files
    for juan_file in sorted(store_path.glob("juan_*.json"), key=lambda path: int(path.stem.split('_')[1])):
        print(f"Processing {juan_file.name}...")
        
        with open(juan_file, 'r', encoding='utf-8') as f:
            juan_data = json.load(f)
        
        for chunk_key, extraction in sorted(juan_data.items(), key=lambda pair: (
            pair[1]['segment_index'], pair[1]['chunk_start_index'])):
            extraction = apply_reviewed_identity(extraction, original_sources.get(chunk_key, {}).get('original', ''))
            extraction = apply_reviewed_place_aliases(extraction)
            extraction = scope_ambiguous_people(extraction)
            juan_idx = extraction.get('juan_index', 0)
            seg_idx = extraction.get('segment_index', 0)
            chunk_idx = extraction.get('chunk_start_index', 0)
            source_sentences = extraction.get('source_sentences', [])
            source_text = ' '.join(source_sentences)
            
            # Add roles
            for entity in extraction.get('entities', []):
                role = Role(**entity)
                resolver.add_role(role, juan_idx, seg_idx, chunk_idx, source_text)
            
            # Add locations
            for loc in extraction.get('locations', []):
                location = Location(**loc)
                resolver.add_location(location, juan_idx, seg_idx, chunk_idx)
            
            # Add events
            for evt in extraction.get('events', []):
                event = Event(**evt)
                resolver.add_event(event, juan_idx, seg_idx)
            
            # Add relations
            for rel in extraction.get('relations', []):
                action = Action(**rel)
                resolver.add_relation(action)
    
    return resolver.build_knowledge_base()


def save_unified_knowledge_base(kb: UnifiedKnowledgeBase, output_path: str) -> None:
    """Save unified knowledge base to JSON file."""
    
    def serialize(obj):
        """Custom serializer for sets and other non-JSON types."""
        if isinstance(obj, set):
            return list(obj)
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(kb.model_dump(), f, ensure_ascii=False, indent=2, default=serialize)
    
    print(f"Saved unified knowledge base to {output_path}")
    print(f"  - {kb.total_roles} unique roles (persons)")
    print(f"  - {kb.total_polities} unique polities (states/dynasties)")
    print(f"  - {kb.total_schools} unique schools (ideologies)")
    print(f"  - {kb.total_organizations} unique organizations")
    print(f"  - {kb.total_locations} unique locations")
    print(f"  - {kb.total_events} unique events")
    print(f"  - {kb.total_relations} unique relations")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build unified knowledge base from extractions")
    parser.add_argument("--store-dir", default="data/store", help="Directory containing juan_*.json files")
    parser.add_argument("--output", default="data/unified_knowledge.json", help="Output file path")
    parser.add_argument(
        "--segment-year-index",
        default="data/segment_year_index.json",
        help="Optional segment-year index JSON for deriving numeric years",
    )
    
    args = parser.parse_args()
    
    seg_path = args.segment_year_index if args.segment_year_index else None
    kb = load_and_resolve(args.store_dir, segment_year_index_path=seg_path)
    save_unified_knowledge_base(kb, args.output)

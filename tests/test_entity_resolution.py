"""
Tests for entity resolution with entity type classification.

Tests cover:
1. Entity type routing from Role.entity_type field (LLM-provided)
2. Fallback heuristic classification (polity/school/organization patterns)
3. School and organization resolution and merging
4. Updated LLM prompt produces valid entity_type values
"""

import pytest
from model.role import Role
from model.polity import Polity
from model.school import School
from model.organization import Organization
from model.event import Event
from model.unified import EntityOccurrence
from entity_resolution import EntityResolver, scope_ambiguous_people


def test_display_name_prefers_attested_full_name_over_union_root():
    resolver = EntityResolver()
    resolver.add_role(Role(name="孔伋", alias=["孔", "子思"]), 1, 1, 0)
    resolver.add_role(Role(name="孔伋", alias=["子思"]), 1, 2, 0)
    roles = resolver.resolve_roles()
    assert len(roles) == 1
    role = next(iter(roles.values()))
    assert role.canonical_name == "孔伋"
    assert role.id == "孔"  # Preserve existing links and bookmarks.
    assert "子思" in role.all_names
    assert role.total_mentions == 2
    assert len(role.occurrences) == 2


def test_repeated_event_names_keep_their_dates_and_sources():
    resolver = EntityResolver()
    resolver.add_event(Event(name="日食", time="前397年", description="日食"), 1, 7)
    resolver.add_event(Event(name="日食", time="前375年", description="日食"), 1, 25)
    events = resolver.resolve_events()
    assert len(events) == 2
    assert {event.time_start for event in events.values()} == {-397, -375}
    assert events["日食@1-25"].source_segments == ["1-25"]


def test_unidentified_ruler_titles_do_not_merge_across_passages():
    source = {'juan_index': 3, 'segment_index': 2, 'chunk_start_index': 0,
              'entities': [{'name': '秦王', 'entity_type': 'person'}, {'name': '张仪', 'entity_type': 'person'}],
              'relations': [{'from_roles': ['秦王'], 'to_roles': ['张仪']}],
              'events': [{'participants': ['秦王']}], 'locations': [{'related_entities': ['秦王']}]}
    first = scope_ambiguous_people(source)
    second = scope_ambiguous_people({**source, 'segment_index': 8})
    title = first['entities'][0]['name']
    assert title != second['entities'][0]['name']
    assert first['relations'][0]['from_roles'] == first['events'][0]['participants'] == [title]
    assert first['locations'][0]['related_entities'] == [title]
    assert source['entities'][0]['name'] == '秦王'


def test_truncated_surnames_do_not_bridge_an_identified_person_and_an_unknown_person():
    resolver = EntityResolver()
    for juan, aliases in [(1, ['子思']), (2, [])]:
        data = scope_ambiguous_people({'juan_index': juan, 'segment_index': 1, 'chunk_start_index': 0,
            'entities': [{'name': '孔', 'alias': aliases, 'entity_type': 'person'}]})
        resolver.add_role(Role(**data['entities'][0]), juan, 1, 0)
    roles = list(resolver.resolve_roles().values())
    assert len(roles) == 2
    assert '子思' in {role.canonical_name for role in roles}
    assert any('卷2' in role.canonical_name for role in roles)


class TestEntityTypeClassification:
    """Test entity type classification from Role.entity_type field."""

    def test_entity_type_field_exists(self):
        """Role model should have entity_type field with default None (inferred as 'person')."""
        role = Role(name="张三")
        assert hasattr(role, 'entity_type')
        # Default is None, which is treated as 'person' by entity_resolution.py
        assert role.entity_type is None or role.entity_type == "person"

    def test_entity_type_person(self):
        """entity_type='person' should route to role occurrences."""
        resolver = EntityResolver()
        role = Role(
            name="商鞅",
            entity_type="person",
            description="秦国变法大臣",
            alias=["卫鞅", "公孙鞅"],
        )
        resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        assert len(resolver.role_occurrences) > 0
        assert "商鞅" in resolver.role_occurrences
        assert len(resolver.polity_occurrences) == 0
        assert len(resolver.school_occurrences) == 0
        assert len(resolver.organization_occurrences) == 0

    def test_entity_type_polity(self):
        """entity_type='polity' should route to polity occurrences."""
        resolver = EntityResolver()
        role = Role(
            name="秦",
            entity_type="polity",
            description="战国七雄之一",
            alias=["秦国"],
        )
        resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        assert len(resolver.polity_occurrences) > 0
        assert "秦" in resolver.polity_occurrences
        assert len(resolver.role_occurrences) == 0

    def test_entity_type_school(self):
        """entity_type='school' should route to school occurrences."""
        resolver = EntityResolver()
        role = Role(
            name="儒家",
            entity_type="school",
            description="以孔子思想为核心的学派",
            alias=["儒学"],
        )
        resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        assert len(resolver.school_occurrences) > 0
        assert "儒家" in resolver.school_occurrences
        assert len(resolver.role_occurrences) == 0
        assert len(resolver.polity_occurrences) == 0

    def test_entity_type_organization(self):
        """entity_type='organization' should route to organization occurrences."""
        resolver = EntityResolver()
        role = Role(
            name="丞相府",
            entity_type="organization",
            description="丞相办公机构",
        )
        resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        assert len(resolver.organization_occurrences) > 0
        assert "丞相府" in resolver.organization_occurrences
        assert len(resolver.role_occurrences) == 0


class TestFallbackHeuristics:
    """Test fallback heuristic classification when entity_type='person' or unset."""

    def test_polity_name_heuristic(self):
        """Names matching polity patterns should be reclassified."""
        resolver = EntityResolver()
        
        # Test various polity patterns
        polity_names = ["赵", "魏国", "汉", "周朝", "秦王朝"]
        for name in polity_names:
            role = Role(name=name, entity_type="person")  # Default/wrong type
            resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        # All should be reclassified to polities
        assert len(resolver.polity_occurrences) >= len(polity_names)
        for name in polity_names:
            assert name in resolver.polity_occurrences, f"{name} should be in polity_occurrences"

    def test_school_name_heuristic(self):
        """Names matching school patterns should be reclassified."""
        resolver = EntityResolver()
        
        # Test various school patterns
        school_names = ["儒家", "法家", "道家", "墨家", "兵家", "儒学"]
        for name in school_names:
            role = Role(name=name, entity_type="person")  # Default/wrong type
            resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        # All should be reclassified to schools
        assert len(resolver.school_occurrences) >= len(school_names)
        for name in school_names:
            assert name in resolver.school_occurrences, f"{name} should be in school_occurrences"

    def test_organization_name_heuristic(self):
        """Names matching organization patterns should be reclassified."""
        resolver = EntityResolver()
        
        # Test various organization patterns
        org_names = ["丞相府", "太尉府", "虎贲军"]
        for name in org_names:
            role = Role(name=name, entity_type="person")  # Default/wrong type
            resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        # All should be reclassified to organizations
        for name in org_names:
            assert name in resolver.organization_occurrences, f"{name} should be in organization_occurrences"

    def test_person_not_reclassified(self):
        """Person names should not be reclassified."""
        resolver = EntityResolver()
        
        person_names = ["商鞅", "孔子", "韩非子", "李斯"]
        for name in person_names:
            role = Role(name=name, entity_type="person")
            resolver.add_role(role, juan_index=1, segment_index=1, chunk_index=0)
        
        # All should remain as roles
        for name in person_names:
            assert name in resolver.role_occurrences, f"{name} should be in role_occurrences"
        assert len(resolver.polity_occurrences) == 0
        assert len(resolver.school_occurrences) == 0
        assert len(resolver.organization_occurrences) == 0


class TestSchoolResolution:
    """Test school entity resolution and merging."""

    def test_add_school_directly(self):
        """Schools added directly should be tracked correctly."""
        resolver = EntityResolver()
        school = School(
            name="法家",
            alias=["法"],
            description="以法治国的思想流派",
        )
        resolver.add_school(school, juan_index=1, segment_index=1, chunk_index=0)
        
        assert "法家" in resolver.school_occurrences
        assert len(resolver.school_occurrences["法家"]) == 1

    def test_school_alias_union(self):
        """Schools with aliases should be merged."""
        resolver = EntityResolver()
        
        school1 = School(name="儒家", alias=["儒"])
        school2 = School(name="儒", alias=[])
        
        resolver.add_school(school1, juan_index=1, segment_index=1, chunk_index=0)
        resolver.add_school(school2, juan_index=2, segment_index=1, chunk_index=0)
        
        schools = resolver.resolve_schools()
        # Should merge into one school
        assert len(schools) == 1
        unified = list(schools.values())[0]
        assert "儒家" in unified.all_names
        assert "儒" in unified.all_names

    def test_school_suffix_unification(self):
        """'X家' should be unified with 'X'."""
        resolver = EntityResolver()
        
        school = School(name="儒家", alias=[])
        resolver.add_school(school, juan_index=1, segment_index=1, chunk_index=0)
        
        # Check union-find relationship
        root1 = resolver._school_find("儒家")
        root2 = resolver._school_find("儒")
        assert root1 == root2, "儒家 and 儒 should have same root"


class TestOrganizationResolution:
    """Test organization entity resolution and merging."""

    def test_add_organization_directly(self):
        """Organizations added directly should be tracked correctly."""
        resolver = EntityResolver()
        org = Organization(
            name="丞相府",
            alias=["相府"],
            description="丞相的办公机构",
        )
        resolver.add_organization(org, juan_index=1, segment_index=1, chunk_index=0)
        
        assert "丞相府" in resolver.organization_occurrences
        assert len(resolver.organization_occurrences["丞相府"]) == 1

    def test_organization_alias_union(self):
        """Organizations with aliases should be merged."""
        resolver = EntityResolver()
        
        org1 = Organization(name="丞相府", alias=["相府"])
        org2 = Organization(name="相府", alias=[])
        
        resolver.add_organization(org1, juan_index=1, segment_index=1, chunk_index=0)
        resolver.add_organization(org2, juan_index=2, segment_index=1, chunk_index=0)
        
        orgs = resolver.resolve_organizations()
        # Should merge into one organization
        assert len(orgs) == 1
        unified = list(orgs.values())[0]
        assert "丞相府" in unified.all_names
        assert "相府" in unified.all_names


class TestBuildKnowledgeBase:
    """Test the complete knowledge base building with all entity types."""

    def test_build_includes_all_types(self):
        """build_knowledge_base should include all entity types."""
        resolver = EntityResolver()
        
        # Add one of each type
        resolver.add_role(
            Role(name="商鞅", entity_type="person"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="秦国", entity_type="polity"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="法家", entity_type="school"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="丞相府", entity_type="organization"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        
        kb = resolver.build_knowledge_base()
        
        assert kb.total_roles == 1
        assert kb.total_polities == 1
        assert kb.total_schools == 1
        assert kb.total_organizations == 1
        
        assert "商鞅" in kb.roles
        assert "秦" in kb.polities or "秦国" in kb.polities
        assert "法家" in kb.schools or "法" in kb.schools
        assert "丞相府" in kb.organizations

    def test_name_indexes_built(self):
        """Name to ID indexes should include all entity types."""
        resolver = EntityResolver()
        
        resolver.add_role(
            Role(name="商鞅", alias=["卫鞅"], entity_type="person"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="秦国", alias=["秦"], entity_type="polity"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="法家", alias=["法"], entity_type="school"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="丞相府", alias=["相府"], entity_type="organization"),
            juan_index=1, segment_index=1, chunk_index=0
        )
        
        kb = resolver.build_knowledge_base()
        
        # Check name indexes
        assert "商鞅" in kb.name_to_role_id
        assert "卫鞅" in kb.name_to_role_id
        
        # Either form should be in polity index
        assert "秦" in kb.name_to_polity_id or "秦国" in kb.name_to_polity_id
        
        # Either form should be in school index  
        assert "法家" in kb.name_to_school_id or "法" in kb.name_to_school_id
        
        # Either form should be in org index
        assert "丞相府" in kb.name_to_organization_id or "相府" in kb.name_to_organization_id

    def test_juan_indexes_built(self):
        """Juan indexes should include all entity types."""
        resolver = EntityResolver()
        
        resolver.add_role(
            Role(name="商鞅", entity_type="person"),
            juan_index=5, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="法家", entity_type="school"),
            juan_index=5, segment_index=1, chunk_index=0
        )
        resolver.add_role(
            Role(name="丞相府", entity_type="organization"),
            juan_index=5, segment_index=1, chunk_index=0
        )
        
        kb = resolver.build_knowledge_base()
        
        assert 5 in kb.juan_to_roles
        assert 5 in kb.juan_to_schools
        assert 5 in kb.juan_to_organizations


class TestClassificationMethods:
    """Test the individual classification methods."""

    def test_is_polity_name(self):
        """Test polity name detection."""
        resolver = EntityResolver()
        
        # Should be polities
        assert resolver._is_polity_name("秦") is True
        assert resolver._is_polity_name("秦国") is True
        assert resolver._is_polity_name("周朝") is True
        assert resolver._is_polity_name("汉王朝") is True
        assert resolver._is_polity_name("魏") is True
        assert resolver._is_polity_name("晋") is True
        
        # Should not be polities
        assert resolver._is_polity_name("商鞅") is False
        assert resolver._is_polity_name("孔子") is False
        assert resolver._is_polity_name("法家") is False
        assert resolver._is_polity_name("") is False

    def test_is_school_name(self):
        """Test school name detection."""
        resolver = EntityResolver()
        
        # Should be schools
        assert resolver._is_school_name("儒家") is True
        assert resolver._is_school_name("法家") is True
        assert resolver._is_school_name("道家") is True
        assert resolver._is_school_name("墨家") is True
        assert resolver._is_school_name("兵家") is True
        assert resolver._is_school_name("阴阳家") is True
        assert resolver._is_school_name("儒学") is True
        assert resolver._is_school_name("黄老之学") is True
        
        # Should not be schools
        assert resolver._is_school_name("三家") is False
        assert resolver._is_school_name("晋国三家") is False
        assert resolver._is_school_name("商鞅") is False
        assert resolver._is_school_name("秦国") is False
        assert resolver._is_school_name("") is False

    def test_is_organization_name(self):
        """Test organization name detection."""
        resolver = EntityResolver()
        
        # Should be organizations
        assert resolver._is_organization_name("丞相府") is True
        assert resolver._is_organization_name("太尉府") is True
        assert resolver._is_organization_name("虎贲军") is True
        assert resolver._is_organization_name("秦军") is True
        assert resolver._is_organization_name("三家") is True
        assert resolver._is_organization_name("晋国三家") is True
        
        # Should not be organizations
        assert resolver._is_organization_name("商鞅") is False
        assert resolver._is_organization_name("秦国") is False
        assert resolver._is_organization_name("儒家") is False
        assert resolver._is_organization_name("") is False


def test_event_mention_year_does_not_redate_a_retrospective_story():
    from model.event import Event
    resolver = EntityResolver()
    resolver.segment_year_index = {"4-25": -273}
    resolver.add_event(Event(name="艾陵之战", time="春秋末年", description="引用旧事"), 4, 25)
    resolver.add_event(Event(name="未定年旧事", description="引用旧事"), 4, 25)
    for event in resolver.resolve_events().values():
        assert event.time_start is None
        assert event.imputed_time_start is None


def test_relative_relation_date_does_not_use_mention_year():
    from model.action import Action
    resolver = EntityResolver()
    resolver.segment_year_index = {'3-11': -310}
    resolver.add_relation(Action(from_roles=['张仪'], to_roles=['魏国'], action='担任国相',
        context='任国相一年后', time='一年后', juan_index=3, segment_index=11))
    relation = next(iter(resolver.resolve_relations().values()))
    assert relation.first_interaction_year is None
    assert relation.occurrences[0].year is None


def test_generic_groups_and_unnamed_envoys_do_not_merge_between_passages():
    raw = {'juan_index': 3, 'segment_index': 8, 'chunk_start_index': 0,
           'entities': [{'name': '楚国使者', 'entity_type': 'person'},
                        {'name': '群臣', 'entity_type': 'organization'},
                        {'name': '秦国', 'entity_type': 'polity'},
                        {'name': '王太后', 'entity_type': 'person'}],
           'events': [{'participants': ['楚国使者', '群臣', '秦国']}]}
    first = scope_ambiguous_people(raw)
    second = scope_ambiguous_people({**raw, 'segment_index': 11})
    assert first['entities'][0]['name'] != second['entities'][0]['name']
    assert first['entities'][1]['name'] != second['entities'][1]['name']
    assert first['entities'][2]['name'] == second['entities'][2]['name'] == '秦国'
    assert first['entities'][3]['name'] != second['entities'][3]['name']
    assert first['events'][0]['participants'][1] == first['entities'][1]['name']
    assert raw['entities'][1]['name'] == '群臣'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

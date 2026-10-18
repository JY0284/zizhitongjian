from zztj_pipeline.source_review import apply_reviewed_identity


def test_reviewed_place_aliases_keep_geography_separate_from_polities():
    from zztj_pipeline.source_review import apply_reviewed_place_aliases
    raw = {'juan_index': 3, 'locations': [{'name': '蜀国', 'related_entities': ['蜀国']}],
           'entities': [{'name': '蜀国', 'entity_type': 'polity'}],
           'events': [{'location': '蜀国'}], 'relations': [{'location': '蜀地'}]}
    result = apply_reviewed_place_aliases(raw)
    assert result['locations'][0]['name'] == '蜀'
    assert result['locations'][0]['alias'] == ['蜀国']
    assert result['events'][0]['location'] == result['relations'][0]['location'] == '蜀'
    assert result['entities'] == raw['entities']
    assert result['locations'][0]['related_entities'] == ['蜀国']
    assert raw['locations'][0]['name'] == '蜀国'
    assert apply_reviewed_place_aliases({**raw, 'juan_index': 6})['locations'][0]['name'] == '蜀国'


def test_source_alignment_accepts_fullwidth_markers_but_rejects_different_text(tmp_path):
    import json
    from zztj_pipeline.source_review import aligned_sources
    source = tmp_path / 'source.json'
    source.write_text(json.dumps({'chapters': [{'index': 4, 'segments': [{'sentences': [
        {'original': '秦将伐赵', 'translated': '[１]秦国大将攻打赵国。'}]}]}]}), encoding='utf-8')
    store = tmp_path / 'store'
    store.mkdir()
    chunk = {'juan_index': 4, 'segment_index': 1, 'chunk_start_index': 0,
             'source_sentences': ['[１]秦国大将攻打赵国。']}
    path = store / 'juan_4.json'
    path.write_text(json.dumps({'4-1-0': chunk}), encoding='utf-8')
    assert aligned_sources(store, source)['4-1-0']['original'] == '秦将伐赵'
    chunk['source_sentences'] = ['不相同的译文']
    path.write_text(json.dumps({'4-1-0': chunk}), encoding='utf-8')
    assert aligned_sources(store, source) == {}


def test_reviewed_identity_requires_the_specific_source_passage_and_preserves_raw():
    raw = {'juan_index': 2, 'segment_index': 26, 'chunk_start_index': 2,
           'entities': [{'name': '孔', 'entity_type': 'person'}],
           'source_sentences': ['孟轲拜孔为师'],
           'events': [{'name': '孟轲拜孔为师', 'participants': ['孔']}],
           'relations': [{'from_roles': ['孟轲'], 'to_roles': ['孔'], 'event_name': '孟轲拜孔为师'}]}
    revised = apply_reviewed_identity(raw, '初，孟子师子思')
    assert revised['entities'][0]['name'] == '子思'
    assert revised['relations'][0]['to_roles'] == ['子思']
    assert revised['events'][0]['name'] == revised['relations'][0]['event_name'] == '孟轲拜子思为师'
    assert revised['source_sentences'] == raw['source_sentences']
    assert raw['entities'][0]['name'] == '孔'
    assert apply_reviewed_identity(raw, '没有确认身份的文言对照') == raw
    other = {**raw, 'segment_index': 27}
    assert apply_reviewed_identity(other, '初，孟子师子思') == other

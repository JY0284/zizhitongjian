import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_pages import install_snapshot, prepare_book_sources
from scripts.export_public_snapshot import check_public


def test_snapshot_rejects_tampering_and_unexpected_files_before_copy(tmp_path):
    source = tmp_path / 'snapshot'
    source.mkdir()
    files = {}
    for name in ['unified_knowledge.json', 'juan_year_index.json']:
        content = b'{"safe":true}'
        (source / name).write_bytes(content)
        files[name] = {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    (source / 'manifest.json').write_text(json.dumps({'files': files}), encoding='utf-8')
    install_snapshot(source, tmp_path / 'good')
    assert (tmp_path / 'good/unified_knowledge.json').read_bytes() == content
    (source / 'unified_knowledge.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hash mismatch'):
        install_snapshot(source, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()
    files['../.env'] = files['juan_year_index.json']
    (source / 'manifest.json').write_text(json.dumps({'files': files}), encoding='utf-8')
    with pytest.raises(ValueError, match='Unexpected'):
        install_snapshot(source, tmp_path / 'bad')


@pytest.mark.parametrize('payload', [
    {'nested': {'api_key': 'do-not-publish'}},
    {'url': 'http://192.168.1.8/data'},
    {'url': 'http://127.0.0.1:5173/'},
    {'path': 'C:\\Users\\example\\private.json'},
])
def test_public_data_rejects_credentials_and_local_connections(payload):
    with pytest.raises(ValueError):
        check_public(payload)


def test_book_staging_does_not_copy_private_or_development_files(tmp_path, monkeypatch):
    import scripts.build_pages as pages
    source = tmp_path / 'repo'
    source.mkdir()
    for name in ['book.toml', 'SUMMARY.md', 'README.md', 'appendix.md', '.env', 'budget.sqlite3']:
        (source / name).write_text('fixture', encoding='utf-8')
    for name in ['chapters', 'demo', 'docs', 'data', 'visualization']:
        (source / name).mkdir()
        (source / name / 'sample.txt').write_text(name, encoding='utf-8')
    monkeypatch.setattr(pages, 'ROOT', source)
    output = tmp_path / 'reader'
    prepare_book_sources(output)
    assert {p.name for p in output.iterdir()} == {
        'book.toml', 'SUMMARY.md', 'README.md', 'appendix.md', 'chapters', 'demo', 'docs'}
    assert not list(output.rglob('.env'))

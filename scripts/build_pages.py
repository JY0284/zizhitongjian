"""Assemble the reader and visualization from an explicit public file list."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.pages-build'


def install_snapshot(snapshot: Path, destination: Path):
    manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
    if set(manifest['files']) != {'unified_knowledge.json', 'juan_year_index.json'}:
        raise ValueError('Unexpected public snapshot files')
    # Check every hash before publishing any file.
    for name, entry in manifest['files'].items():
        content = (snapshot / name).read_bytes()
        if len(content) != entry['bytes'] or hashlib.sha256(content).hexdigest() != entry['sha256']:
            raise ValueError(f'Snapshot hash mismatch: {name}')
    destination.mkdir(parents=True, exist_ok=True)
    for name in [*manifest['files'], 'manifest.json']:
        shutil.copy2(snapshot / name, destination / name)


def prepare_book_sources(destination: Path):
    # The repository root contains .env, model logs, and development caches.
    # mdBook's source must contain only the reader's explicitly selected files.
    destination.mkdir(parents=True, exist_ok=True)
    for name in ['book.toml', 'SUMMARY.md', 'README.md', 'appendix.md']:
        shutil.copy2(ROOT / name, destination / name)
    for name in ['chapters', 'demo', 'docs']:
        shutil.copytree(ROOT / name, destination / name)


def build_site(mdbook: str):
    output = (BUILD / 'site').resolve()
    if output != (ROOT / '.pages-build/site').resolve() or not output.is_relative_to(ROOT.resolve()):
        raise ValueError('Unsafe build output path')
    if output.exists():
        shutil.rmtree(output)  # Checked absolute path, generated build output only.
    BUILD.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='reader-', dir=BUILD) as temporary:
        source = Path(temporary).resolve()
        if not source.is_relative_to(BUILD.resolve()):
            raise ValueError('Unsafe reader staging path')
        prepare_book_sources(source)
        subprocess.run([mdbook, 'build', str(source), '--dest-dir', str(output)], check=True)
    if len(list((output / 'chapters').glob('*.html'))) != 294:
        raise ValueError('Reader chapter output is incomplete')
    dist = ROOT / 'visualization/dist'
    if not (dist / 'index.html').exists():
        raise ValueError('Build the visualization first')
    # Do not publish unexpected files left in the local public/ directory.
    allowed = {'index.html', 'favicon.svg', 'vite.svg', 'assets', 'data'}
    if {path.name for path in dist.iterdir()} - allowed:
        raise ValueError('Unexpected frontend build files')
    explorer = output / 'explore'
    explorer.mkdir()
    for path in dist.iterdir():
        if path.name == 'data':
            continue  # Install only manifest-checked data, never the local cache.
        if path.is_dir():
            shutil.copytree(path, explorer / path.name)
        else:
            shutil.copy2(path, explorer / path.name)
    install_snapshot(ROOT / 'visualization/snapshot', output / 'explore/data')
    for path in (output / 'explore/data').iterdir():
        if path.name not in {'unified_knowledge.json', 'juan_year_index.json', 'manifest.json'}:
            raise ValueError('Unexpected frontend data file')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-snapshot', action='store_true')
    parser.add_argument('--mdbook', default='mdbook')
    args = parser.parse_args()
    if args.install_snapshot:
        install_snapshot(ROOT / 'visualization/snapshot', ROOT / 'visualization/public/data')
    else:
        print(build_site(args.mdbook))

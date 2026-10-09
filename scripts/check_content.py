"""Check local reading links and catalog consistency without network access."""

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def heading_slug(text):
    text = re.sub(r'[*_`]', '', text).strip().lower()
    text = re.sub(r'[^\w\-\s]', '', text, flags=re.UNICODE)
    return text.replace(' ', '-')


def check():
    errors = []
    documents = {p: p.read_text(encoding='utf-8') for p in ROOT.glob('*.md')}
    anchors = {}
    for path, text in documents.items():
        explicit = re.findall(r'<a id="([^"]+)"></a>', text)
        duplicates = [name for name, n in Counter(explicit).items() if n > 1]
        if duplicates:
            errors.append(f'{path.name}: duplicate anchors: {duplicates}')
        anchors[path] = set(explicit)
        for heading in re.findall(r'^#{1,6}\s+(.+)$', text, re.MULTILINE):
            slug = heading_slug(heading)
            candidate = slug
            suffix = 0
            while candidate in anchors[path]:
                suffix += 1
                candidate = f'{slug}-{suffix}'
            anchors[path].add(candidate)

    for path, text in documents.items():
        for target in re.findall(r'\[[^\]\n]*\]\(([^)\s]+)\)', text):
            link = urlsplit(target)
            if link.scheme or link.netloc:
                continue
            destination = (path.parent / unquote(link.path)).resolve() if link.path else path
            if not destination.is_file():
                errors.append(f'{path.name}: missing file: {target}')
            elif link.fragment and unquote(link.fragment) not in anchors.get(destination, set()):
                errors.append(f'{path.name}: missing anchor: {target}')

    data = json.loads((ROOT / 'data/episodes.json').read_text(encoding='utf-8'))
    episodes = data['episodes']
    numbers = [e['number'] for e in episodes]
    if numbers != list(range(1, len(episodes) + 1)):
        errors.append('Catalog numbers must be unique, ordered, and contiguous from 1')
    checked_on = date.fromisoformat(data['checked_on'])
    index = documents[ROOT / 'EPISODES.md']
    rows = {}
    for number, row in re.findall(r'^\| (\d+) \| (.+)$', index, re.MULTILINE):
        if int(number) in rows:
            errors.append(f'Index has duplicate row {number}')
        rows[int(number)] = row
    if sorted(rows) != numbers:
        errors.append('Index and JSON catalog have different episode numbers')

    translated_files = set()
    chapter_count = 0
    for episode in episodes:
        number = episode['number']
        row = rows.get(number, '')
        published = date.fromisoformat(episode['published'])
        if published > checked_on:
            errors.append(f'Episode {number}: published after the catalog check date')
        if not re.fullmatch(r'\d+:\d{2}', episode['duration']) or int(episode['duration'].split(':')[1]) >= 60:
            errors.append(f'Episode {number}: invalid duration')
        for value in (episode['title'].replace('|', '\\|'), episode['published'], episode['duration'], f'https://darknetdiaries.com/episode/{number}/'):
            if value not in row:
                errors.append(f'Episode {number}: index is missing catalog value {value!r}')
        filename = episode['translation']
        if filename is None:
            if '未翻訳' not in row or re.search(r'\]\(Episode-\d+\.md\)', row):
                errors.append(f'Episode {number}: untranslated row presents a translation link')
            continue
        translated_files.add(filename)
        path = ROOT / filename
        if path not in documents:
            errors.append(f'Episode {number}: missing translation {filename}')
            continue
        if f']({filename})' not in row:
            errors.append(f'Episode {number}: translation link missing from index')
        text = documents[path]
        chapters = re.findall(r'<a id="(chapter-\d+)"', text)
        expected = [f'chapter-{i:02d}' for i in range(1, len(chapters) + 1)]
        if not chapters or chapters != expected:
            errors.append(f'{filename}: chapter IDs must be consecutive from chapter-01')
        chapter_count += len(chapters)
        toc = re.findall(r'^- \[\d+\. [^\n]+\]\(#(chapter-\d+)\)$', text, re.MULTILINE)
        if toc != chapters:
            errors.append(f'{filename}: chapter table of contents does not match anchors')
        for value in (episode['title'], episode['published'], episode['duration']):
            if value not in text:
                errors.append(f'{filename}: missing metadata {value!r}')
        if text.count('[目次に戻る](#contents)') != len(chapters):
            errors.append(f'{filename}: each chapter needs a return link')

    if {p.name for p in ROOT.glob('Episode-*.md')} != translated_files:
        errors.append('Translation files and catalog translation entries differ')
    if list(ROOT.glob('Episode-*.txt')):
        errors.append('Legacy Episode-*.txt files remain after the Markdown migration')
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print(f'OK: {len(episodes)} catalog entries, {len(translated_files)} translations, {chapter_count} chapters; local links and metadata match.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(check())
    except (KeyError, ValueError, OSError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)

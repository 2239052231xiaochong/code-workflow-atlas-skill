#!/usr/bin/env python3
"""Capture selected code evidence and render an offline workflow atlas (stdlib only)."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import urlsplit

SKILL = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(items, kind):
    require(isinstance(items, list), f'{kind} must be an array')
    result = {}
    for item in items:
        require(isinstance(item, dict), f'{kind} entries must be objects')
        key = item.get('id')
        require(isinstance(key, str) and re.fullmatch(r'[a-zA-Z0-9_-]+', key), f'Invalid {kind} id: {key}')
        require(key not in result, f'Duplicate {kind} id: {key}')
        result[key] = item
    return result


def safe_path(raw):
    require(isinstance(raw, str) and raw, 'Source path must be nonempty and relative')
    require('\\' not in raw and ':' not in raw, f'Use a repository-relative POSIX path: {raw}')
    path = PurePosixPath(raw)
    require(not path.is_absolute() and '..' not in path.parts and '.git' not in path.parts,
            f'Source path escapes repository: {raw}')
    return str(path)


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=20)
    require(result.returncode == 0, 'Git could not read the requested revision or path')
    return result.stdout.decode('utf-8')


def capture_source(item, repo):
    item = copy.deepcopy(item)
    if 'text' in item:
        require('path' not in item and 'ref' not in item, 'Provided excerpts cannot claim a Git path/ref')
        require(isinstance(item['text'], str), 'Excerpt text must be a string')
        lines = item['text'].splitlines()
        start = item.get('start', 1)
        require(type(start) is int and start >= 1 and lines, 'Excerpt needs a valid start and text')
        end = start + len(lines) - 1
        item['provenance'] = 'provided-excerpt'
    else:
        relative = safe_path(item.get('path'))
        item['path'] = relative
        if item.get('ref'):
            ref = item['ref']
            require(isinstance(ref, str) and not ref.startswith('-') and re.fullmatch(r'[A-Za-z0-9_./~^\-]+', ref), 'Invalid Git reference')
            revision = git(repo, 'rev-parse', '--verify', ref + '^{commit}').strip()
            text = git(repo, 'show', revision + ':' + relative)
            item['revision'] = revision
            item['provenance'] = 'git-snapshot'
        else:
            target = (repo / relative).resolve()
            require(target.is_relative_to(repo.resolve()), 'Source symlink escapes repository')
            text = target.read_text(encoding='utf-8')
            item['provenance'] = 'working-copy'
        all_lines = text.splitlines()
        start, end = item.get('start', 1), item.get('end', len(all_lines))
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(all_lines),
                f'Invalid source range for {relative}: {start}-{end}')
        lines = all_lines[start - 1:end]
    require(len(lines) <= 2000, 'Narrow each source excerpt to at most 2000 lines')
    item['start'], item['end'] = start, end
    item['text'] = '\n'.join(lines)
    item['sha256'] = hashlib.sha256(item['text'].encode('utf-8')).hexdigest()
    if item.get('url'):
        url = urlsplit(item['url'])
        require(url.scheme in {'https', 'http'} and url.netloc and not url.username and not url.password,
                'Source URL must be HTTP(S) without credentials')
    annotations = item.get('annotations', [])
    require(isinstance(annotations, list), 'Annotations must be an array')
    for note in annotations:
        require(isinstance(note, dict) and type(note.get('line')) is int and start <= note['line'] <= end,
                f'Annotation outside source range: {item["id"]}')
        require(isinstance(note.get('text'), str) and note['text'].strip(), 'Annotation text required')
    return item


def render_prompt(prompt):
    result = copy.deepcopy(prompt)
    require(result.get('provenance') in {'repository-template', 'provided-template', 'illustrative'},
            f'Prompt provenance required: {result["id"]}')
    for key in ('system', 'user'):
        require(isinstance(result.get(key), str), f'Prompt {key} must be a string')
    require(isinstance(result.get('sourceIds', []), list), 'Prompt sourceIds must be an array')
    if result['provenance'] == 'repository-template':
        require(result.get('sourceIds'), 'Repository templates require source evidence')
    assembly = result.get('assembly')
    if assembly is None:
        return result
    require(isinstance(assembly, dict) and assembly.get('syntax') == 'mustache-basic', 'Unsupported assembly syntax')
    require(assembly.get('label'), 'Assembled examples need a provenance label')
    require(all(isinstance(assembly.get(key, ''), str) for key in ('systemAppend', 'userAppend')),
            'Prompt appendices must be strings')
    variables, snippets = result.get('parameters', {}), assembly.get('snippets', {})
    require(isinstance(variables, dict) and isinstance(snippets, dict), 'Parameters/snippets must be objects')

    def expand(template):
        def snippet(match):
            key = match[1]
            require(key in snippets and isinstance(snippets[key], str), f'Missing snippet: {key}')
            return snippets[key]
        template = re.sub(r'\{\{snippet:([\w-]+)\}\}', snippet, template)
        depth = 0
        for token in re.finditer(r'\{\{#if\s+\w+\}\}|\{\{/if\}\}', template):
            depth += -1 if token[0] == '{{/if}}' else 1
            require(0 <= depth <= 1, 'Nested/unbalanced conditionals are unsupported')
        require(depth == 0, 'Unbalanced conditional')
        template = re.sub(r'\{\{#if (\w+)\}\}([\s\S]*?)\{\{/if\}\}',
                          lambda m: m[2] if variables.get(m[1]) else '', template)

        def value(match):
            key = match[1]
            require(key in variables, f'Missing prompt parameter: {key}')
            val = variables[key]
            return json.dumps(val, ensure_ascii=False, indent=2) if isinstance(val, (dict, list, bool)) or val is None else str(val)
        template = re.sub(r'\{\{(\w+)\}\}', value, template)
        require(not re.search(r'\{\{[^}]*\}\}', template), 'Unresolved prompt placeholder')
        return template

    result['assembledSystem'] = expand(result['system']) + assembly.get('systemAppend', '')
    result['assembledUser'] = expand(result['user']) + assembly.get('userAppend', '')
    return result


def prepare(manifest, repo):
    require(isinstance(manifest, dict), 'Manifest must be an object')
    data = copy.deepcopy(manifest)
    require(data.get('version') == 1, 'Manifest version must be 1')
    require(isinstance(data.get('title'), str) and data['title'].strip(), 'Title required')
    require(isinstance(data.get('baseline'), str) and data['baseline'].strip(), 'Inspected baseline required')
    nodes, phases = unique(data.get('nodes', []), 'node'), unique(data.get('phases', []), 'phase')
    sources, prompts = unique(data.get('sources', []), 'source'), unique(data.get('prompts', []), 'prompt')
    require(nodes and phases, 'At least one node and phase required')
    located = set()
    for phase in phases.values():
        for lane in ('nodes', 'compare'):
            ids = phase.get(lane, [])
            require(isinstance(ids, list) and len(ids) <= 3, 'At most three nodes per phase/lane')
            if lane == 'compare' and ids:
                require(isinstance(data.get('comparison'), dict) and data['comparison'].get('baseline'), 'Comparison baseline required')
            for key in ids:
                require(key in nodes, f'Unknown phase node: {key}')
                require(key not in located, f'Node appears in multiple phases/lanes: {key}')
                located.add(key)
    require(located == set(nodes), 'Every node must be placed in a phase/lane')
    for node in nodes.values():
        require(isinstance(node.get('title'), str) and node['title'], 'Node title required')
        require(node.get('sourceIds') or node.get('evidenceStatus') == 'inferred', f'Node needs evidence or inferred label: {node["id"]}')
        for key in node.get('sourceIds', []):
            require(key in sources, f'Unknown source ID: {key}')
        for key in node.get('promptIds', []):
            require(key in prompts, f'Unknown prompt ID: {key}')
        for name in ('inputs', 'outputs', 'steps', 'sourceIds', 'promptIds'):
            require(isinstance(node.get(name, []), list), f'Node {name} must be an array')
    for edge in data.get('edges', []):
        require(isinstance(edge, dict) and edge.get('from') in nodes and edge.get('to') in nodes, 'Edge references unknown node')
    for prompt in prompts.values():
        for key in prompt.get('sourceIds', []):
            require(key in sources, f'Unknown prompt source ID: {key}')
    data['sources'] = [capture_source(source, repo) for source in sources.values()]
    data['prompts'] = [render_prompt(prompt) for prompt in prompts.values()]
    data['generator'] = {'name': 'code-workflow-atlas', 'version': '0.1.0'}
    return data


def render(data):
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    template = (SKILL / 'assets' / 'atlas.html').read_text(encoding='utf-8')
    require(template.count('__ATLAS_PAYLOAD__') == 1, 'Invalid atlas payload slot')
    return template.replace('__ATLAS_PAYLOAD__', payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        data = prepare(json.loads(args.manifest.read_text(encoding='utf-8-sig')),
                       (args.repo or args.manifest.parent).resolve())
        result = render(data)
        selected_sources = {(args.repo or args.manifest.parent).resolve() / item['path']
                            for item in data['sources'] if item.get('path')}
        require(args.output.resolve() != args.manifest.resolve()
                and args.output.resolve() not in {path.resolve() for path in selected_sources},
                'Output must not overwrite a manifest or selected source file')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding='utf-8')
        print(json.dumps({'output': str(args.output.resolve()), 'nodes': len(data['nodes']),
                          'sources': len(data['sources']), 'bytes': len(result.encode('utf-8'))}))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'Atlas build failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

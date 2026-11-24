import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'code-workflow-atlas'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load('builder', SKILL / 'scripts' / 'build_atlas.py')
packer = load('packer', SKILL / 'scripts' / 'package_skill.py')


def manifest():
    return {'version': 1, 'title': 'Fixture', 'baseline': 'Local synthetic source',
            'phases': [{'id': 'work', 'nodes': ['work']}],
            'nodes': [{'id': 'work', 'title': 'Work', 'sourceIds': ['source']}],
            'sources': [{'id': 'source', 'path': 'code.py', 'start': 1, 'end': 2,
                         'annotations': [{'line': 2, 'text': 'Returns data'}]}],
            'edges': [], 'prompts': []}


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / 'code.py').write_text('def work():\n    return 42\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_capture_exact_lines_and_hash(self):
        data = builder.prepare(manifest(), self.repo)
        source = data['sources'][0]
        self.assertEqual(source['text'], 'def work():\n    return 42')
        self.assertEqual(source['provenance'], 'working-copy')
        self.assertEqual(len(source['sha256']), 64)
        self.assertEqual(source['annotations'][0]['line'], 2)

    def test_invalid_graphs_rejected(self):
        for mutate in [
            lambda d: d['nodes'].append(copy.deepcopy(d['nodes'][0])),
            lambda d: d['phases'][0]['nodes'].append('missing'),
            lambda d: d['edges'].append({'from': 'work', 'to': 'missing'}),
            lambda d: d['nodes'][0].update(sourceIds=['missing']),
            lambda d: d['nodes'][0].update(promptIds=['missing']),
            lambda d: d['phases'].append({'id': 'duplicate-placement', 'nodes': ['work']}),
            lambda d: d['nodes'].append({'id': 'unplaced', 'title': 'Unplaced', 'sourceIds': ['source']}),
            lambda d: d.update(baseline=''),
        ]:
            data = manifest(); mutate(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                builder.prepare(data, self.repo)

    def test_evidence_required_but_inference_allowed(self):
        data = manifest(); data['nodes'][0]['sourceIds'] = []
        with self.assertRaises(ValueError): builder.prepare(data, self.repo)
        data['nodes'][0]['evidenceStatus'] = 'inferred'
        self.assertEqual(builder.prepare(data, self.repo)['nodes'][0]['evidenceStatus'], 'inferred')

    def test_source_bounds_and_annotation_bounds(self):
        for start, end in [(0, 2), (1, 50), (2, 1), (True, 2)]:
            data = manifest(); data['sources'][0].update(start=start, end=end)
            with self.subTest(start=start, end=end), self.assertRaises(ValueError): builder.prepare(data, self.repo)
        data = manifest(); data['sources'][0]['annotations'][0]['line'] = 99
        with self.assertRaises(ValueError): builder.prepare(data, self.repo)

    def test_traversal_and_executable_urls_rejected(self):
        for value in ['../secret.py', '/tmp/secret', 'C:/secret.py', '.git/config', 'dir\\file.py']:
            data = manifest(); data['sources'][0]['path'] = value
            with self.subTest(path=value), self.assertRaises(ValueError): builder.prepare(data, self.repo)
        for url in ['javascript:alert(1)', 'file:///tmp/source', 'https://user:secret@example.com/code']:
            data = manifest(); data['sources'][0]['url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError): builder.prepare(data, self.repo)

    def test_escaping_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / 'outside.py'; outside.write_text('outside', encoding='utf-8')
            try: (self.repo / 'link.py').symlink_to(outside)
            except OSError: self.skipTest('Symlink creation unavailable')
            data = manifest(); data['sources'][0]['path'] = 'link.py'
            with self.assertRaises(ValueError): builder.prepare(data, self.repo)

    def test_provided_excerpt_is_not_git_evidence(self):
        data = manifest(); data['sources'][0] = {'id': 'source', 'text': 'provided\ncode', 'start': 50}
        source = builder.prepare(data, self.repo)['sources'][0]
        self.assertEqual((source['start'], source['end'], source['provenance']), (50, 51, 'provided-excerpt'))

    def test_git_snapshot_survives_worktree_changes(self):
        def run(*args):
            return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
        run('init'); run('add', 'code.py')
        run('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Fixture')
        (self.repo / 'code.py').write_text('changed\nworktree\n', encoding='utf-8')
        data = manifest(); data['sources'][0]['ref'] = 'HEAD'
        source = builder.prepare(data, self.repo)['sources'][0]
        self.assertEqual(source['text'], 'def work():\n    return 42')
        self.assertEqual(source['provenance'], 'git-snapshot')
        self.assertEqual(len(source['revision']), 40)

    def test_prompt_assembly_matches_declared_order(self):
        prompt = {'id': 'p', 'provenance': 'illustrative', 'system': '{{snippet:s}}',
                  'user': '{{#if enabled}}Topic {{topic}}{{/if}}', 'parameters': {'enabled': True, 'topic': 'Arrays'},
                  'assembly': {'syntax': 'mustache-basic', 'label': 'Demo', 'snippets': {'s': 'Return JSON.'}, 'userAppend': '\nExtra'}}
        result = builder.render_prompt(prompt)
        self.assertEqual(result['assembledSystem'], 'Return JSON.')
        self.assertEqual(result['assembledUser'], 'Topic Arrays\nExtra')
        prompt['parameters']['enabled'] = False
        self.assertEqual(builder.render_prompt(prompt)['assembledUser'], '\nExtra')

    def test_prompt_failures_are_visible(self):
        for text in ['{{missing}}', '{{snippet:missing}}', '{{#if x}}a{{#if y}}b{{/if}}{{/if}}', '{{#if x}}x']:
            prompt = {'id': 'p', 'provenance': 'illustrative', 'system': text, 'user': '',
                      'assembly': {'syntax': 'mustache-basic', 'label': 'Demo'}}
            with self.subTest(text=text), self.assertRaises(ValueError): builder.render_prompt(prompt)

    def test_repository_template_requires_evidence(self):
        with self.assertRaises(ValueError):
            builder.render_prompt({'id': 'p', 'provenance': 'repository-template', 'system': 's', 'user': 'u'})

    def test_json_payload_cannot_close_script(self):
        data = builder.prepare(manifest(), self.repo)
        data['title'] = '</script><script>window.injected=true</script>'
        html = builder.render(data)
        self.assertNotIn(data['title'], html)
        self.assertIn('\\u003c/script\\u003e', html)

    def test_render_is_deterministic_and_offline(self):
        data = builder.prepare(manifest(), self.repo)
        html = builder.render(data)
        self.assertEqual(html, builder.render(data))
        self.assertNotIn('<script src=', html)
        self.assertNotIn('cdn.', html)

    def test_zip_is_reproducible_and_self_contained(self):
        one, two = self.repo / 'one.zip', self.repo / 'two.zip'
        self.assertEqual(packer.package(SKILL, one), packer.package(SKILL, two))
        with zipfile.ZipFile(one) as archive:
            self.assertIn('code-workflow-atlas/SKILL.md', archive.namelist())
            self.assertIn('code-workflow-atlas/assets/atlas.html', archive.namelist())
            self.assertFalse(any('__pycache__' in name for name in archive.namelist()))


if __name__ == '__main__': unittest.main()

"""Regressões da biblioteca, dos diagramas e do fluxo local de ilustração."""
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

STUDIO = Path(__file__).resolve().parents[1] / 'studio'
sys.path.insert(0, str(STUDIO))


class Version14Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        variables = patch.dict(os.environ, {
            'STUDIO_DATA': temp.name, 'STUDIO_VOICES': str(Path(temp.name) / 'voices'),
            'COMFY_IMAGE_URL': '', 'COMFY_IMAGE_CHECKPOINT': '', 'COMFY_IMAGE_MODEL_REVISION': '',
        })
        variables.start()
        self.addCleanup(variables.stop)
        spec = importlib.util.spec_from_file_location('studio_v14_test', STUDIO / 'app.py')
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)
        self.addCleanup(self.module.image_executor.shutdown)
        self.client = TestClient(self.module.app)
        self.addCleanup(self.client.close)
        sample = self.client.get('/api/sample').json()
        self.project = self.client.post('/api/projects', json=sample).json()
        self.pid = self.project['id']
        self.base = f'/api/projects/{self.pid}'
        buffer = io.BytesIO()
        Image.new('RGB', (512, 512), (40, 95, 120)).save(buffer, format='PNG')
        self.png = buffer.getvalue()

    def wait_job(self, status):
        for _ in range(60):
            job = self.client.get(self.base + '/image-job').json()
            if job['status'] == status:
                return job
            if job['status'] == 'error' and status != 'error':
                self.fail(job)
            time.sleep(.02)
        self.fail(job)

    def test_graph_validates_and_exports_editable_branching(self):
        self.assertNotIn('diagram', self.project['scenes'][0])
        graph = {
            'nodes': [{'id': 'olt', 'label': 'OLT', 'group': 'Operadora'},
                      {'id': 'ont1', 'label': 'Residência A'},
                      {'id': 'ont2', 'label': 'Residência B'}],
            'edges': [{'source': 'olt', 'target': 'ont1', 'label': 'ramal A'},
                      {'source': 'olt', 'target': 'ont2', 'label': 'ramal B'}],
        }
        self.project['scenes'][0]['diagram'] = graph
        saved = self.client.put(self.base, json=self.project)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['scenes'][0]['diagram'], graph)
        svg = self.client.get(self.base + '/slides/0/preview').text
        self.assertIn('ramal B', svg)
        self.assertIn('Operadora', svg)
        exported = self.client.post(self.base + '/slides/export')
        self.assertEqual(exported.status_code, 200, exported.text)
        with ZipFile(self.module.PROJECTS / self.pid / 'exports/slides.pptx') as pptx:
            slide = pptx.read('ppt/slides/slide1.xml').decode()
            self.assertIn('<a:t>Residência B</a:t>', slide)
            self.assertIn('prst="line"', slide)
        graph['edges'].append({'source': 'ont1', 'target': 'olt'})
        invalid = self.client.put(self.base, json=self.project)
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertEqual(len(self.client.get(self.base).json()['scenes'][0]['diagram']['edges']), 2)

    def test_legacy_asset_metadata_delete_guard_and_restore(self):
        library = self.module.PROJECTS / self.pid / 'assets'
        library.mkdir()
        name = 'a' * 24 + '.png'
        (library / name).write_bytes(self.png)
        self.assertEqual(self.client.get(self.base + '/assets').json()[0]['origin'], 'upload')
        route = self.base + '/assets/' + name
        patched = self.client.patch(route, json={'title': 'ONT', 'tags': [' GPON ', 'GPON'], 'license': 'CC BY'})
        self.assertEqual(patched.json()['tags'], ['GPON'])
        self.assertEqual(self.client.patch(route, json={'alt': 'Terminal óptico'}).json()['title'], 'ONT')
        self.project['scenes'][0]['image'] = name
        self.assertEqual(self.client.put(self.base, json=self.project).status_code, 200)
        self.assertEqual(self.client.delete(route).status_code, 409)
        copy = self.client.post(self.base + '/duplicate').json()['id']
        self.assertEqual(self.client.get(f'/api/projects/{copy}/assets').json()[0]['license'], 'CC BY')
        self.assertEqual(self.client.delete(self.base).status_code, 200)
        self.client.post(f'/api/trash/{self.pid}/restore').raise_for_status()
        self.assertEqual(self.client.get(self.base + '/assets').json()[0]['title'], 'ONT')
        self.project['scenes'][0]['image'] = ''
        self.client.put(self.base, json=self.project).raise_for_status()
        self.client.delete(route).raise_for_status()
        self.assertEqual(self.client.get(self.base + '/assets').json(), [])

    def test_image_provider_disabled_busy_and_approval(self):
        route = self.base + '/image-job'
        self.assertEqual(self.client.post(route, json={'prompt': 'Uma OLT'}).status_code, 503)
        prompt_id = 'b2c64577-f486-4065-8172-76db121aa283'
        provider_release = threading.Event()
        submissions = []

        def provider(url, path, payload=None, limit=1_000_000):
            if path == '/queue':
                return b'{"queue_running":[],"queue_pending":[]}'
            if path == '/prompt':
                submissions.append(payload['prompt'])
                return json.dumps({'prompt_id': prompt_id}).encode()
            if path == '/history/' + prompt_id:
                self.assertTrue(provider_release.wait(3))
                return json.dumps({prompt_id: {'outputs': {'7': {
                    'images': [{'filename': 'educativa.png', 'subfolder': 'studio-educativo', 'type': 'output'}],
                }}}}).encode()
            self.assertTrue(path.startswith('/view?'), path)
            return self.png

        config = {'COMFY_IMAGE_URL': 'http://comfyui:8188', 'COMFY_IMAGE_CHECKPOINT': 'sd15.safetensors',
                  'COMFY_IMAGE_MODEL_REVISION': 'test-revision'}
        with patch.dict(os.environ, config), \
             patch.object(self.module.image_generation, '_request', side_effect=provider):
            run = self.client.post(route, json={'prompt': 'Uma OLT'})
            try:
                self.assertEqual(run.status_code, 202, run.text)
                self.assertEqual(self.client.post(route, json={'prompt': 'Outra OLT'}).status_code, 409)
                self.assertEqual(self.client.delete(self.base).status_code, 409)
                self.assertEqual(self.client.get(self.base + '/assets').json(), [])
            finally:
                provider_release.set()
            job = self.wait_job('ready')
        self.assertEqual(submissions[0]['4']['inputs'], {'width': 512, 'height': 512, 'batch_size': 1})
        self.assertEqual(job['prompt_id'], prompt_id)
        draft = route + '/' + job['id']
        self.assertEqual(self.client.get(draft + '/preview').headers['content-type'], 'image/png')
        first = self.client.post(draft + '/approve')
        self.assertEqual(first.status_code, 200, first.text)
        asset = first.json()
        self.assertEqual(self.client.post(draft + '/approve').json(), asset)
        self.assertEqual(asset['origin'], 'ai')
        self.assertEqual(asset['model'], 'sd15.safetensors')
        self.assertEqual(asset['model_revision'], 'test-revision')
        self.project['scenes'][0].update(image=asset['id'], layout='two_column_explanation')
        self.client.put(self.base, json=self.project).raise_for_status()
        self.assertIn('image/png;base64', self.client.get(self.base + '/slides/0/preview').text)

    def test_discard_does_not_publish_late_provider_result(self):
        route = self.base + '/image-job'
        requested = threading.Event()
        release = threading.Event()

        def wait_image(*args):
            requested.set()
            release.wait(2)
            return self.png

        with patch.object(self.module.image_generation, 'settings', return_value=('http://comfyui:8188', 'sd15')), \
             patch.object(self.module.image_generation, 'submit', return_value=('provider-id', 123)), \
             patch.object(self.module.image_generation, 'wait_image', side_effect=wait_image):
            result = self.client.post(route, json={'prompt': 'Uma OLT'})
            self.assertEqual(result.status_code, 202, result.text)
            try:
                self.assertTrue(requested.wait(2))
                discard = self.client.delete(route + '/' + result.json()['id'])
                self.assertEqual(discard.json()['status'], 'cancelled')
            finally:
                release.set()
            self.assertTrue(self.module.image_slot.acquire(timeout=2))
            self.module.image_slot.release()
        self.assertEqual(self.client.get(route).json()['status'], 'cancelled')
        self.assertEqual(self.client.get(self.base + '/assets').json(), [])

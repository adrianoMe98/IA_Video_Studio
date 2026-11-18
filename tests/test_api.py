import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from cairosvg import svg2pdf
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'studio'))

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['STUDIO_DATA'] = cls.temp.name
        os.environ['STUDIO_VOICES'] = str(Path(cls.temp.name) / 'voices')
        cls.appmod = importlib.import_module('app')
        cls.client = TestClient(cls.appmod.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.temp.cleanup()

    def test_health_and_project_crud(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        sample = self.client.get('/api/sample').json()
        self.assertEqual(len(sample['scenes']), 3)
        created = self.client.post('/api/projects', json=sample)
        self.assertEqual(created.status_code, 201, created.text)
        pid = created.json()['id']
        self.assertEqual(self.client.get(f'/api/projects/{pid}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/projects/{pid}/job').json()['status'], 'none')
        sample['title'] = 'Aula revisada'
        updated = self.client.put(f'/api/projects/{pid}', json=sample)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['title'], 'Aula revisada')
        self.assertEqual(self.client.get(f'/api/projects/{pid}/files/../project.json').status_code, 404)

    def test_import_txt(self):
        result = self.client.post('/api/projects/import', files={'file':('aula.txt', b'Tema\nUma frase.\n\n---\n\nOutro\nOutra frase.')})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(len(result.json()['scenes']), 2)

    def test_import_pdf_extracts_scene_text(self):
        pdf = svg2pdf(bytestring=b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="80">'
                                 b'<text x="10" y="30">Introducao ao GPON</text></svg>')
        result = self.client.post('/api/projects/import', files={'file': ('redes.pdf', pdf, 'application/pdf')})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()['title'], 'redes')
        self.assertEqual(result.json()['scenes'][0]['narration'], 'Introducao ao GPON')

    def test_script_retries_short_block_and_uses_requested_duration(self):
        sample = self.client.get('/api/sample').json()
        project = self.client.post('/api/projects', json=sample).json()
        route = f"/api/projects/{project['id']}/suggest?duration_minutes=3"
        prompts = []

        def ollama(request, timeout):
            payload = json.loads(request.data)
            self.assertGreater(timeout, 0)
            prompts.append(payload['prompt'])
            count = 16 if len(prompts) == 1 else 65
            scenes = [
                {'title': f'Etapa {len(prompts)}-{i}', 'bullets': ['Conceito'],
                 'narration': f'Etapa {len(prompts)} {i}. ' + 'contexto ' * (count - 3)}
                for i in range(3)
            ]
            return io.BytesIO(json.dumps({'response': json.dumps({'scenes': scenes})}).encode())

        with patch('script_suggestion.urlopen', side_effect=ollama):
            response = self.client.post(route, json=project)
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()
        self.assertEqual(draft['target_seconds'], 180)
        self.assertEqual(draft['estimated_seconds'], 180)
        self.assertEqual(len(draft['scenes']), 6)
        self.assertFalse(draft['below_target'])
        self.assertEqual(len(prompts), 3)
        self.assertIn('48 palavras válidas', prompts[1])
        self.assertIn('bloco 2 de 2', prompts[2])
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}").json(), project)

    def test_script_reports_short_result_and_unavailable_model(self):
        sample = self.client.get('/api/sample').json()
        project = self.client.post('/api/projects', json=sample).json()
        route = f"/api/projects/{project['id']}/suggest"
        scene = {'title': 'GPON', 'narration': 'Uma rede óptica distribui o sinal.'}
        body = json.dumps({'response': json.dumps({'scenes': [scene, scene]})}).encode()
        with patch('script_suggestion.urlopen', side_effect=lambda *a, **kw: io.BytesIO(body)):
            result = self.client.post(route + '?duration_minutes=1', json=project)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(len(result.json()['scenes']), 1)
        self.assertEqual(result.json()['estimated_seconds'], 3)
        self.assertTrue(result.json()['below_target'])
        with patch('script_suggestion.urlopen', side_effect=URLError('offline')):
            self.assertEqual(self.client.post(route, json=project).status_code, 503)
        self.assertEqual(self.client.post(route + '?duration_minutes=9', json=project).status_code, 422)

    def test_invalid_voice(self):
        sample = self.client.get('/api/sample').json()
        sample['voice'] = 'desconhecida'
        response = self.client.post('/api/projects', json=sample)
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__': unittest.main()

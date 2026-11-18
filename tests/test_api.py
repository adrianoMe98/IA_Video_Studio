import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
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

    def test_invalid_voice(self):
        sample = self.client.get('/api/sample').json()
        sample['voice'] = 'desconhecida'
        response = self.client.post('/api/projects', json=sample)
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__': unittest.main()

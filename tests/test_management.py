"""Testes dos novos recursos de gerenciamento da v1.2, sem dependência do Docker."""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'studio'))


class ManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['STUDIO_DATA'] = cls.temp.name
        os.environ['STUDIO_VOICES'] = str(Path(cls.temp.name) / 'voices')
        # Testes usam mesmo módulo FastAPI que test_api; importação em processo único.
        spec = importlib.util.spec_from_file_location('studio_management_test', Path(__file__).resolve().parents[1] / 'studio' / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules['studio_management_test'] = cls.module
        spec.loader.exec_module(cls.module)
        cls.client = TestClient(cls.module.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.temp.cleanup()

    def create(self):
        sample = self.client.get('/api/sample').json()
        response = self.client.post('/api/projects', json=sample)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_search_rename_duplicate_and_trash_restore(self):
        first = self.create()
        pid = first['id']
        response = self.client.patch(f'/api/projects/{pid}/rename', json={'title': 'Aula de XGS-PON'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['title'], 'Aula de XGS-PON')
        self.assertIn(pid, [p['id'] for p in self.client.get('/api/projects?q=xgs-pon').json()])
        self.assertNotIn(pid, [p['id'] for p in self.client.get('/api/projects?q=inexistente').json()])

        duplicate = self.client.post(f'/api/projects/{pid}/duplicate')
        self.assertEqual(duplicate.status_code, 201, duplicate.text)
        copy_id = duplicate.json()['id']
        self.assertNotEqual(copy_id, pid)
        self.assertTrue(duplicate.json()['title'].endswith('(cópia)'))
        self.assertEqual(duplicate.json()['scenes'], first['scenes'])
        self.assertFalse((self.module.PROJECTS / copy_id / 'job.json').exists())
        self.assertFalse((self.module.PROJECTS / copy_id / 'exports').exists())

        exports = self.module.PROJECTS / pid / 'exports'
        exports.mkdir()
        (exports / 'video.mp4').write_bytes(b'video mantido')
        deletion = self.client.delete(f'/api/projects/{pid}')
        self.assertEqual(deletion.status_code, 200, deletion.text)
        self.assertEqual(self.client.get(f'/api/projects/{pid}').status_code, 404)
        trashed = self.client.get('/api/trash').json()
        self.assertIn(pid, [p['id'] for p in trashed])
        self.assertTrue((self.module.TRASH / pid / 'exports/video.mp4').exists())
        self.assertEqual(self.client.get('/api/trash?q=xgs-pon').json()[0]['id'], pid)
        restored = self.client.post(f'/api/trash/{pid}/restore')
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()['title'], 'Aula de XGS-PON')
        self.assertEqual((self.module.PROJECTS / pid / 'exports/video.mp4').read_bytes(), b'video mantido')
        self.assertFalse((self.module.PROJECTS / pid / 'trash.json').exists())

    def test_permanent_deletion_restricted_to_trash_and_confirmed(self):
        first = self.create()
        pid = first['id']
        self.assertEqual(self.client.request('DELETE', f'/api/trash/{pid}', json={'confirm':'EXCLUIR'}).status_code, 404)
        self.assertEqual(self.client.delete(f'/api/projects/{pid}').status_code, 200)
        self.assertEqual(self.client.request('DELETE', f'/api/trash/{pid}', json={'confirm':'SIM'}).status_code, 400)
        self.assertTrue((self.module.TRASH / pid / 'project.json').exists())
        self.assertEqual(self.client.request('DELETE', f'/api/trash/{pid}', json={'confirm':'EXCLUIR'}).status_code, 200)
        self.assertFalse((self.module.TRASH / pid).exists())
        self.assertEqual(self.client.post(f'/api/trash/{pid}/restore').status_code, 404)

    def test_cannot_trash_during_render_or_cross_paths(self):
        first = self.create()
        pid = first['id']
        with self.module.job_lock:
            self.module.running_projects.add(pid)
        try:
            resp = self.client.delete(f'/api/projects/{pid}')
            self.assertEqual(resp.status_code, 409, resp.text)
            self.assertTrue((self.module.PROJECTS / pid / 'project.json').is_file())
        finally:
            with self.module.job_lock:
                self.module.running_projects.discard(pid)
        self.assertEqual(self.client.delete('/api/projects/not-valid').status_code, 404)
        self.assertEqual(self.client.request('DELETE', '/api/trash/not-valid', json={'confirm': 'EXCLUIR'}).status_code, 404)
        self.assertEqual(self.client.patch(f'/api/projects/{pid}/rename', json={'title':'  '}).status_code, 400)


if __name__ == '__main__':
    unittest.main()

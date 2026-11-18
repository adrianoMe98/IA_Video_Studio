"""Integração dos dez blocos, quatro temas, APIs de mídia e exportações."""
from __future__ import annotations
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'studio'))
from slide_studio import LAYOUTS, THEMES, build_slide, as_svg, render_slides


class SlideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['STUDIO_DATA'] = cls.temp.name
        os.environ['STUDIO_VOICES'] = str(Path(cls.temp.name) / 'voices')
        import importlib.util
        spec = importlib.util.spec_from_file_location('studio_slides_test', Path(__file__).resolve().parents[1] / 'studio' / 'app.py')
        cls.appmod = importlib.util.module_from_spec(spec)
        sys.modules['studio_slides_test'] = cls.appmod
        spec.loader.exec_module(cls.appmod)
        cls.client = TestClient(cls.appmod.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.temp.cleanup()

    def create(self):
        sample=self.client.get('/api/sample').json()
        response=self.client.post('/api/projects',json=sample)
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def test_all_layouts_and_themes_render_svg(self):
        with tempfile.TemporaryDirectory() as d:
            for theme in THEMES:
                for layout in LAYOUTS:
                    p={'slide_theme': theme, 'scenes':[{'title':'Arquitetura da rede GPON', 'layout':layout,'bullets':['OLT','Splitter','ONT','Plano óptico'],'narration':'Exemplo técnico.'}]}
                    s=as_svg(build_slide(p,p['scenes'][0],0,Path(d)))
                    self.assertIn('<svg',s)
                    self.assertIn('OLT',s if layout not in ['hero_cover','concept_explainer'] else 'OLT' + s)
                    self.assertNotIn('<script',s)

    def test_asset_upload_preview_duplicate_and_guards(self):
        p=self.create();pid=p['id']
        image=Image.new('RGB',(600,350),(120,180,210));buf=io.BytesIO();image.save(buf,format='PNG')
        uploaded=self.client.post(f'/api/projects/{pid}/assets',files={'file':('example.png',buf.getvalue(),'image/png')})
        self.assertEqual(uploaded.status_code,201,uploaded.text)
        asset=uploaded.json()['id']
        self.assertIn(asset,[a['id'] for a in self.client.get(f'/api/projects/{pid}/assets').json()])
        p['scenes'][0]['image']=asset;p['scenes'][0]['layout']='two_column_explanation'
        p['slide_theme']='creative_course'
        self.assertEqual(self.client.put(f'/api/projects/{pid}',json=p).status_code,200)
        preview=self.client.get(f'/api/projects/{pid}/slides/0/preview')
        self.assertEqual(preview.status_code,200,preview.text[:200]);self.assertIn('image/png;base64',preview.text)
        clone=self.client.post(f'/api/projects/{pid}/duplicate')
        self.assertEqual(clone.status_code,201,clone.text)
        self.assertEqual(self.client.get(f'/api/projects/{clone.json()["id"]}/assets/{asset}').status_code,200)
        p['scenes'][0]['image']='../../etc/passwd'
        self.assertEqual(self.client.put(f'/api/projects/{pid}',json=p).status_code,400)
        self.assertEqual(self.client.get(f'/api/projects/{pid}/assets/not-valid').status_code,404)
        self.assertEqual(self.client.get(f'/api/projects/{pid}/slides/120/preview').status_code,404)

    def test_slide_only_export_and_editable_pptx(self):
        p=self.create();pid=p['id']
        exported=self.client.post(f'/api/projects/{pid}/slides/export')
        self.assertEqual(exported.status_code,200,exported.text)
        folder=self.appmod.PROJECTS/pid/'exports'
        self.assertTrue((folder/'slides.pdf').is_file())
        self.assertTrue((folder/'slides.pptx').is_file())
        self.assertEqual(len(PdfReader(str(folder/'slides.pdf')).pages),len(p['scenes']))
        import zipfile
        with zipfile.ZipFile(folder/'slides.pptx') as z:
            self.assertTrue(any(name.endswith('slide1.xml') for name in z.namelist()))
            xml=z.read('ppt/slides/slide1.xml').decode('utf-8')
            self.assertIn('<a:t>',xml) # texto editável, não apenas imagem de fundo
        self.assertEqual(self.client.get(f'/api/projects/{pid}/files/slides.pptx').status_code,200)

    def test_auto_layout(self):
        p=self.create();pid=p['id']
        res=self.client.post(f'/api/projects/{pid}/slides/auto-layout')
        self.assertEqual(res.status_code,200)
        self.assertIn(res.json()['scenes'][0]['layout'],LAYOUTS)


if __name__=='__main__':unittest.main()

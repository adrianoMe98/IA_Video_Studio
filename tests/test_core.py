import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'studio'))
from core import text_sentences, timestamp_srt, make_deck, draft_from_text, write_srt, concat_manifest

class CoreTests(unittest.TestCase):
    def test_sentences(self):
        self.assertEqual(text_sentences('Olá! Como vai? Tudo bem.'), ['Olá!', 'Como vai?', 'Tudo bem.'])

    def test_srt_time(self):
        self.assertEqual(timestamp_srt(3661.234), '01:01:01,234')
        self.assertEqual(timestamp_srt(0), '00:00:00,000')

    def test_srt_file(self):
        with tempfile.TemporaryDirectory() as p:
            path = Path(p) / 'sub.srt'
            write_srt([(0., 1.3, 'Olá.'), (1.3, 3.0, 'Fim.')], path)
            contents = path.read_text()
            self.assertIn('00:00:01,300 --> 00:00:03,000', contents)
            self.assertIn('Fim.', contents)

    def test_deck_escaping_and_slides(self):
        deck = make_deck({'scenes': [
            {'title': 'Rede <GPON>', 'bullets': ['Primeiro item'], 'narration': 'Nar.'},
            {'title': 'Segundo slide', 'bullets': ['Outro'], 'narration': 'Nar.'},
        ]})
        self.assertIn('&lt;GPON&gt;', deck)
        self.assertIn('marp: true', deck)
        self.assertEqual(deck.count('\n---\n'), 2)  # fim do YAML + separador entre cenas
        self.assertIn('Segundo slide', deck)

    def test_import_does_not_invent(self):
        slides = draft_from_text('# Título\nTexto inicial.\n\n---\n\n# Outro\nOutro texto.', 'Aula')
        self.assertEqual(len(slides), 2)
        self.assertIn('Texto inicial', slides[0]['narration'])

    def test_concat_manifest(self):
        with tempfile.TemporaryDirectory() as p:
            root = Path(p)
            a = root / 'one.wav'
            b = root / 'two.wav'
            concat_manifest([a,b], root / 'concat.txt')
            self.assertEqual((root/'concat.txt').read_text().count("file '"), 2)

if __name__ == '__main__': unittest.main()

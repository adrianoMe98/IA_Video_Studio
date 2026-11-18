"""Baixa modelos de voz PT-BR do repositório oficial rhasspy/piper-voices."""
import argparse
import os
from pathlib import Path
from urllib.request import urlopen

from core import VOICES

ROOT = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/'
FOLDERS = {'faber': 'faber/medium', 'edresson': 'edresson/low'}


def download(key: str, directory: Path) -> None:
    name = VOICES[key]
    directory.mkdir(parents=True, exist_ok=True)
    for suffix in ('.onnx', '.onnx.json'):
        target = directory / f'{name}{suffix}'
        if target.exists() and target.stat().st_size > 512:
            print(f'[OK] Já existe: {target.name}', flush=True)
            continue
        url = f'{ROOT}{FOLDERS[key]}/{name}{suffix}?download=true'
        temp = target.with_suffix(target.suffix + '.tmp')
        print(f'Baixando {target.name}...', flush=True)
        try:
            with urlopen(url, timeout=120) as response, temp.open('wb') as out:
                while data := response.read(1024 * 1024):
                    out.write(data)
            if temp.stat().st_size < 512:
                raise RuntimeError(f'Download incompleto: {target.name}')
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
        print(f'[OK] {target.name}: {target.stat().st_size // 1024} KiB', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('voice', nargs='?', choices=list(VOICES))
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    voices = list(VOICES) if args.all or not args.voice else [args.voice]
    directory = Path(os.environ.get('STUDIO_VOICES', '/data/voices'))
    for choice in voices:
        download(choice, directory)

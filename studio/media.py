"""Normalização e persistência de imagens do projeto."""
from __future__ import annotations

import io
import json
from pathlib import Path
import re

from PIL import Image, ImageOps

ASSET_NAME = re.compile(r'[0-9a-f]{24}\.png')
MAX_UPLOAD = 6 * 1024 * 1024
MAX_PNG = 8 * 1024 * 1024


def normalize_image(content: bytes, *, limit: int = MAX_UPLOAD) -> bytes:
    if len(content) > limit:
        raise OverflowError('Imagem maior que o limite de envio.')
    with Image.open(io.BytesIO(content)) as source:
        if (source.format not in ('PNG', 'JPEG', 'WEBP') or
                max(source.size) > 4000 or source.width * source.height > 12_000_000):
            raise ValueError('Envie PNG, JPG ou WebP válido, até 4000px.')
        result = io.BytesIO()
        ImageOps.exif_transpose(source).convert('RGB').save(result, format='PNG', optimize=True)
    if result.tell() > MAX_PNG:
        raise ValueError('Imagem PNG resultante muito grande.')
    return result.getvalue()


def asset_path(project: Path, name: str) -> Path | None:
    directory = project / 'assets'
    if not isinstance(name, str) or not ASSET_NAME.fullmatch(name) or directory.is_symlink():
        return None
    path = directory / name
    return path if path.is_file() and not path.is_symlink() else None


def asset_info(path: Path) -> dict:
    sidecar = path.with_suffix('.json')
    data = {}
    if sidecar.is_file() and not sidecar.is_symlink():
        try:
            parsed = json.loads(sidecar.read_text(encoding='utf-8'))
            if isinstance(parsed, dict):
                data = parsed
        except (OSError, ValueError):
            pass
    return {'origin': 'upload', **data, 'id': path.name, 'bytes': path.stat().st_size}


def add_asset(project: Path, name: str, content: bytes, metadata: dict, save_json) -> dict:
    directory = project / 'assets'
    if directory.is_symlink():
        raise ValueError('Biblioteca inválida.')
    directory.mkdir(exist_ok=True)
    if asset_path(project, name):
        return asset_info(directory / name)
    if sum(asset_path(project, item.name) is not None for item in directory.glob('*.png')) >= 40:
        raise ValueError('Limite de 40 imagens por projeto.')
    path = directory / name
    sidecar = path.with_suffix('.json')
    draft = path.with_suffix('.tmp')
    try:
        draft.write_bytes(content)
        save_json(sidecar, metadata)
        draft.replace(path)
    except OSError:
        sidecar.unlink(missing_ok=True)
        raise
    finally:
        draft.unlink(missing_ok=True)
    return asset_info(path)

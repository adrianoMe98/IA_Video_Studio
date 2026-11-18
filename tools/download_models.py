#!/usr/bin/env python3
"""Baixa somente os três arquivos necessários para Wan 2.1 T2V 1.3B GGUF.

Apenas arquivos públicos. O conteúdo grande fica fora da imagem Docker.
"""
import argparse
from pathlib import Path
from huggingface_hub import hf_hub_download

BASE = Path('/app/ComfyUI/models')
FILES = {
    'wan-q4': ('samuelchristlie/Wan2.1-T2V-1.3B-GGUF', 'Wan2.1-T2V-1.3B-Q4_K_S.gguf', 'diffusion_models'),
    'text-q3': ('city96/umt5-xxl-encoder-gguf', 'umt5-xxl-encoder-Q3_K_S.gguf', 'text_encoders'),
    'text-q4': ('city96/umt5-xxl-encoder-gguf', 'umt5-xxl-encoder-Q4_K_S.gguf', 'text_encoders'),
    'vae': ('Comfy-Org/Wan-2.1', 'split_files/vae/wan_2.1_vae.safetensors', 'vae'),
}

def main():
    parser = argparse.ArgumentParser(description='Download dos modelos Wan 2.1 GGUF')
    parser.add_argument('--profile', choices=['gtx1650', 'text-q4'], default='gtx1650')
    parser.add_argument('--only', choices=list(FILES), help='Baixar apenas um item')
    parser.add_argument('--list', action='store_true', help='Listar arquivos e sair')
    parser.add_argument('--verify', action='store_true', help='Checar arquivos locais sem baixar')
    args = parser.parse_args()
    keys = [args.only] if args.only else ['wan-q4', 'text-q3' if args.profile == 'gtx1650' else 'text-q4', 'vae']
    if args.list:
        for key, (repo, file, subdir) in FILES.items():
            print(f'{key:8} {repo}/{file} -> models/{subdir}/{Path(file).name}')
        return
    for key in keys:
        repo, repo_path, subdir = FILES[key]
        dest = BASE/subdir
        dest.mkdir(parents=True, exist_ok=True)
        target = dest/Path(repo_path).name
        if args.verify:
            status = 'OK' if target.is_file() and target.stat().st_size > 1_000_000 else 'AUSENTE/INCOMPLETO'
            print(f'{status}: {target}')
            if status != 'OK':
                raise SystemExit(2)
            continue
        if target.is_file() and target.stat().st_size > 1_000_000:
            print(f'[OK] Arquivo já presente: {target}')
            continue
        print(f'\n[download] {key}: {repo}/{repo_path}\n[destino]  {target}', flush=True)
        # O parâmetro local_dir cria um subdiretório quando repo_path tem subpastas.
        local_file = hf_hub_download(repo_id=repo, filename=repo_path, local_dir=dest)
        local_file = Path(local_file)
        if local_file != target:
            if target.exists():
                target.unlink()
            local_file.replace(target)
        print(f'[OK] {target.name}: {target.stat().st_size / 1e9:.2f} GB', flush=True)

if __name__ == '__main__':
    main()

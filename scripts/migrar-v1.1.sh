#!/usr/bin/env bash
# Copia dados persistentes da v1.1 para v1.2, sem alterar a origem.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Uso: $0 /caminho/ia-video-studio-v1.1 [--comfy]" >&2
  exit 2
fi
OLD="$(realpath "$1")"
if [[ "$OLD" == "$ROOT" ]]; then echo '[ERRO] Origem e destino são iguais.' >&2; exit 1; fi
if [[ ! -d "$OLD/studio-data/projects" ]]; then echo '[ERRO] Pasta de projetos da v1.1 não encontrada.' >&2; exit 1; fi
if [[ $# -eq 2 && "$2" != '--comfy' ]]; then echo '[ERRO] Use apenas --comfy como segundo argumento.' >&2; exit 2; fi
if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'ia-video-studio'; then
  echo '[ERRO] Remova o container antigo preservando volumes: no diretório v1.1 execute docker compose down (SEM -v)' >&2
  exit 1
fi
mkdir -p "$ROOT/studio-data" "$ROOT/studio-data/projects" "$ROOT/studio-data/voices" "$ROOT/studio-data/trash"
# Não sobrepor IDs de projetos existentes no destino.
for entry in "$OLD"/studio-data/projects/* "$OLD"/studio-data/trash/*; do
  [[ -e "$entry" ]] || continue
  name="$(basename "$entry")"
  case "$name" in .gitkeep) continue;; esac
  if [[ "$(basename "$(dirname "$entry")")" == 'projects' ]]; then target="$ROOT/studio-data/projects/$name"; else target="$ROOT/studio-data/trash/$name"; fi
  if [[ -e "$target" ]]; then echo "[ERRO] Já existe $target. Migração interrompida para não sobrescrever dados." >&2; exit 1; fi
done
for sub in projects voices trash; do
  [[ -d "$OLD/studio-data/$sub" ]] || continue
  cp -an "$OLD/studio-data/$sub/." "$ROOT/studio-data/$sub/"
done
if [[ -f "$OLD/.env" && ! -f "$ROOT/.env" ]]; then cp -a "$OLD/.env" "$ROOT/.env"; fi
if [[ "${2:-}" == '--comfy' && -d "$OLD/data" ]]; then
  mkdir -p "$ROOT/data"
  cp -an "$OLD/data/." "$ROOT/data/"
fi
printf '[OK] Dados copiados (origem preservada).\nProjetos: %s\nVozes: %s\n' "$(find "$ROOT/studio-data/projects" -mindepth 1 -maxdepth 1 -type d | wc -l)" "$(find "$ROOT/studio-data/voices" -maxdepth 1 -type f | wc -l)"
echo 'Agora execute ./scripts/preparar.sh && docker compose up -d --build studio'

#!/usr/bin/env bash
# Copia persistent data da v1.2 para a v1.3 sem sobrescrever nenhum projeto.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
usage(){ echo "Uso: $0 /caminho/ia-video-studio-v1.2 [--comfy]" >&2;exit 2;}
[[ $# -ge 1 && $# -le 2 ]] || usage
[[ "${2:-}" == '' || "${2:-}" == '--comfy' ]] || usage
OLD="$(realpath "$1")"
[[ "$OLD" != "$ROOT" ]] || { echo '[ERRO] Origem igual ao destino' >&2;exit 1; }
[[ -d "$OLD/studio-data/projects" ]] || { echo '[ERRO] Nenhuma pasta studio-data/projects na origem' >&2;exit 1; }
if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'ia-video-studio';then
  echo '[ERRO] Container ia-video-studio ainda existe. Execute docker compose down na v1.2 (SEM -v).' >&2
  exit 1
fi
for sub in projects trash;do
  for entry in "$OLD/studio-data/$sub"/*;do
    [[ -d "$entry" ]] || continue
    name="$(basename "$entry")"
    if [[ -e "$ROOT/studio-data/$sub/$name" ]];then
      echo "[ERRO] Projeto $name já existe no destino, migração interrompida" >&2
      exit 1
    fi
  done
done
mkdir -p "$ROOT/studio-data" "$ROOT/studio-data/projects" "$ROOT/studio-data/trash" "$ROOT/studio-data/voices"
for sub in projects trash voices;do
  [[ -d "$OLD/studio-data/$sub" ]] && cp -an "$OLD/studio-data/$sub/." "$ROOT/studio-data/$sub/"
done
[[ -f "$OLD/.env" && ! -f "$ROOT/.env" ]] && cp -a "$OLD/.env" "$ROOT/.env"
if [[ "${2:-}" == '--comfy' && -d "$OLD/data" ]];then
  mkdir -p "$ROOT/data"
  cp -an "$OLD/data/." "$ROOT/data/"
fi
printf '[OK] Dados da v1.2 copiados. Origem preservada.\nProjetos ativos: %s\nProjetos na lixeira: %s\n' \
  "$(find "$ROOT/studio-data/projects" -mindepth 1 -maxdepth 1 -type d | wc -l)" \
  "$(find "$ROOT/studio-data/trash" -mindepth 1 -maxdepth 1 -type d | wc -l)"
echo 'Inicie: ./scripts/preparar.sh && docker compose up -d --build studio'

#!/usr/bin/env bash
# Valida o projeto sem depender de Python ou Node de desenvolvimento no HOST.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
for f in scripts/*.sh docker/*.sh; do bash -n "$f"; done
python3 -m compileall -q studio
if command -v node >/dev/null 2>&1;then
  node --check studio/static/app.js
  node --check studio/renderer/export_pptx.cjs
fi
python3 tools/validate_workflow.py
if command -v docker >/dev/null 2>&1;then
  docker compose config --quiet
  docker compose -f compose.yaml -f compose.comfy.yaml --profile wan config --quiet
  if docker image inspect ia-video-studio:1.3-local >/dev/null 2>&1; then
    echo '[INFO] Testando APIs e renderização PDF/PPTX na imagem Docker.'
    docker compose run --rm --no-deps --entrypoint python studio -m unittest discover -s /opt/tests -v
  else
    echo '[INFO] Build ainda não realizado: execute docker compose build studio antes dos testes completos.'
  fi
else
  echo '[INFO] Docker indisponível: testes da imagem serão executados no notebook.'
fi
echo '[OK] Validação concluída.'

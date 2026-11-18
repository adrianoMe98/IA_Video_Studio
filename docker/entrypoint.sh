#!/usr/bin/env bash
set -Eeuo pipefail
cd /app/ComfyUI
mkdir -p custom_nodes user/default/workflows input output temp
if [[ ! -f custom_nodes/ComfyUI-GGUF/nodes.py ]]; then
  echo '[init] Instalando node ComfyUI-GGUF no volume persistente...'
  rm -rf custom_nodes/ComfyUI-GGUF
  cp -a /opt/ComfyUI-GGUF custom_nodes/ComfyUI-GGUF
fi
if [[ ! -f user/default/workflows/wan21_1.3b_4gb_ui.json ]]; then
  cp /opt/seed-workflows/wan21_1.3b_4gb_ui.json user/default/workflows/
fi
echo '[init] Iniciando ComfyUI com perfil de baixo consumo...'
exec "$@"

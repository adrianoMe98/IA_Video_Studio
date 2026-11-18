#!/usr/bin/env bash
set -u
printf '%s\n' '=== IA VIDEO STUDIO - DIAGNÓSTICO ==='
printf '\n=== HOST ===\n'
uname -srm
free -h | head -3 || true
printf '\n=== DOCKER (necessário para videoaulas) ===\n'
if command -v docker >/dev/null; then
  docker version --format 'Cliente: {{.Client.Version}} | Servidor: {{.Server.Version}}' || true
  docker compose version || true
  docker compose ps || true
else
  echo '[ERRO] Docker ausente.'
fi
printf '\n=== GPU (necessária SOMENTE para Wan/ComfyUI) ===\n'
if command -v nvidia-smi >/dev/null; then
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
else
  echo '[INFO] nvidia-smi não encontrado: estúdio de videoaulas continua funcionando por CPU.'
fi
printf '\n=== ARMAZENAMENTO ===\n'
df -h . | tail -1

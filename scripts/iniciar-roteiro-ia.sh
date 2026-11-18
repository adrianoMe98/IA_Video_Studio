#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# Carregar o modelo configurado em .env, sem executar arquivos .env como shell script.
MODEL="$(sed -n 's/^OLLAMA_MODEL=//p' .env | head -1)"
MODEL="${MODEL:-qwen2.5:1.5b}"
docker compose --profile roteiro-ia up -d ollama
echo "Baixando modelo de roteiro: $MODEL"
docker compose --profile roteiro-ia exec -T ollama ollama pull "$MODEL"
echo 'Ativado. Na interface, clique Sugerir cenas com IA.'

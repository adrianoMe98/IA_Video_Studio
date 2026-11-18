#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p studio-data/{voices,projects} data/{models,custom_nodes,user,input,output,temp,cache}
if [[ ! -f .env ]]; then
  cp .env.example .env
  sed -i "s/^PUID=.*/PUID=$(id -u)/;s/^PGID=.*/PGID=$(id -g)/" .env
  echo '[OK] .env criado com UID/GID atuais.'
else
  echo '[INFO] .env preservado.'
fi
if [[ ! -w studio-data ]]; then
  echo '[AVISO] studio-data não permite escrita ao usuário atual. Ajuste permissões do diretório.'
fi
printf 'Espaço livre: '; df -h . | awk 'NR==2 {print $4}'
echo 'Próximo: docker compose build studio && ./scripts/baixar-voz.sh && docker compose up -d studio'

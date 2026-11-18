#!/usr/bin/env bash
set -Eeuo pipefail
if (( $# < 1 || $# > 2 )); then
  echo 'Uso: scripts/webp-para-mp4.sh arquivo.webp [arquivo.mp4]' >&2
  exit 2
fi
command -v ffmpeg >/dev/null || { echo 'Instale ffmpeg no host: sudo apt install ffmpeg' >&2; exit 1; }
SRC="$1"
DST="${2:-${SRC%.*}.mp4}"
ffmpeg -hide_banner -y -i "$SRC" -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2'   -c:v libx264 -crf 22 -preset medium -pix_fmt yuv420p -movflags +faststart "$DST"
echo "Salvo em: $DST"

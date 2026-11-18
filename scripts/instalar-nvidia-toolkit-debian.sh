#!/usr/bin/env bash
# Execute manualmente APENAS se docker --gpus all falhar e nvidia-smi funcionar no host.
set -Eeuo pipefail
if ! command -v nvidia-smi >/dev/null; then
  echo '[ERRO] Instale/corrija o driver proprietário NVIDIA primeiro.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y curl ca-certificates gnupg
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |   sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |   sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
printf '\n[OK] Toolkit configurado. Execute: ./scripts/diagnostico.sh\n'

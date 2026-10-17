#!/usr/bin/env bash
# One-time, idempotent setup of the fresh Ubuntu exam VM (1x NVIDIA L40S):
#   Docker Engine + compose/buildx plugins, NVIDIA Container Toolkit, rsync/python3,
#   then proves the GPU is visible INSIDE the pinned llama.cpp CUDA container.
#
#   sudo bash docker/prod_bootstrap.sh
#
# Env: LLM_IMAGE (default: pinned llama.cpp CUDA server), INSTALL_DRIVER=1 (install the
#      NVIDIA data-center driver via ubuntu-drivers if nvidia-smi is missing; needs a reboot),
#      SKIP_GPU_TEST=1
set -euo pipefail
[ "$(id -u)" = 0 ] || exec sudo -E bash "$0" "$@"

LLM_IMAGE=${LLM_IMAGE:-ghcr.io/ggml-org/llama.cpp:server-cuda-b11176}
TARGET_USER=${SUDO_USER:-$(logname 2>/dev/null || echo root)}
export DEBIAN_FRONTEND=noninteractive
log() { printf '\n[bootstrap %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

. /etc/os-release
[ "${ID:-}" = ubuntu ] || log "WARNING: tested on Ubuntu 22.04/24.04 only (found ${PRETTY_NAME:-unknown})"
[ "$(uname -m)" = x86_64 ] || log "WARNING: expected x86_64, found $(uname -m)"

# ---------------------------------------------------------------- 0. host driver
log "host GPU driver"
if ! nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi does not work on the host."
  if [ "${INSTALL_DRIVER:-0}" = 1 ]; then
    apt-get update && apt-get install -y ubuntu-drivers-common
    ubuntu-drivers install --gpgpu
    echo "Driver installed. REBOOT the VM and run this script again."
    exit 3
  fi
  echo "Install the data-center driver first (or rerun with INSTALL_DRIVER=1):"
  echo "  sudo apt-get install -y ubuntu-drivers-common && sudo ubuntu-drivers install --gpgpu && sudo reboot"
  exit 2
fi
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
DRV_MAJOR=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1 | cut -d. -f1)
if [ "${DRV_MAJOR:-0}" -lt 570 ]; then
  log "NOTE: driver $DRV_MAJOR < 570. The CUDA 12.8 image relies on forward compatibility (OK on"
  log "      data-center GPUs with 535/550 branches). If llama-server reports no CUDA device, upgrade the driver."
fi

# ---------------------------------------------------------------- 1. base tools
log "base packages"
apt-get update
apt-get install -y ca-certificates curl gnupg rsync python3 jq pigz

# ---------------------------------------------------------------- 2. Docker Engine
if ! command -v docker >/dev/null 2>&1; then
  log "installing Docker Engine (download.docker.com apt repo)"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker present: $(docker --version)"
  docker compose version >/dev/null 2>&1 || apt-get install -y docker-compose-plugin
fi
systemctl enable --now docker
if [ "$TARGET_USER" != root ]; then
  usermod -aG docker "$TARGET_USER" && log "added $TARGET_USER to group docker (re-login to take effect)"
fi

# ---------------------------------------------------------------- 3. NVIDIA Container Toolkit
if ! command -v nvidia-ctk >/dev/null 2>&1; then
  log "installing NVIDIA Container Toolkit"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update
  apt-get install -y nvidia-container-toolkit
else
  log "NVIDIA Container Toolkit present: $(nvidia-ctk --version | head -1)"
fi
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

log "versions"
docker version --format 'docker {{.Server.Version}}'
docker compose version
docker info --format 'storage={{.Driver}} runtimes={{range $k,$v := .Runtimes}}{{$k}} {{end}}'

# ---------------------------------------------------------------- 4. GPU inside the container
if [ "${SKIP_GPU_TEST:-0}" != 1 ]; then
  if ! docker image inspect "$LLM_IMAGE" >/dev/null 2>&1; then
    TARBALL=$(ls "$(dirname "$0")"/../dist/*llama.cpp*cuda*linux-amd64.tar.gz "$(dirname "$0")"/../dist/server-cuda*linux-amd64.tar.gz 2>/dev/null | head -1 || true)
    if [ -n "$TARBALL" ]; then
      log "loading $TARBALL"; docker load -i "$TARBALL"
    else
      log "pulling $LLM_IMAGE"; docker pull "$LLM_IMAGE"
    fi
  fi
  log "nvidia-smi inside $LLM_IMAGE"
  docker run --rm --gpus all --entrypoint nvidia-smi "$LLM_IMAGE"
  log "llama.cpp devices inside $LLM_IMAGE"
  docker run --rm --gpus all "$LLM_IMAGE" --list-devices
fi
log "BOOTSTRAP OK"

# Source me on the Mac build host (non-interactive SSH sessions):  . docker/mac_env.sh
# - exposes Docker Desktop's `docker` CLI (only the CLI, via a private bin dir)
# - uses a private DOCKER_CONFIG without the "desktop" credsStore, because the macOS keychain
#   is locked in SSH sessions and every registry call would fail with "keychain cannot be accessed".
#   The Docker CLI auto-detects docker-credential-osxkeychain on PATH, so Docker.app/Contents/
#   Resources/bin must NOT be on PATH.  Anonymous pulls (python:3.12-slim,
#   ghcr.io/ggml-org/llama.cpp) need no credentials.
case "$(uname -s)" in
  Darwin)
    _wmt_cfg="${WMT_DOCKER_CONFIG:-$HOME/.wmt-docker-config}"
    _res=/Applications/Docker.app/Contents/Resources
    if [ ! -x "$_wmt_cfg/bin/docker" ]; then
      mkdir -p "$_wmt_cfg/cli-plugins" "$_wmt_cfg/bin"
      [ -f "$_wmt_cfg/config.json" ] || printf '{\n  "auths": {}\n}\n' > "$_wmt_cfg/config.json"
      ln -sf "$_res/bin/docker" "$_wmt_cfg/bin/docker"
      for p in docker-buildx docker-compose; do
        [ -e "$_res/cli-plugins/$p" ] && ln -sf "$_res/cli-plugins/$p" "$_wmt_cfg/cli-plugins/$p"
      done
    fi
    PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v "^$_res/bin\$" | paste -sd: -)
    export PATH="$_wmt_cfg/bin:$PATH"
    export DOCKER_CONFIG="$_wmt_cfg"
    export DOCKER_HOST="${DOCKER_HOST:-unix://$HOME/.docker/run/docker.sock}"
    unset _wmt_cfg _res
    ;;
esac

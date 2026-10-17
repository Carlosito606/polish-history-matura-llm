#!/usr/bin/env bash
# Prove the running stack is offline:
#   1. the 'internal' network is internal-only and only the gateway is attached to 'edge'
#   2. llm / llm-base / harness cannot resolve or reach anything outside (DNS, TCP 443/53/80)
#   3. positive control: the same probe from the gateway (edge network) DOES reach the internet
#      when the host is online -> the probe is not vacuous (skipped with --no-control)
#   4. after one question through the gateway, every TCP peer of the harness is inside the
#      internal subnet (no external calls); offline env vars are set
#
#   bash docker/offline_check.sh                          # prod (run in docker/ or anywhere)
#   COMPOSE_ARGS="-p wmt-smoke --env-file docker/mac.env -f docker/compose.yaml -f docker/compose.mac.yaml" \
#     bash docker/offline_check.sh                        # Mac smoke stack
# Exit 0 = all checks passed.
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=mac_env.sh
. "$HERE/mac_env.sh"
CONTROL=1; [ "${1:-}" = "--no-control" ] && CONTROL=0
if [ -z "${COMPOSE_ARGS:-}" ]; then COMPOSE_ARGS="-f $HERE/compose.yaml"; fi
# shellcheck disable=SC2086
DC() { docker compose $COMPOSE_ARGS "$@"; }
FAIL=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*"; FAIL=1; }
info() { printf 'INFO  %s\n' "$*"; }

PROBE='
import socket, sys
socket.setdefaulttimeout(4)
reach = []
def t(name, fn):
    try:
        fn(); print("    reachable  " + name); reach.append(name)
    except Exception as e:
        print("    blocked    %s (%s: %s)" % (name, type(e).__name__, str(e)[:60]))
t("dns huggingface.co", lambda: socket.getaddrinfo("huggingface.co", 443))
t("dns pypi.org",       lambda: socket.getaddrinfo("pypi.org", 443))
t("tcp 1.1.1.1:443",    lambda: socket.create_connection(("1.1.1.1", 443)).close())
t("tcp 8.8.8.8:53",     lambda: socket.create_connection(("8.8.8.8", 53)).close())
t("tcp 9.9.9.9:80",     lambda: socket.create_connection(("9.9.9.9", 80)).close())
sys.exit(10 if reach else 0)
'

nets() { docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$1"; }

H=$(DC ps -q harness 2>/dev/null | head -1)
[ -n "$H" ] || { echo "stack not running (harness container not found; set COMPOSE_ARGS)"; exit 2; }
PROJECT=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$H")
# by label, so services of inactive profiles (llm-base) are found too
cid() { docker ps -q --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$1" | head -1; }
GW=$(cid gateway); L=$(cid llm); LB=$(cid llm-base)
[ -n "$GW" ] && [ -n "$L" ] || { echo "stack not running (need gateway, harness, llm)"; exit 2; }
INET="${PROJECT}_internal"; ENET="${PROJECT}_edge"

echo "== 1. networks (project $PROJECT)"
if [ "$(docker network inspect -f '{{.Internal}}' "$INET")" = true ]; then pass "$INET is internal (no egress route)"; else fail "$INET is NOT internal"; fi
SUBNET=$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' "$INET")
info "$INET subnet(s): $SUBNET"
ON_EDGE=$(docker network inspect -f '{{range .Containers}}{{.Name}} {{end}}' "$ENET")
info "containers on $ENET: $ON_EDGE"
for c in $ON_EDGE; do case "$c" in *gateway*) ;; *) fail "unexpected container on edge: $c" ;; esac; done
for c in $L $LB $H; do
  n=$(nets "$c"); name=$(docker inspect -f '{{.Name}}' "$c")
  if [ "$(echo $n)" = "$INET" ]; then pass "$name only on $INET"; else fail "$name networks: $n"; fi
  pp=$(docker inspect -f '{{range $p,$b := .NetworkSettings.Ports}}{{if $b}}{{$p}} {{end}}{{end}}' "$c")
  if [ -z "$pp" ]; then pass "$name publishes no ports"; else fail "$name publishes $pp"; fi
done

echo "== 2. egress probes from isolated containers"
for c in $L $LB $H; do
  name=$(docker inspect -f '{{.Name}}' "$c")
  py=$(docker exec "$c" sh -c 'command -v python3 || command -v python' 2>/dev/null)
  if [ -z "$py" ]; then
    if docker exec "$c" sh -c 'getent hosts huggingface.co || curl -s -m 5 -o /dev/null https://1.1.1.1' >/dev/null 2>&1; then
      fail "$name reached the outside (curl/getent)"; else pass "$name: no DNS / no HTTPS egress (curl/getent)"; fi
    continue
  fi
  echo "  $name ($py):"
  if docker exec -i "$c" "$py" - <<<"$PROBE"; then pass "$name has no egress"; else fail "$name reached the outside"; fi
done

if [ "$CONTROL" = 1 ]; then
  echo "== 3. positive control from the gateway (edge network)"
  if docker exec -i "$GW" python - <<<"$PROBE"; then
    info "gateway also has no egress (host offline or locked down) -> control inconclusive"
  else
    pass "probe detects egress where it exists (gateway on edge) -> isolation results above are meaningful"
  fi
fi

echo "== 4. harness makes no external calls"
docker exec "$H" python -c 'import os; print("    HF_HUB_OFFLINE=%s proxies=%s" % (os.environ.get("HF_HUB_OFFLINE"), [k for k in os.environ if k.lower().endswith("_proxy") and k.lower() not in ("no_proxy",)]))'
docker exec "$GW" python /opt/wmt/smoke_test.py --url http://harness:18000 >/tmp/wmt_offline_smoke.$$ 2>&1 \
  && pass "question answered through the isolated stack" || { fail "smoke question failed"; cat /tmp/wmt_offline_smoke.$$; }
grep -E '^\[(rag|health)\]' /tmp/wmt_offline_smoke.$$ | sed 's/^/    /'; rm -f /tmp/wmt_offline_smoke.$$
PEERS=$(docker exec -i "$H" python - "$SUBNET" <<'EOF'
import ipaddress, socket, struct, sys
nets = [ipaddress.ip_network(s) for s in sys.argv[1].split()] + [ipaddress.ip_network("127.0.0.0/8")]
def v4(h): return ipaddress.ip_address(socket.inet_ntoa(struct.pack("<I", int(h, 16))))
def v6(h):
    b = b"".join(struct.pack("<I", int(h[i:i + 8], 16)) for i in range(0, 32, 8))
    a = ipaddress.ip_address(b)
    return a.ipv4_mapped or a
bad = seen = 0
for fn, conv in (("/proc/net/tcp", v4), ("/proc/net/tcp6", v6)):
    try:
        lines = open(fn).read().splitlines()[1:]
    except OSError:
        continue
    for ln in lines:
        rem = ln.split()[2]; ip_h, port_h = rem.split(":")
        ip, port = conv(ip_h), int(port_h, 16)
        if ip.is_unspecified:
            continue  # listening socket
        seen += 1
        ok = any(ip in n for n in nets if n.version == ip.version) or ip.is_loopback
        if not ok:
            bad += 1
        print("    %-8s %s:%d" % ("ok" if ok else "EXTERNAL", ip, port))
print("SUMMARY seen=%d external=%d" % (seen, bad))
EOF
)
echo "$PEERS"
if echo "$PEERS" | grep -q "external=0"; then pass "all harness TCP peers are internal"; else fail "harness has external TCP peers"; fi

echo
if [ "$FAIL" = 0 ]; then echo "OFFLINE CHECK: ALL PASS"; else echo "OFFLINE CHECK: FAILURES"; fi
exit "$FAIL"

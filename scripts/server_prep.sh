#!/usr/bin/env bash
set -euo pipefail

retry() {  # retry helper: retry CMD up to N times with backoff
  local n=0; local max=5; local delay=3
  until "$@"; do
    n=$((n+1))
    if [[ $n -ge $max ]]; then echo "ERROR: '$*' failed after $n attempts"; return 1; fi
    echo "retry $n for: $*"; sleep $((delay*n))
  done
}

# Clean any bad caches first
sudo dnf clean all || true
sudo rm -rf /var/cache/dnf || true
retry sudo dnf -y makecache

# Install packages (no cache, allow best resolution)
retry sudo dnf -y install --setopt=keepcache=0 --best --allowerasing httpd iperf3 coreutils

# Prepare test payloads
sudo mkdir -p /var/www/html/hls
sudo dd if=/dev/zero of=/var/www/html/big.bin bs=1M count=200
for i in $(seq -w 1 20); do
  sudo dd if=/dev/zero of=/var/www/html/hls/seg${i}.ts bs=1M count=2
done

# Start services
sudo systemctl enable --now httpd
nohup iperf3 -s -p 5001 >/var/log/iperf3-server.log 2>&1 &
echo "server_prep: DONE"

#!/usr/bin/env bash
# run_experiments.sh  (client-side; invoked via SSM)
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <SERVER_PRIVATE_IP>"
  exit 1
fi
SERVER_IP="$1"
CSV="/var/log/net-experiments.csv"
DUR=10
PAR=4
UDP_RATE="1G"
HTTP_URL_BIG="http://${SERVER_IP}/big.bin"
HLS_URL_PREFIX="http://${SERVER_IP}/hls/seg"
HLS_SEG_COUNT=10

# tools
sudo yum install -y iperf3 iproute-tc jq sysstat curl awscli >/dev/null 2>&1 || true

# AL2023 interface is ens5 on Nitro
IFACE="ens5"

# helpers
cc_get() { sysctl -n net.ipv4.tcp_congestion_control; }
cc_set() { sudo sysctl -w net.ipv4.tcp_congestion_control="$1" >/dev/null; }
mtu_set() { sudo ip link set dev "$IFACE" mtu "$1"; }
impair_clear() { sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true; }
impair_set() {
  local delay="$1" loss="$2"
  impair_clear
  if [[ "$delay" != "0" || "$loss" != "0" ]]; then
    sudo tc qdisc add dev "$IFACE" root netem ${delay:+delay $delay} ${loss:+loss $loss}
  fi
}
cpu_sample() { mpstat 1 3 | awk '/Average:/ && $3 ~ /all/ {print 100-$12}'; }

ping_block() {
  ping -c 20 "$SERVER_IP" | tee /tmp/ping.txt >/dev/null
  AVG=$(awk -F'/' '/rtt/ {print $5}' /tmp/ping.txt)
  MDEV=$(awk -F'/' '/rtt/ {print $7}' /tmp/ping.txt)
  echo "$AVG"  > /tmp/ping_avg
  echo "$MDEV" > /tmp/ping_mdev
}

iperf_tcp() {
  iperf3 -c "$SERVER_IP" -p 5001 -P "$PAR" -t "$DUR" --json > /tmp/iperf_tcp.json
  jq -r '.end.sum_received.bits_per_second' /tmp/iperf_tcp.json | awk '{printf "%.2f", $1/1e9}' > /tmp/tcp_gbps
  jq -r '[.end.streams[].sender.retransmits] | add' /tmp/iperf_tcp.json > /tmp/tcp_retr
}

iperf_udp() {
  iperf3 -c "$SERVER_IP" -p 5001 -u -b "$UDP_RATE" -t "$DUR" --json > /tmp/iperf_udp.json
  jq -r '.end.sum.bits_per_second' /tmp/iperf_udp.json | awk '{printf "%.2f", $1/1e9}' > /tmp/udp_gbps
  jq -r '.end.sum.lost_percent' /tmp/iperf_udp.json | awk '{printf "%.2f", $1}' > /tmp/udp_loss
  jq -r '.end.sum.jitter_ms' /tmp/iperf_udp.json | awk '{printf "%.3f", $1}' > /tmp/udp_jitter
}

app_progressive() {
  curl -s -w "%{time_starttransfer} %{time_total}\n" -o /dev/null "$HTTP_URL_BIG" > /tmp/app_progressive.txt
}

app_hls_loop() {
  > /tmp/app_hls_times.txt
  for i in $(seq -w 1 "$HLS_SEG_COUNT"); do
    /usr/bin/time -f "%e" curl -s -o /dev/null "${HLS_URL_PREFIX}${i}.ts" 2>> /tmp/app_hls_times.txt
  done
  awk '{s+=$1} END{if(NR>0) printf "%.3f", s/NR; else print "0.000"}' /tmp/app_hls_times.txt > /tmp/app_hls_avg
}

csv_header() {
  if [[ ! -f "$CSV" ]]; then
    echo "exp,topo,cc,mtu,impair,load,duration_s,ping_avg_ms,ping_mdev_ms,tcp_sum_gbps,tcp_retr,udp_gbps,udp_loss_pct,udp_jitter_ms,cpu_client_pct,app_ttfb_s,app_total_s,app_hls_avg_s,notes" | sudo tee -a "$CSV" >/dev/null
  fi
}

record() {
  local exp="$1" topo="$2" cc="$3" mtu="$4" impair="$5" load="$6" notes="$7"
  local PING_AVG=$(cat /tmp/ping_avg 2>/dev/null || echo "")
  local PING_MDEV=$(cat /tmp/ping_mdev 2>/dev/null || echo "")
  local TCP_G=$(cat /tmp/tcp_gbps 2>/dev/null || echo "")
  local TCP_R=$(cat /tmp/tcp_retr 2>/dev/null || echo "")
  local UDP_G=$(cat /tmp/udp_gbps 2>/dev/null || echo "")
  local UDP_L=$(cat /tmp/udp_loss 2>/dev/null || echo "")
  local UDP_J=$(cat /tmp/udp_jitter 2>/dev/null || echo "")
  local CPU=$(cpu_sample)
  local TTFB=$(awk '{print $1}' /tmp/app_progressive.txt 2>/dev/null || echo "")
  local ATOT=$(awk '{print $2}' /tmp/app_progressive.txt 2>/dev/null || echo "")
  local HLSA=$(cat /tmp/app_hls_avg 2>/dev/null || echo "")
  printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%.1f,%s,%s,%s,%s\n" \
    "$exp" "$topo" "$cc" "$mtu" "$impair" "$load" "$DUR" \
    "$PING_AVG" "$PING_MDEV" "$TCP_G" "$TCP_R" "$UDP_G" "$UDP_L" "$UDP_J" "$CPU" "$TTFB" "$ATOT" "$HLSA" "$notes" \
    | sudo tee -a "$CSV" >/dev/null
}

csv_header

run_bundle() {
  local EXP="$1" TOPO="$2" CC="$3" MTU="$4" IMP="$5" LOAD="$6" NOTES="$7"
  echo "[*] $EXP: topo=$TOPO cc=$CC mtu=$MTU impair=$IMP load=$LOAD"
  cc_set "$CC"
  mtu_set "$MTU"
  case "$IMP" in
    none) impair_set 0 0 ;;
    d50)  impair_set 50ms 0 ;;
    l1p)  impair_set 0 1% ;;
    d50l1p) impair_set 50ms 1% ;;
  esac

  ping_block
  iperf_tcp
  iperf_udp

  if [[ "$EXP" =~ ^E(9|10|11)$ ]]; then
    app_progressive
    [[ "$EXP" == "E11" ]] && app_hls_loop || true
  else
    : > /tmp/app_progressive.txt || true
    : > /tmp/app_hls_avg || true
  fi

  record "$EXP" "$TOPO" "$CC" "$MTU" "$IMP" "$LOAD" "$NOTES"
  impair_clear
}

# Experiment matrix
run_bundle E1  T1 cubic 1500 none   none "baseline same-AZ private, CUBIC"
run_bundle E2  T1 cubic 9001 none   none "jumbo same-AZ private, CUBIC"
run_bundle E3  T1 bbr   1500 none   none "BBR vs CUBIC"
run_bundle E4  T1 bbr   9001 none   none "BBR + jumbo"
run_bundle E5  T2 cubic 1500 none   none "cross-AZ (set client in another AZ first)"
run_bundle E6  T3 cubic 1500 none   none "public-path via IGW (use server public IP if you modify script)"
run_bundle E7  T1 cubic 1500 l1p    none "loss 1%"
run_bundle E8  T1 bbr   1500 l1p    none "loss 1% with BBR"

run_bundle E9  T1 cubic 1500 none   none "HTTP big.bin"
run_bundle E10 T1 cubic 1500 d50    none "HTTP with 50ms delay"
run_bundle E11 T1 cubic 1500 l1p    none "HLS-like under 1% loss"

echo "✅ Done. CSV at: $CSV"

# Optional upload to S3 if RESULT_S3_URI is provided
if [[ -n "${RESULT_S3_URI:-}" ]]; then
  TS=$(date +%Y%m%d-%H%M%S)
  /usr/bin/aws s3 cp "$CSV" "${RESULT_S3_URI%/}/net-experiments-$TS.csv"
  echo "Uploaded results to ${RESULT_S3_URI%/}/net-experiments-$TS.csv"
fi

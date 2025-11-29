import sys, pandas as pd, matplotlib.pyplot as plt

if len(sys.argv) < 2:
    print("Usage: python analyze_results.py net-experiments.csv")
    sys.exit(1)

csv = sys.argv[1] if len(sys.argv) > 1 else "results/net-experiments-latest.csv"

cols = [
    "exp","topo","cc","mtu","impair","load","duration_s",
    "ping_avg_ms","ping_mdev_ms","tcp_sum_gbps","tcp_retr",
    "udp_gbps","udp_loss_pct","udp_jitter_ms","cpu_client_pct",
    "app_ttfb_s","app_total_s","app_hls_avg_s","notes"
]

df_raw = pd.read_csv(csv, header=0, engine='python', index_col=False)

# Fix overflow from commas in notes if needed
if len(df_raw.columns) > len(cols):
    df_raw["notes"] = df_raw[df_raw.columns[len(cols)-1:]].astype(str).agg(" ".join, axis=1)
    df_raw = df_raw.iloc[:, :len(cols)]

df_raw.columns = cols

# Trim
df = df_raw.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

# Clean mdev
df["ping_mdev_ms"] = df["ping_mdev_ms"].astype(str).str.replace(" ms","",regex=False)

# Convert numerics
num_cols = ["duration_s","ping_avg_ms","ping_mdev_ms","tcp_sum_gbps","tcp_retr",
            "udp_gbps","udp_loss_pct","udp_jitter_ms","cpu_client_pct",
            "app_ttfb_s","app_total_s","app_hls_avg_s"]
df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")

print(df.head(3).to_string())
print("Unique topo values:", df["topo"].unique())

# 1) MTU effect
mtu_df = df[(df.topo=="T1") & (df.cc=="cubic") & (df.impair=="none")]
if not mtu_df.empty:
    plt.figure()
    labels, vals = [], []
    for mtu, g in mtu_df.groupby("mtu"):
        labels.append(str(mtu)); vals.append(g["tcp_sum_gbps"].mean())
    plt.bar(labels, vals)
    plt.title("MTU effect on TCP throughput (T1, CUBIC, no impair)")
    plt.ylabel("TCP sum throughput (Gbps)")
    plt.xlabel("MTU")
    plt.savefig("fig_mtu.png", bbox_inches="tight")
else:
    print("[!] Skipping MTU plot — no data found")

# 2) CC clean vs loss
cc_clean = df[(df.topo=="T1") & (df.mtu==1500) & (df.impair=="none")]
if not cc_clean.empty:
    plt.figure()
    cc_clean.groupby("cc")["tcp_sum_gbps"].mean().plot(kind="bar")
    plt.title("CC vs throughput (clean network, T1, MTU1500)")
    plt.ylabel("TCP sum throughput (Gbps)")
    plt.savefig("fig_cc.png", bbox_inches="tight")
else:
    print("[!] Skipping CC clean plot — no data found")

cc_loss  = df[(df.topo=="T1") & (df.mtu==1500) & (df.impair=="l1p")]
if not cc_loss.empty:
    plt.figure()
    cc_loss.groupby("cc")["tcp_sum_gbps"].mean().plot(kind="bar")
    plt.title("CC vs throughput (1% loss, T1, MTU1500)")
    plt.ylabel("TCP sum throughput (Gbps)")
    plt.savefig("fig_cc_loss.png", bbox_inches="tight")
else:
    print("[!] Skipping CC loss plot — no data found")

# 3) Impairments impact
imp_df = df[(df.topo=="T1") & (df.cc=="cubic") & (df.mtu==1500)]
if not imp_df.empty:
    plt.figure()
    for imp, g in imp_df.groupby("impair"):
        plt.bar(imp, g["tcp_sum_gbps"].mean())
    plt.title("Impairments vs TCP throughput (T1, CUBIC, MTU1500)")
    plt.ylabel("TCP sum throughput (Gbps)")
    plt.savefig("fig_impair.png", bbox_inches="tight")
else:
    print("[!] Skipping Impair plot — no data found")

# 4) Path comparison
path_df = df[(df.cc=="cubic") & (df.mtu==1500) & (df.impair=="none") & (df.exp.isin(["E1","E5","E6"]))]
if not path_df.empty:
    plt.figure()
    for topo, g in path_df.groupby("topo"):
        plt.bar(topo, g["ping_avg_ms"].mean())
    plt.title("Path vs Latency (avg RTT)")
    plt.ylabel("Ping avg (ms)")
    plt.savefig("fig_paths.png", bbox_inches="tight")
else:
    print("[!] Skipping Path plot — no data found")

# 5) App QoE
app_df = df[df.exp.isin(["E9","E10","E11"])]
if not app_df.empty:
    plt.figure()
    for exp, g in app_df.groupby("exp"):
        plt.bar(exp, g["app_ttfb_s"].mean())
    plt.title("App TTFB (progressive download)")
    plt.ylabel("seconds")
    plt.savefig("fig_app_ttfb.png", bbox_inches="tight")

    plt.figure()
    for exp, g in app_df.groupby("exp"):
        plt.bar(exp, g["app_hls_avg_s"].mean())
    plt.title("HLS-like avg segment fetch time")
    plt.ylabel("seconds/segment")
    plt.savefig("fig_app.png", bbox_inches="tight")
else:
    print("[!] Skipping App QoE plot — no data found")

print("Plots generated")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
import os
import json

# Ensure we use a non-interactive backend for saving plots without a display
plt.switch_backend('Agg')

OUTPUT_DIR = 'artifacts'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def generate_fidelity_plot():
    print("Generating Fidelity Plot (CDF)...")
    
    try:
        # Load Data
        df_real = pd.read_csv('real_traffic.csv')
        df_syn = pd.read_csv('synthetic_traffic.csv')
        
        real_iat = df_real['iat'].values
        syn_iat = df_syn['iat'].values
        
        # Calculate KS-Test
        statistic, p_value = ks_2samp(real_iat, syn_iat)
        print(f"  KS-Test Statistic: {statistic:.4f}")
        print(f"  P-Value: {p_value:.4f}")

        # Plot CDF
        plt.figure(figsize=(8, 6))
        plt.hist(real_iat, bins=50, density=True, histtype='step', cumulative=True, label='Real Traffic', linewidth=2)
        plt.hist(syn_iat, bins=50, density=True, histtype='step', cumulative=True, label='Synthetic (GAN)', linewidth=2, linestyle='--')
        plt.title('Fidelity: CDF of Packet Inter-arrival Times')
        plt.xlabel('Inter-arrival Time (ms)')
        plt.ylabel('Cumulative Probability')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        filename = os.path.join(OUTPUT_DIR, 'fidelity_cdf.png')
        plt.savefig(filename)
        print(f"  Saved to {filename}")
        plt.close()
        
    except FileNotFoundError:
        print("Error: Data files (real_traffic.csv, synthetic_traffic.csv) not found!")
        print("       Ensure simple_gan.py has been run first.")

def generate_utility_table():
    print("\nGenerating Utility Table...")
    try:
        with open('metrics.json', 'r') as f:
            metrics = json.load(f)
            
        real = metrics['utility']['real']
        syn = metrics['utility']['synthetic']
        
        data = {
            'Metric': ['Accuracy', 'Precision', 'Recall', 'F1-Score'],
            'Real Data (Baseline)': [
                real['Accuracy'], real['Precision'], real['Recall'], real['F1-Score']
            ],
            'Synthetic Data (Ours)': [
                syn['Accuracy'], syn['Precision'], syn['Recall'], syn['F1-Score']
            ]
        }
        # Round values
        data['Real Data (Baseline)'] = [round(x, 4) for x in data['Real Data (Baseline)']]
        data['Synthetic Data (Ours)'] = [round(x, 4) for x in data['Synthetic Data (Ours)']]
        
        df = pd.DataFrame(data)
        
        # Render as a plot table
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.axis('tight')
        ax.axis('off')
        table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.5)
        
        plt.title('Utility: Intrusion Detection System Performance (TSTR)', y=1.1)
        
        filename = os.path.join(OUTPUT_DIR, 'utility_table.png')
        plt.savefig(filename)
        print(f"  Saved to {filename}")
        plt.close()
        
    except FileNotFoundError:
        print("Error: metrics.json not found!")

def generate_efficiency_chart():
    print("\nGenerating Efficiency Chart...")
    try:
        with open('metrics.json', 'r') as f:
            metrics = json.load(f)
            
        gpu_mbps = metrics['efficiency']['gpu_throughput_mbps']
        cpu_mbps = metrics['efficiency']['cpu_throughput_mbps']
        
        # Convert to Gbps
        gpu_gbps = gpu_mbps / 1000.0
        cpu_gbps = cpu_mbps / 1000.0
        
        models = ['CPU Baseline', 'GAN (GPU)']
        throughput = [cpu_gbps, gpu_gbps]
        
        plt.figure(figsize=(8, 6))
        bars = plt.bar(models, throughput, color=['gray', 'tab:blue'])
        
        plt.title('Efficiency: Traffic Generation Throughput')
        plt.ylabel('Throughput (Gbps)')
        plt.grid(axis='y', alpha=0.3)
        
        # Add labels
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f} Gbps',
                    ha='center', va='bottom')

        filename = os.path.join(OUTPUT_DIR, 'efficiency_throughput.png')
        plt.savefig(filename)
        print(f"  Saved to {filename}")
        plt.close()
        
    except FileNotFoundError:
        print("Error: metrics.json not found!")

if __name__ == "__main__":
    print("Generating Research Artifacts...")
    try:
        generate_fidelity_plot()
    except Exception as e:
        print(f"FAILED to generate Fidelity Plot: {e}")
        import traceback
        traceback.print_exc()

    try:
        generate_utility_table()
    except Exception as e:
        print(f"FAILED to generate Utility Table: {e}")
        import traceback
        traceback.print_exc()

    try:
        generate_efficiency_chart()
    except Exception as e:
        print(f"FAILED to generate Efficiency Chart: {e}")
        import traceback
        traceback.print_exc()

    print("\nDone! Check the 'artifacts' directory.")

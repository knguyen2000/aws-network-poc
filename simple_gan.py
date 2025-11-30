import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
import os
import time
import json
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split

# Configuration
REAL_DATA_FILE = 'real_traffic.csv'
SYNTH_DATA_FILE = 'synthetic_traffic.csv'
METRICS_FILE = 'metrics.json'
MODEL_FILE = 'gan_model.pth'
EPOCHS = 50
BATCH_SIZE = 64
LR = 0.001
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

print(f"Using device: {device}")

# 1. Load or Generate Real Data
def load_or_create_real_data(n_samples=5000):
    if os.path.exists(REAL_DATA_FILE):
        print(f"Loading real data from {REAL_DATA_FILE}...")
        df = pd.read_csv(REAL_DATA_FILE)
        # Ensure required columns exist
        required_cols = ['iat', 'size']
        if not all(col in df.columns for col in required_cols):
            print(f"Warning: {REAL_DATA_FILE} missing columns {required_cols}. Generating dummy data instead.")
            return create_dummy_data(n_samples)
        
        # If label is missing, create a dummy one based on size (or 0)
        if 'label' not in df.columns:
            print("Adding dummy labels based on packet size...")
            df['label'] = (df['size'] > 1000).astype(int)
            
        return df
    else:
        return create_dummy_data(n_samples)

def create_dummy_data(n_samples):
    print(f"File {REAL_DATA_FILE} not found. Generating dummy data for demonstration...")
    # Packet Sizes: Bimodal
    sizes_small = np.random.normal(64, 5, int(n_samples * 0.5))
    sizes_large = np.random.normal(1500, 20, int(n_samples * 0.5))
    packet_sizes = np.concatenate([sizes_small, sizes_large])
    
    # Inter-arrival Times
    iat = np.random.exponential(scale=1.5, size=n_samples)
    
    # Labels: 1 if size > 1000 else 0
    labels = (packet_sizes > 1000).astype(int)
    
    df = pd.DataFrame({'iat': iat, 'size': packet_sizes, 'label': labels})
    df = df.sample(frac=1).reset_index(drop=True) # Shuffle
    df.to_csv(REAL_DATA_FILE, index=False)
    print(f"Saved {REAL_DATA_FILE}")
    return df

data_df = load_or_create_real_data()

# Prepare Data Loader
data_tensor = torch.tensor(data_df.values, dtype=torch.float32).to(device)
dataset = torch.utils.data.TensorDataset(data_tensor)
dataloader = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

# 2. Define GAN Models
class Generator(nn.Module):
    def __init__(self, input_dim=10, output_dim=3): # iat, size, label
        super(Generator, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim)
        )
    
    def forward(self, x):
        return self.net(x)

class Discriminator(nn.Module):
    def __init__(self, input_dim=3):
        super(Discriminator, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.LeakyReLU(0.2),
            nn.Linear(64, 32),
            nn.LeakyReLU(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        return self.net(x)

# Initialize
generator = Generator().to(device)
discriminator = Discriminator().to(device)
criterion = nn.BCELoss()
opt_g = optim.Adam(generator.parameters(), lr=LR)
opt_d = optim.Adam(discriminator.parameters(), lr=LR)

# 3. Train Loop
print("Starting GAN training...")
start_train = time.time()
for epoch in range(EPOCHS):
    for real_data, in dataloader:
        batch_size = real_data.size(0)
        
        # --- Train Discriminator ---
        opt_d.zero_grad()
        label_real = torch.ones(batch_size, 1).to(device)
        output_real = discriminator(real_data)
        loss_real = criterion(output_real, label_real)
        
        noise = torch.randn(batch_size, 10).to(device)
        fake_data = generator(noise)
        label_fake = torch.zeros(batch_size, 1).to(device)
        output_fake = discriminator(fake_data.detach())
        loss_fake = criterion(output_fake, label_fake)
        
        loss_d = loss_real + loss_fake
        loss_d.backward()
        opt_d.step()
        
        # --- Train Generator ---
        opt_g.zero_grad()
        output_fake = discriminator(fake_data)
        loss_g = criterion(output_fake, label_real)
        loss_g.backward()
        opt_g.step()

print(f"Training finished in {time.time() - start_train:.2f}s")

# 4. Generate Synthetic Data & Measure GPU Efficiency
print("Generating synthetic data (GPU)...")
start_gen = time.time()
n_generated = 5000
with torch.no_grad():
    noise = torch.randn(n_generated, 10).to(device)
    generated_data = generator(noise).cpu().numpy()
end_gen = time.time()

# Calculate GPU Throughput
gen_time = end_gen - start_gen
df_synth = pd.DataFrame(generated_data, columns=['iat', 'size', 'label'])
df_synth['iat'] = df_synth['iat'].abs()
df_synth['size'] = df_synth['size'].abs()
df_synth['label'] = (df_synth['label'] > 0.5).astype(int)

# Dynamic Throughput Calculation
avg_packet_size_bits = df_synth['size'].mean() * 8
gpu_throughput_mbps = (n_generated * avg_packet_size_bits) / (gen_time * 1e6)
print(f"GPU Throughput: {gpu_throughput_mbps:.2f} Mbps")

df_synth.to_csv(SYNTH_DATA_FILE, index=False)
print(f"Saved {SYNTH_DATA_FILE}")

# 5. Measure CPU Baseline Efficiency
print("Measuring CPU Baseline...")
device_cpu = torch.device('cpu')
generator_cpu = Generator().to(device_cpu)
generator_cpu.load_state_dict(generator.state_dict()) # Load trained weights

start_cpu = time.time()
with torch.no_grad():
    noise_cpu = torch.randn(n_generated, 10).to(device_cpu)
    _ = generator_cpu(noise_cpu)
end_cpu = time.time()

cpu_gen_time = end_cpu - start_cpu
cpu_throughput_mbps = (n_generated * avg_packet_size_bits) / (cpu_gen_time * 1e6)
print(f"CPU Throughput: {cpu_throughput_mbps:.2f} Mbps")

# 6. Calculate Utility Metrics (TSTR)
print("Calculating Utility Metrics (TSTR)...")

# Split Real Data into Train/Test
X_real = data_df[['iat', 'size']]
y_real = data_df['label']
X_real_train, X_real_test, y_real_train, y_real_test = train_test_split(X_real, y_real, test_size=0.3, random_state=42)

# Baseline: Train on Real, Test on Real
clf_real = RandomForestClassifier(n_estimators=100, random_state=42)
clf_real.fit(X_real_train, y_real_train)
y_pred_real = clf_real.predict(X_real_test)

metrics_real = {
    'Accuracy': accuracy_score(y_real_test, y_pred_real),
    'Precision': precision_score(y_real_test, y_pred_real),
    'Recall': recall_score(y_real_test, y_pred_real),
    'F1-Score': f1_score(y_real_test, y_pred_real)
}

# TSTR: Train on Synthetic, Test on Real
X_syn = df_synth[['iat', 'size']]
y_syn = df_synth['label']

clf_syn = RandomForestClassifier(n_estimators=100, random_state=42)
clf_syn.fit(X_syn, y_syn)
y_pred_syn = clf_syn.predict(X_real_test)

metrics_syn = {
    'Accuracy': accuracy_score(y_real_test, y_pred_syn),
    'Precision': precision_score(y_real_test, y_pred_syn),
    'Recall': recall_score(y_real_test, y_pred_syn),
    'F1-Score': f1_score(y_real_test, y_pred_syn)
}

# Save Metrics
metrics = {
    'utility': {
        'real': metrics_real,
        'synthetic': metrics_syn
    },
    'efficiency': {
        'gpu_throughput_mbps': gpu_throughput_mbps,
        'cpu_throughput_mbps': cpu_throughput_mbps
    }
}

with open(METRICS_FILE, 'w') as f:
    json.dump(metrics, f, indent=4)

print(f"Saved metrics to {METRICS_FILE}")

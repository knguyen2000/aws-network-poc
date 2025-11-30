import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
import os

# Configuration
REAL_DATA_FILE = 'real_traffic.csv'
SYNTH_DATA_FILE = 'synthetic_traffic.csv'
MODEL_FILE = 'gan_model.pth'
EPOCHS = 500
BATCH_SIZE = 64
LR = 0.001
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

print(f"Using device: {device}")

# 1. Generate Dummy "Real" Data (if not exists)
# Simulating a mix of small packets (ACKs) and large packets (Data)
def create_real_data(n_samples=5000):
    print("Generating dummy 'real' traffic data...")
    # Packet Sizes: Bimodal (64 bytes and 1500 bytes) with some noise
    sizes_small = np.random.normal(64, 5, int(n_samples * 0.4))
    sizes_large = np.random.normal(1500, 20, int(n_samples * 0.6))
    packet_sizes = np.concatenate([sizes_small, sizes_large])
    
    # Inter-arrival Times: Exponential distribution
    iat = np.random.exponential(scale=1.5, size=n_samples)
    
    df = pd.DataFrame({'iat': iat, 'size': packet_sizes})
    df = df.sample(frac=1).reset_index(drop=True) # Shuffle
    df.to_csv(REAL_DATA_FILE, index=False)
    print(f"Saved {REAL_DATA_FILE}")
    return df

if not os.path.exists(REAL_DATA_FILE):
    data_df = create_real_data()
else:
    data_df = pd.read_csv(REAL_DATA_FILE)

# Prepare Data Loader
data_tensor = torch.tensor(data_df.values, dtype=torch.float32).to(device)
dataset = torch.utils.data.TensorDataset(data_tensor)
dataloader = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

# 2. Define GAN Models
class Generator(nn.Module):
    def __init__(self, input_dim=10, output_dim=2):
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
    def __init__(self, input_dim=2):
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
for epoch in range(EPOCHS):
    for real_data, in dataloader:
        batch_size = real_data.size(0)
        
        # --- Train Discriminator ---
        opt_d.zero_grad()
        # Real
        label_real = torch.ones(batch_size, 1).to(device)
        output_real = discriminator(real_data)
        loss_real = criterion(output_real, label_real)
        
        # Fake
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
        loss_g = criterion(output_fake, label_real) # Trick discriminator
        loss_g.backward()
        opt_g.step()
        
    if epoch % 100 == 0:
        print(f"Epoch {epoch}/{EPOCHS} | Loss D: {loss_d.item():.4f} | Loss G: {loss_g.item():.4f}")

# 4. Generate and Save Synthetic Data
print("Generating synthetic data...")
with torch.no_grad():
    noise = torch.randn(5000, 10).to(device)
    generated_data = generator(noise).cpu().numpy()

df_synth = pd.DataFrame(generated_data, columns=['iat', 'size'])
# Post-processing: Ensure positive values
df_synth['iat'] = df_synth['iat'].abs()
df_synth['size'] = df_synth['size'].abs()

df_synth.to_csv(SYNTH_DATA_FILE, index=False)
print(f"Saved {SYNTH_DATA_FILE}")

# Save Model
torch.save(generator.state_dict(), MODEL_FILE)
print("Training complete.")

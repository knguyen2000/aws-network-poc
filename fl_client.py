import torch
import torch.optim as optim
import xmlrpc.client
import pickle
import base64
import time
import sys
import pandas as pd
from cpt_model import CPTGPT, CPTTokenizer
from cellular_sim import generate_dataset, MESSAGES

# Config
SERVER_URL = 'http://192.168.1.10:8000' # Will be updated by deploy script
CLIENT_ID = 'client_1'
EPOCHS_PER_ROUND = 2
BATCH_SIZE = 32

def train_epoch(model, data, optimizer, tokenizer):
    model.train()
    total_loss = 0
    
    # Simple data loader
    # Data is list of message strings. We need to tokenize them.
    # For GPT, input is sequence, target is shifted sequence.
    
    # Flatten data into one long sequence of tokens
    full_text = []
    for msg in data:
        full_text.append(msg)
        
    # Encode
    ids = tokenizer.encode(full_text)
    data_tensor = torch.tensor(ids, dtype=torch.long)
    
    # Create batches
    block_size = 64
    if len(data_tensor) <= block_size:
        return 0 # Not enough data
        
    for i in range(0, len(data_tensor) - block_size, BATCH_SIZE):
        # Get batch
        xb = []
        yb = []
        for j in range(BATCH_SIZE):
            if i+j+block_size >= len(data_tensor): break
            chunk = data_tensor[i+j : i+j+block_size]
            target = data_tensor[i+j+1 : i+j+block_size+1]
            xb.append(chunk)
            yb.append(target)
            
        if not xb: break
        
        x = torch.stack(xb)
        y = torch.stack(yb)
        
        if torch.cuda.is_available():
            x, y = x.cuda(), y.cuda()
            
        optimizer.zero_grad()
        logits, loss = model(x, y)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        
    return total_loss

def run_client():
    print(f"Starting Client {CLIENT_ID}...")
    
    # 1. Generate Local Data
    filename = f"local_data_{CLIENT_ID}.csv"
    generate_dataset(num_ues=50, max_events=2000, output_file=filename)
    df = pd.read_csv(filename)
    messages = df['Message'].tolist()
    print(f"Generated {len(messages)} local samples.")
    
    # 2. Setup Model
    tokenizer = CPTTokenizer(MESSAGES)
    model = CPTGPT(tokenizer.vocab_size)
    if torch.cuda.is_available():
        model.cuda()
    optimizer = optim.AdamW(model.parameters(), lr=1e-3)
    
    # 3. Connect to Server
    server = xmlrpc.client.ServerProxy(SERVER_URL)
    
    round_num = 0
    while True:
        print(f"\n--- Round {round_num} ---")
        
        # Pull Global Weights
        try:
            print("Fetching global weights...")
            encoded = server.get_global_weights()
            data = base64.b64decode(encoded)
            state_dict = pickle.loads(data)
            model.load_state_dict(state_dict)
        except Exception as e:
            print(f"Error fetching weights: {e}")
            time.sleep(5)
            continue
            
        # Train Local
        print("Training locally...")
        for epoch in range(EPOCHS_PER_ROUND):
            loss = train_epoch(model, messages, optimizer, tokenizer)
            print(f"  Epoch {epoch}: Loss {loss:.4f}")
            
        # Push Update
        print("Uploading update...")
        state_dict = model.state_dict()
        # CPU for serialization
        for k in state_dict:
            state_dict[k] = state_dict[k].cpu()
            
        data = pickle.dumps(state_dict)
        encoded = base64.b64encode(data).decode('utf-8')
        
        status = server.submit_update(CLIENT_ID, encoded, len(messages))
        print(f"Status: {status}")
        
        if status == "AGGREGATED":
            round_num += 1
        
        time.sleep(2) # Wait a bit
        
        # Periodically evaluate (e.g., every 5 rounds)
        if round_num > 0 and round_num % 5 == 0:
            print("Generating synthetic samples for evaluation...")
            # Generate 100 sequences
            model.eval()
            gen_events = []
            
            # Start with random tokens
            for i in range(50):
                # Context: Start with IDLE equivalent or random
                # For simplicity, just sample unconditional
                context = torch.zeros((1, 1), dtype=torch.long, device='cuda' if torch.cuda.is_available() else 'cpu')
                generated = model.generate(context, max_new_tokens=20)
                
                # Decode
                tokens = generated[0].tolist()
                msgs = tokenizer.decode(tokens)
                
                # Create CSV rows (Mock timestamps for now as model doesn't predict them)
                t = 0.0
                for m in msgs:
                    gen_events.append([t, f"UE_GEN_{i}", m])
                    t += 0.1
            
            # Save
            gen_file = f"gen_data_{CLIENT_ID}_round{round_num}.csv"
            with open(gen_file, "w", newline="") as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "UE_ID", "Message"])
                writer.writerows(gen_events)
            
            print(f"Saved {gen_file}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        CLIENT_ID = sys.argv[1]
    if len(sys.argv) > 2:
        SERVER_URL = sys.argv[2]
        
    run_client()

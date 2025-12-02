import torch
import copy
from xmlrpc.server import SimpleXMLRPCServer
import threading
import time
import pickle
import base64
from cpt_model import CPTGPT, CPTTokenizer
from cellular_sim import MESSAGES

# Config
HOST = '0.0.0.0'
PORT = 8000
MIN_CLIENTS = 2
ROUNDS = 5

class FederatedServer:
    def __init__(self):
        # Initialize Global Model
        tokenizer = CPTTokenizer(MESSAGES)
        self.global_model = CPTGPT(tokenizer.vocab_size)
        self.lock = threading.Lock()
        self.client_updates = []
        self.round = 0
        
        print(f"Federated Server initialized. Vocab size: {tokenizer.vocab_size}")

    def get_global_weights(self):
        """Returns base64 encoded pickled state_dict of global model"""
        with self.lock:
            state_dict = self.global_model.state_dict()
            # Serialize
            data = pickle.dumps(state_dict)
            return base64.b64encode(data).decode('utf-8')

    def submit_update(self, client_id, encoded_weights, num_samples):
        """Receives local update from a client"""
        print(f"Received update from {client_id} ({num_samples} samples)")
        
        # Decode
        data = base64.b64decode(encoded_weights)
        state_dict = pickle.loads(data)
        
        with self.lock:
            self.client_updates.append({
                'id': client_id,
                'weights': state_dict,
                'samples': num_samples
            })
            
            # Check if we have enough updates to aggregate
            if len(self.client_updates) >= MIN_CLIENTS:
                self.aggregate()
                return "AGGREGATED"
            else:
                return "WAITING"

    def aggregate(self):
        """FedAvg: Average the weights"""
        print(f"\n--- Aggregating Round {self.round} ---")
        
        total_samples = sum(c['samples'] for c in self.client_updates)
        
        # Start with zero weights
        avg_weights = copy.deepcopy(self.client_updates[0]['weights'])
        for key in avg_weights.keys():
            avg_weights[key] = torch.zeros_like(avg_weights[key], dtype=torch.float)
            
        # Weighted Average
        for client in self.client_updates:
            weight = client['samples'] / total_samples
            for key in avg_weights.keys():
                avg_weights[key] += client['weights'][key] * weight
                
        # Update Global Model
        self.global_model.load_state_dict(avg_weights)
        
        # Reset
        self.client_updates = []
        self.round += 1
        print(f"Round {self.round} complete. Global model updated.")

def start_server():
    server = SimpleXMLRPCServer((HOST, PORT), allow_none=True)
    fed_server = FederatedServer()
    
    server.register_instance(fed_server)
    print(f"Listening on {HOST}:{PORT}...")
    server.serve_forever()

if __name__ == "__main__":
    start_server()

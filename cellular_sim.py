import random
import time
import csv
import os

# 3GPP Control Plane Messages (Simplified Vocabulary)
MESSAGES = [
    "RRC_CONNECTION_REQUEST",
    "RRC_CONNECTION_SETUP",
    "RRC_CONNECTION_SETUP_COMPLETE",
    "ATTACH_REQUEST",
    "AUTH_REQUEST",
    "AUTH_RESPONSE",
    "SEC_MODE_COMMAND",
    "SEC_MODE_COMPLETE",
    "ATTACH_ACCEPT",
    "ATTACH_COMPLETE",
    "SERVICE_REQUEST",
    "DATA_TRANSFER_UPLINK",
    "DATA_TRANSFER_DOWNLINK",
    "RRC_CONNECTION_RELEASE",
    "DETACH_REQUEST",
    "DETACH_ACCEPT"
]

class UEStateMachine:
    def __init__(self, ue_id):
        self.ue_id = ue_id
        self.state = "IDLE"
        self.history = []

    def transition(self):
        """Generates the next valid message based on current state."""
        msg = None
        
        if self.state == "IDLE":
            # Start connection
            msg = "RRC_CONNECTION_REQUEST"
            self.state = "RRC_WAIT"
            
        elif self.state == "RRC_WAIT":
            msg = "RRC_CONNECTION_SETUP"
            self.state = "RRC_SETUP"
            
        elif self.state == "RRC_SETUP":
            msg = "RRC_CONNECTION_SETUP_COMPLETE"
            self.state = "ATTACH_START"
            
        elif self.state == "ATTACH_START":
            msg = "ATTACH_REQUEST"
            self.state = "AUTH_WAIT"
            
        elif self.state == "AUTH_WAIT":
            msg = "AUTH_REQUEST"
            self.state = "AUTH_RESP"
            
        elif self.state == "AUTH_RESP":
            msg = "AUTH_RESPONSE"
            self.state = "SEC_WAIT"
            
        elif self.state == "SEC_WAIT":
            msg = "SEC_MODE_COMMAND"
            self.state = "SEC_COMP"
            
        elif self.state == "SEC_COMP":
            msg = "SEC_MODE_COMPLETE"
            self.state = "ATTACH_ACC_WAIT"
            
        elif self.state == "ATTACH_ACC_WAIT":
            msg = "ATTACH_ACCEPT"
            self.state = "ATTACH_COMP"
            
        elif self.state == "ATTACH_COMP":
            msg = "ATTACH_COMPLETE"
            self.state = "CONNECTED"
            
        elif self.state == "CONNECTED":
            # Randomly do data transfer or release
            choice = random.random()
            if choice < 0.8:
                msg = random.choice(["DATA_TRANSFER_UPLINK", "DATA_TRANSFER_DOWNLINK"])
            else:
                msg = "DETACH_REQUEST"
                self.state = "DETACH_WAIT"
                
        elif self.state == "DETACH_WAIT":
            msg = "DETACH_ACCEPT"
            self.state = "IDLE" # Loop back
            
        if msg:
            self.history.append(msg)
            
        return msg

def generate_dataset(num_ues=100, max_events=5000, output_file="cellular_data.csv"):
    print(f"Generating {max_events} events for {num_ues} UEs...")
    
    ues = [UEStateMachine(i) for i in range(num_ues)]
    events = []
    
    timestamp = 1000.0
    
    for _ in range(max_events):
        # Pick a random UE
        ue = random.choice(ues)
        msg = ue.transition()
        
        if msg:
            # Add some random time delay
            timestamp += random.uniform(0.01, 0.5)
            events.append([f"{timestamp:.3f}", f"UE_{ue.ue_id}", msg])
            
    # Save to CSV
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "UE_ID", "Message"])
        writer.writerows(events)
        
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    generate_dataset()

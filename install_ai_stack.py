import os
import configparser
import sys
import time

# Fix for Windows: fablib expects HOME to be set
if os.name == 'nt' and 'HOME' not in os.environ:
    os.environ['HOME'] = os.environ.get('USERPROFILE', 'c:\\')

# Manually load fabric_rc into environment variables
rc_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabric_rc')
if os.path.exists(rc_file):
    config = configparser.ConfigParser()
    config.read(rc_file)
    if 'DEFAULT' in config:
        for key, value in config['DEFAULT'].items():
            os.environ[key.upper()] = value

try:
    from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager
    fablib = fablib_manager()
    
    SLICE_NAME = 'ai-traffic-synth'
    slice = fablib.get_slice(name=SLICE_NAME)
    generator = slice.get_node('generator')
    
    print("Setting up AI Stack on 'generator' node...")
    print("This will take 5-10 minutes. Please be patient.")

    # 1. Install NVIDIA Drivers (Headless)
    print("\n1. Installing NVIDIA Drivers...")
    # Add NVIDIA repo
    commands = [
        'sudo apt-get update',
        'sudo apt-get install -y ubuntu-drivers-common',
        'sudo ubuntu-drivers autoinstall',
        # Install basic tools
        'sudo apt-get install -y python3-pip tcpreplay tcpdump git'
    ]
    
    for cmd in commands:
        print(f"Running: {cmd}")
        generator.execute(cmd)

    # 2. Install PyTorch (CPU version first to test, CUDA version needs reboot usually)
    # We will install the full CUDA version.
    print("\n2. Installing PyTorch (with CUDA support)...")
    generator.execute('pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118')

    # 3. Check if reboot is needed
    print("\n3. Checking Driver Status...")
    try:
        stdout, stderr = generator.execute('nvidia-smi')
        print(stdout)
    except:
        print("nvidia-smi failed. A reboot is likely required to load the new drivers.")
        print("Rebooting node...")
        generator.execute('sudo reboot', quiet=True) # This command will fail/disconnect
        
        print("Waiting for node to come back online (rebooting)...")
        time.sleep(60)
        slice.wait_ssh()
        
        print("Verifying nvidia-smi after reboot...")
        stdout, stderr = generator.execute('nvidia-smi')
        print(stdout)

    print("\nAI Stack Setup Complete!")

except Exception as e:
    print(f"Error: {e}")

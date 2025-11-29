import os
import configparser
import sys
import ipaddress

# Fix for Windows: fablib expects HOME to be set
if os.name == 'nt' and 'HOME' not in os.environ:
    os.environ['HOME'] = os.environ.get('USERPROFILE', 'c:\\')

# Manually load fabric_rc into environment variables
# This bypasses issues where fablib fails to find/parse the rc file
rc_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabric_rc')
if os.path.exists(rc_file):
    config = configparser.ConfigParser()
    config.read(rc_file)
    if 'DEFAULT' in config:
        for key, value in config['DEFAULT'].items():
            # configparser keys are lowercase, convert to UPPER for env vars
            os.environ[key.upper()] = value

from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager

def deploy():
    try:
        fablib = fablib_manager()
        
        # Configuration
        SLICE_NAME = 'ai-traffic-synth'
        # We need a site with Tesla T4 GPUs.
        # instead of hardcoding, we ask fablib to find one for us
        print("Finding a site with available Tesla T4 GPUs...")
        site = fablib.get_random_site(filter_function=lambda s: s.get_component_available('GPU_TeslaT4') > 0)
        print(f"Selected site: {site}")

        # Check if slice exists and delete it to avoid "Slice already exists" error
        try:
            existing_slice = fablib.get_slice(name=SLICE_NAME)
            print(f"Slice '{SLICE_NAME}' already exists. Deleting it...")
            existing_slice.delete()
            
            # Wait for deletion to complete
            import time
            for i in range(10):
                try:
                    fablib.get_slice(name=SLICE_NAME)
                    print(f"Waiting for slice deletion... ({i+1}/10)")
                    time.sleep(10)
                except:
                    print("Slice deleted successfully.")
                    break
        except:
            pass # Slice does not exist

        print(f"Creating slice '{SLICE_NAME}'...")
        slice = fablib.new_slice(name=SLICE_NAME)

        # ---------------------------------------------------------
        # 1. Add Nodes (Generator/AI & Detector)
        # ---------------------------------------------------------
        image = 'default_ubuntu_22'
        
        # Node A: The AI Generator (Needs GPU)
        print("Adding GPU Node (Generator)...")
        generator = slice.add_node(name='generator', site=site, image=image)
        generator.set_capacities(cores=2, ram=8) # Max 8GB allowed by policy
        generator.add_component(model='GPU_TeslaT4', name='gpu1')
        
        # Node B: The Detector (Standard CPU)
        print("Adding CPU Node (Detector)...")
        detector = slice.add_node(name='detector', site=site, image=image)
        detector.set_capacities(cores=2, ram=8)

        # ---------------------------------------------------------
        # 2. Add Network (L2 Bridge)
        # ---------------------------------------------------------
        # We need interfaces on both nodes to connect them
        gen_iface = generator.add_component(model='NIC_Basic', name='nic1').get_interfaces()[0]
        det_iface = detector.add_component(model='NIC_Basic', name='nic1').get_interfaces()[0]

        # Create the L2 network connecting them
        slice.add_l2network(name='net_a', interfaces=[gen_iface, det_iface])

        # ---------------------------------------------------------
        # 3. Submit Slice
        # ---------------------------------------------------------
        print("Submitting slice... this may take a few minutes.")
        slice.submit()
        print("Slice active!")

        # ---------------------------------------------------------
        # 4. Configure Network (IPs)
        # ---------------------------------------------------------
        # Reload slice to get latest state
        slice = fablib.get_slice(name=SLICE_NAME)
        generator = slice.get_node('generator')
        detector = slice.get_node('detector')
        
        # Network config
        subnet = ipaddress.IPv4Network("192.168.1.0/24")
        gen_ip = ipaddress.IPv4Address("192.168.1.10")
        det_ip = ipaddress.IPv4Address("192.168.1.11")

        gen_iface = generator.get_interface(network_name='net_a')
        gen_iface.ip_addr_add(addr=gen_ip, subnet=subnet)
        gen_iface.ip_link_up()

        det_iface = detector.get_interface(network_name='net_a')
        det_iface.ip_addr_add(addr=det_ip, subnet=subnet)
        det_iface.ip_link_up()

        # ---------------------------------------------------------
        # 5. Install Software (Drivers & Tools)
        # ---------------------------------------------------------
        print("Installing software...")
        # Wait for SSH to be ready on all nodes
        slice.wait_ssh()
        
        # Install basic tools on both
        for node in [generator, detector]:
            node.execute('sudo apt-get update && sudo apt-get install -y iperf3 python3-pip', quiet=False)

        # Install GPU Drivers on Generator (This can take time, usually pre-installed on some images but good to check)
        # For now, we just check if the card is visible. Installing full CUDA drivers takes ~10 mins, 
        # so we'll skip the full install in this quick script and just verify the hardware exists.
        
        print("\nDeployment Successful!")
        print("To access nodes:")
        print(f"  ssh -i <slice_key> ubuntu@{generator.get_management_ip()}")
        print(f"  ssh -i <slice_key> ubuntu@{detector.get_management_ip()}")

        # ---------------------------------------------------------
        # 6. Automated Verification
        # ---------------------------------------------------------
        print("\nRunning Automated Verification...")
        
        # Ping Test
        print("1. Ping Test (Generator -> Detector)")
        try:
            stdout, stderr = generator.execute('ping -c 4 192.168.1.11')
            print(stdout)
        except Exception as e:
            print(f"Ping failed: {e}")

        # GPU Verification
        print("2. GPU Verification (Generator)")
        try:
            # lspci should show the NVIDIA controller
            stdout, stderr = generator.execute('lspci | grep -i nvidia')
            print("PCI Device Found:")
            print(stdout)
            
            # Check if nvidia-smi works (might fail if drivers aren't loaded yet, but that's okay for step 1)
            stdout, stderr = generator.execute('nvidia-smi')
            print("NVIDIA-SMI Output:")
            print(stdout)
        except Exception as e:
            print(f"GPU check failed (Drivers might need install): {e}")

        print("\nVerification Complete!")

    except Exception as e:
        print(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    deploy()

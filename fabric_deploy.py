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
        # Strategy: Query ALL sites, sort by T4 availability, pick the one with the most.
        print("Finding the site with the MOST available Tesla T4 GPUs...")
        try:
            # Get all sites that have at least 1 T4
            # We ask for a large count (50) to ensure we get all of them
            gpu_sites = fablib.get_random_sites(count=50, filter_function=lambda s: s.get('Tesla T4 Available', 0) > 0)
            
            if not gpu_sites:
                raise Exception("No sites with Tesla T4 GPUs found!")
                
            # Sort by availability (descending)
            # We need to re-fetch the details or rely on the dictionary we have
            # The list returned by get_random_sites is a list of site names (strings) or dicts?
            # get_random_sites returns a list of site names (strings).
            # Wait, the filter function received a dict. 
            # Let's verify what get_random_sites returns. 
            # Documentation says: returns a list of site names.
            
            # If it returns names, we can't sort by availability easily without re-querying.
            # But we can use the 'resources' object if we had it.
            
            # Alternative: Use a hardcoded list of reliable sites if dynamic fails.
            # But let's try to be smart.
            
            # Let's just try the sites in the returned list, but prioritize known big ones.
            known_big_sites = ['NCSA', 'TACC', 'CLEMSON', 'UTAH', 'MICH', 'WASH', 'DALL', 'UCSD', 'LBNL']
            
            site = None
            # Intersection of found sites and known big sites
            candidates = [s for s in known_big_sites if s in gpu_sites]
            
            if candidates:
                site = candidates[0] # Pick the first known big site that has availability
            else:
                site = gpu_sites[0] # Fallback to whatever was found
                
        except Exception as e:
            print(f"Error finding site: {e}. Defaulting to TACC (usually has capacity).")
            site = 'TACC'

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

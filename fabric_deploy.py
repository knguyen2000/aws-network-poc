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
        
        # ---------------------------------------------------------
        # Site Selection Strategy (Robust Retry)
        # ---------------------------------------------------------
        print("Finding sites with Tesla T4 GPUs...")
        try:
            # Get all sites that have at least 1 T4
            gpu_sites = fablib.get_random_sites(count=50, filter_function=lambda s: s.get('Tesla T4 Available', 0) > 0)
            if not gpu_sites:
                raise Exception("No sites with Tesla T4 GPUs found!")
        except Exception as e:
            print(f"Error querying sites: {e}. Defaulting to known list.")
            gpu_sites = []

        # Prioritize known big sites, then append the rest
        known_big_sites = ['NCSA', 'TACC', 'CLEMSON', 'UTAH', 'MICH', 'WASH', 'DALL', 'UCSD', 'LBNL']
        
        # Create a prioritized list of candidates
        candidates = []
        # 1. Known sites that reported having GPUs
        candidates.extend([s for s in known_big_sites if s in gpu_sites])
        # 2. Other sites that reported having GPUs
        candidates.extend([s for s in gpu_sites if s not in known_big_sites])
        # 3. Fallback: Known sites even if query failed (maybe data was stale)
        candidates.extend([s for s in known_big_sites if s not in candidates])
        
        # Remove duplicates and None
        candidates = list(dict.fromkeys([c for c in candidates if c]))
        
        print(f"Candidate Sites (in order): {candidates}")

        # ---------------------------------------------------------
        # Deployment Loop
        # ---------------------------------------------------------
        slice = None
        for site in candidates:
            print(f"\n--- Attempting deployment at {site} ---")
            try:
                # Cleanup existing slice if needed
                try:
                    existing = fablib.get_slice(name=SLICE_NAME)
                    print(f"Deleting existing slice '{SLICE_NAME}'...")
                    existing.delete()
                    # Wait for deletion
                    import time
                    for i in range(10):
                        try:
                            fablib.get_slice(name=SLICE_NAME)
                            time.sleep(5)
                        except:
                            break
                except:
                    pass

                print(f"Creating slice '{SLICE_NAME}' at {site}...")
                slice = fablib.new_slice(name=SLICE_NAME)

                # 1. Add Nodes
                image = 'default_ubuntu_22'
                
                # Node A: Generator (GPU)
                print("Adding GPU Node...")
                generator = slice.add_node(name='generator', site=site, image=image)
                generator.set_capacities(cores=2, ram=8)
                generator.add_component(model='GPU_TeslaT4', name='gpu1')
                
                # Node B: Detector (CPU)
                print("Adding CPU Node...")
                detector = slice.add_node(name='detector', site=site, image=image)
                detector.set_capacities(cores=2, ram=8)

                # 2. Add Network
                gen_iface = generator.add_component(model='NIC_Basic', name='nic1').get_interfaces()[0]
                det_iface = detector.add_component(model='NIC_Basic', name='nic1').get_interfaces()[0]
                slice.add_l2network(name='net_a', interfaces=[gen_iface, det_iface])

                # 3. Submit
                print("Submitting slice...")
                slice.submit()
                print(f"SUCCESS! Slice active at {site}.")
                break # Exit loop on success

            except Exception as e:
                print(f"FAILED at {site}: {e}")
                print("Cleaning up and trying next site...")
                try:
                    if slice: slice.delete()
                except:
                    pass
        
        if not slice or slice.get_state() not in ['Stable', 'StableOK']:
            print(f"\nCRITICAL: All deployment attempts failed. Final State: {slice.get_state() if slice else 'None'}")
            sys.exit(1)

        # ---------------------------------------------------------
        # 4. Configure Network (IPs)
        # ---------------------------------------------------------
        # Reload slice to get latest state and ensure node objects are valid
        print("Reloading slice to get active node handles...")
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

        # Install GPU Drivers on Generator
        print("\nInstalling NVIDIA Drivers on Generator (this takes ~5-10 mins)...")
        try:
            # Check if drivers are already loaded
            generator.execute('nvidia-smi')
            print("Drivers already installed.")
        except:
            print("Drivers not found. Installing...")
            # Add NVIDIA repo and install
            commands = [
                'sudo apt-get update',
                'sudo apt-get install -y ubuntu-drivers-common',
                'sudo ubuntu-drivers autoinstall',
                'sudo apt-get install -y tcpreplay tcpdump git'
            ]
            for cmd in commands:
                generator.execute(cmd)
            
            # Reboot to load drivers
            print("Rebooting generator node to load drivers...")
            try:
                generator.execute('sudo reboot', quiet=True)
            except:
                pass # Expected disconnection
            
            print("Waiting for node to come back online...")
            time.sleep(60) # Give it a minute to shut down
            slice.wait_ssh() # Wait for SSH to be available again
            
            # Verify drivers
            print("Verifying drivers after reboot...")
            generator.execute('nvidia-smi')

        # Install PyTorch
        print("\nInstalling PyTorch (with CUDA support)...")
        generator.execute('pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118')
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

        # ---------------------------------------------------------
        # 7. Generate Research Artifacts (Remote Execution)
        # ---------------------------------------------------------
        print("\nGenerating Research Artifacts on Generator Node...")
        try:
            # 1. Install Dependencies
            print("Installing Data Science stack (pandas, scipy, matplotlib, scikit-learn)...")
            generator.execute('pip3 install pandas scipy matplotlib scikit-learn', quiet=False)
            
            # 2. Upload Scripts
            print("Uploading scripts (GAN & Artifact Gen)...")
            generator.upload_file('simple_gan.py', 'simple_gan.py')
            generator.upload_file('generate_artifacts.py', 'generate_artifacts.py')
            
            # 3. Train GAN
            print("Training GAN Model...")
            generator.execute('python3 simple_gan.py', quiet=False)
            
            # 4. Generate Artifacts (using the data from simple_gan.py)
            print("Generating plots from GAN output...")
            generator.execute('python3 generate_artifacts.py', quiet=False)
            
            # 5. Download Artifacts
            print("Downloading artifacts to local runner...")
            # Create local directory if not exists
            if not os.path.exists('artifacts'):
                os.makedirs('artifacts')
            
            # List of expected files
            files = ['fidelity_cdf.png', 'utility_table.png', 'efficiency_throughput.png']
            for f in files:
                remote_path = f'artifacts/{f}'
                local_path = f'artifacts/{f}'
                try:
                    generator.download_file(local_path, remote_path)
                    print(f"  Downloaded {f}")
                except Exception as e:
                    print(f"  Failed to download {f}: {e}")
                    
        except Exception as e:
            print(f"Artifact generation failed: {e}")

    except Exception as e:
        print(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    deploy()

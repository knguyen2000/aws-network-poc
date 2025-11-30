import os
import configparser
import sys
import ipaddress
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

from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager

def deploy():
    try:
        fablib = fablib_manager()
        SLICE_NAME = 'ai-traffic-synth'
        
        # ---------------------------------------------------------
        # Site Selection
        # ---------------------------------------------------------
        print("Finding sites with Tesla T4 GPUs...")
        try:
            gpu_sites = fablib.get_random_sites(count=50, filter_function=lambda s: s.get('Tesla T4 Available', 0) > 0)
        except Exception as e:
            print(f"Error querying sites: {e}. Defaulting to known list.")
            gpu_sites = []

        known_big_sites = ['NCSA', 'TACC', 'CLEMSON', 'UTAH', 'MICH', 'WASH', 'DALL', 'UCSD', 'LBNL']
        candidates = []
        candidates.extend([s for s in known_big_sites if s in gpu_sites])
        candidates.extend([s for s in gpu_sites if s not in known_big_sites])
        candidates.extend([s for s in known_big_sites if s not in candidates])
        candidates = list(dict.fromkeys([c for c in candidates if c]))
        
        print(f"Candidate Sites (in order): {candidates}")

        # ---------------------------------------------------------
        # Deployment Loop
        # ---------------------------------------------------------
        slice = None
        for site in candidates:
            print(f"\n--- Attempting deployment at {site} ---")
            try:
                # Cleanup
                try:
                    existing = fablib.get_slice(name=SLICE_NAME)
                    print(f"Deleting existing slice '{SLICE_NAME}'...")
                    existing.delete()
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
                
                # Generator (GPU)
                print("Adding GPU Node...")
                generator = slice.add_node(name='generator', site=site, image=image)
                generator.set_capacities(cores=2, ram=8) # Default 10GB disk
                generator.add_component(model='GPU_TeslaT4', name='gpu1')
                
                # Detector (CPU)
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
                break 

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
        print("Reloading slice to get active node handles...")
        slice = fablib.get_slice(name=SLICE_NAME)
        generator = slice.get_node('generator')
        detector = slice.get_node('detector')
        
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
        # 5. Install Software
        # ---------------------------------------------------------
        print("Installing software...")
        slice.wait_ssh()
        
        for node in [generator, detector]:
            # Clean apt cache to save space
            node.execute('sudo apt-get clean', quiet=True)
            node.execute('sudo apt-get update && sudo apt-get install -y iperf3 python3-pip', quiet=False)

        # Install GPU Drivers
        print("\nInstalling NVIDIA Drivers on Generator...")
        try:
            generator.execute('nvidia-smi')
            print("Drivers already installed.")
        except:
            print("Drivers not found. Installing...")
            commands = [
                'sudo apt-get update',
                'sudo apt-get install -y ubuntu-drivers-common',
                'sudo ubuntu-drivers autoinstall',
                'sudo apt-get install -y tcpreplay tcpdump git',
                'sudo apt-get clean'
            ]
            for cmd in commands:
                generator.execute(cmd)
            
            print("Rebooting generator...")
            try:
                generator.execute('sudo reboot', quiet=True)
            except:
                pass
            
            print("Waiting for node to come back online...")
            time.sleep(60)
            slice.wait_ssh()
            
            print("Verifying drivers...")
            generator.execute('nvidia-smi')

        # Install PyTorch (Standard)
        print("\nInstalling PyTorch (Standard with CUDA)...")
        # Reverting to standard install but keeping --no-cache-dir
        # The minimal install caused missing shared libraries
        generator.execute('python3 -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118', quiet=False)
        
        print("Verifying PyTorch...")
        try:
            generator.execute('python3 -c "import torch; print(f\'Torch version: {torch.__version__}, CUDA: {torch.cuda.is_available()}\')"', quiet=False)
        except Exception as e:
            print(f"WARNING: PyTorch verification failed: {e}")

        print("\nDeployment Successful!")
        print(f"  ssh -i <slice_key> ubuntu@{generator.get_management_ip()}")
        print(f"  ssh -i <slice_key> ubuntu@{detector.get_management_ip()}")

        # ---------------------------------------------------------
        # 6. Verification
        # ---------------------------------------------------------
        print("\nRunning Automated Verification...")
        print("1. Ping Test")
        try:
            stdout, stderr = generator.execute('ping -c 4 192.168.1.11')
            print(stdout)
        except Exception as e:
            print(f"Ping failed: {e}")

        print("2. GPU Verification")
        try:
            stdout, stderr = generator.execute('nvidia-smi')
            print(stdout)
        except Exception as e:
            print(f"GPU check failed: {e}")

        # ---------------------------------------------------------
        # 7. Artifacts
        # ---------------------------------------------------------
        print("\nGenerating Research Artifacts...")
        try:
            print("Installing Data Science stack...")
            generator.execute('python3 -m pip install --no-cache-dir pandas scipy matplotlib scikit-learn', quiet=False)
            
            print("Uploading scripts...")
            generator.upload_file('simple_gan.py', 'simple_gan.py')
            generator.upload_file('generate_artifacts.py', 'generate_artifacts.py')
            
            print("Training GAN...")
            generator.execute('python3 simple_gan.py', quiet=False)
            
            print("Generating plots...")
            generator.execute('python3 generate_artifacts.py', quiet=False)
            
            print("Downloading artifacts...")
            if not os.path.exists('artifacts'):
                os.makedirs('artifacts')
            
            files = ['fidelity_cdf.png', 'utility_table.png', 'efficiency_throughput.png']
            for f in files:
                remote_path = f'artifacts/{f}'
                local_path = f'artifacts/{f}'
                try:
                    stdout, stderr = generator.execute(f'ls -l {remote_path} | awk "{{print \$5}}"', quiet=True)
                    size = int(stdout.strip()) if stdout.strip().isdigit() else 0
                    
                    if size > 0:
                        generator.download_file(local_path, remote_path)
                        print(f"  Downloaded {f} ({size} bytes)")
                    else:
                        print(f"  Skipping {f}: Empty or missing.")
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

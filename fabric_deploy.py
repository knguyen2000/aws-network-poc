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

        except Exception as e:
            print(f"WARNING: PyTorch verification failed: {e}")

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
            for f in files:
                remote_path = f'artifacts/{f}'
                local_path = f'artifacts/{f}'
                try:
                    # Verify file exists and has size > 0
                    stdout, stderr = generator.execute(f'ls -l {remote_path} | awk "{{print \$5}}"', quiet=True)
                    size = int(stdout.strip()) if stdout.strip().isdigit() else 0
                    
                    if size > 0:
                        generator.download_file(local_path, remote_path)
                        print(f"  Downloaded {f} ({size} bytes)")
                    else:
                        print(f"  Skipping {f}: File is empty or does not exist remotely.")
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

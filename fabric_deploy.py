import os
import configparser
import sys

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
        SLICE_NAME = 'net-perf-test'
        # We let FABRIC pick a random site with available resources, or you can specify one e.g. 'KAUST'
        # site = fablib.get_random_site() 
        # For simplicity in this script, we'll let the scheduler decide or pick a specific one if needed.
        # Here we don't specify site in add_node, so it might pick random or error if not handled. 
        # Best practice: pick a site.
        # site = fablib.get_random_site()
        site = 'NCSA'
        print(f"Selected site: {site}")

        # Check if slice exists and delete it to avoid "Slice already exists" error
        try:
            existing_slice = fablib.get_slice(name=SLICE_NAME)
            print(f"Slice '{SLICE_NAME}' already exists. Deleting it...")
            existing_slice.delete()
        except:
            pass # Slice does not exist

        print(f"Creating slice '{SLICE_NAME}'...")
        slice = fablib.new_slice(name=SLICE_NAME)

        # ---------------------------------------------------------
        # 1. Add Nodes (Server & Client)
        # ---------------------------------------------------------
        # Using Ubuntu 22.04 as a standard replacement for Amazon Linux
        image = 'default_ubuntu_22'
        
        # Server Node
        server = slice.add_node(name='server', site=site, image=image)
        server.set_capacities(cores=2, ram=4)
        
        # Client Node
        client = slice.add_node(name='client', site=site, image=image)
        client.set_capacities(cores=2, ram=4)

        # ---------------------------------------------------------
        # 2. Add Network (L2 Bridge)
        # ---------------------------------------------------------
        # We need interfaces on both nodes to connect them
        server_iface = server.add_component(model='NIC_Basic', name='nic1').get_interfaces()[0]
        client_iface = client.add_component(model='NIC_Basic', name='nic1').get_interfaces()[0]

        # Create the L2 network connecting them
        slice.add_l2network(name='net_a', interfaces=[server_iface, client_iface])

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
        server = slice.get_node('server')
        client = slice.get_node('client')

        server_iface = server.get_interface(network_name='net_a')
        server_iface.ip_addr_add(addr='192.168.1.10', subnet='255.255.255.0')
        server_iface.ip_link_up()

        client_iface = client.get_interface(network_name='net_a')
        client_iface.ip_addr_add(addr='192.168.1.11', subnet='255.255.255.0')
        client_iface.ip_link_up()

        # ---------------------------------------------------------
        # 5. Install Software (iperf3)
        # ---------------------------------------------------------
        print("Installing iperf3 on nodes...")
        for node in [server, client]:
            # Wait for SSH to be ready
            node.wait_ssh()
            # Update apt and install iperf3
            node.execute('sudo apt-get update && sudo apt-get install -y iperf3', quiet=False)

        print("\nDeployment Successful!")
        print("To access nodes:")
        print(f"  ssh -i <slice_key> ubuntu@{server.get_management_ip()}")
        print(f"  ssh -i <slice_key> ubuntu@{client.get_management_ip()}")
        print("\nVerify connectivity:")
        print("  From client: ping 192.168.1.10")
        print("  From client: iperf3 -c 192.168.1.10")

    except Exception as e:
        print(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    deploy()

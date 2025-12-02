import os
import configparser

# Fix for Windows: fablib expects HOME to be set
# MUST be done before importing fablib
if os.name == 'nt' and 'HOME' not in os.environ:
    os.environ['HOME'] = os.environ.get('USERPROFILE', 'c:\\')

# Force local token path
os.environ['FABRIC_TOKEN_LOCATION'] = r'c:\Users\khuon\aws-network-poc\fabric_token_local.json'

import time
print(f"Current Time (UTC): {time.time()}")
print(f"Current Time (Local): {time.ctime()}")

from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager

# Load RC
rc_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabric_rc')
if os.path.exists(rc_file):
    config = configparser.ConfigParser()
    config.read(rc_file)
    if 'DEFAULT' in config:
        for key, value in config['DEFAULT'].items():
            os.environ[key.upper()] = value

try:
    print("Initializing Fablib...")
    fablib = fablib_manager()
    
    print("User:", fablib.get_bastion_username())
    print("Project:", fablib.get_project_id())
    
    print("Querying Sites...")
    sites = fablib.get_sites()
    print(f"Found {len(sites)} sites.")
    for s in sites[:3]:
        print(f" - {s.get_name()}")
        
    print("Checking Slices...")
    slices = fablib.get_slices()
    print(f"Found {len(slices)} slices.")
    for s in slices:
        print(f" - {s.get_name()} ({s.get_state()})")
        
except Exception as e:
    print(f"FABRIC API Error: {e}")
    import traceback
    with open('traceback.log', 'w') as f:
        traceback.print_exc(file=f)
    traceback.print_exc()

import os
import configparser
import time

# Fix for Windows
if os.name == 'nt' and 'HOME' not in os.environ:
    os.environ['HOME'] = os.environ.get('USERPROFILE', 'c:\\')

# Force local token path
os.environ['FABRIC_TOKEN_LOCATION'] = r'c:\Users\khuon\aws-network-poc\fabric_token_local.json'

# MONKEY PATCH: Fix for Clock Skew (iat error)
try:
    import jwt
    original_decode = jwt.decode
    def patched_decode(*args, **kwargs):
        kwargs['leeway'] = 3600 
        return original_decode(*args, **kwargs)
    jwt.decode = patched_decode
    print("Monkey-patched jwt.decode.", flush=True)
except ImportError:
    pass

from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager

def simple_deploy():
    print("Initializing...", flush=True)
    fablib = fablib_manager()
    
    SITE = 'NCSA'
    SLICE_NAME = 'test-slice-simple'
    
    print(f"Creating slice {SLICE_NAME} at {SITE}...", flush=True)
    try:
        # Check existing
        try:
            s = fablib.get_slice(name=SLICE_NAME)
            print("Deleting existing...", flush=True)
            s.delete()
            time.sleep(10)
        except:
            pass
            
        slice = fablib.new_slice(name=SLICE_NAME)
        node = slice.add_node(name='server', site=SITE)
        node.set_capacities(cores=2, ram=4)
        
        print("Submitting...", flush=True)
        slice.submit()
        print("Success!", flush=True)
        
    except Exception as e:
        print(f"Failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_deploy()

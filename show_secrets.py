import os
import configparser

# Setup Environment
if os.name == 'nt' and 'HOME' not in os.environ:
    os.environ['HOME'] = os.environ.get('USERPROFILE', 'c:\\')

def print_secret(name, value):
    print(f"\n{'='*20}")
    print(f"SECRET NAME: {name}")
    print(f"{'='*20}")
    print(value)
    print(f"{'='*20}\n")

def read_file(path):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        return f"ERROR READING FILE: {e}"

rc_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabric_rc')
config = configparser.ConfigParser()
config.read(rc_file)

if 'DEFAULT' in config:
    defaults = config['DEFAULT']
    
    # Simple String Secrets
    print_secret("FABRIC_PROJECT_ID", defaults.get('FABRIC_PROJECT_ID'))
    print_secret("FABRIC_BASTION_USERNAME", defaults.get('FABRIC_BASTION_USERNAME'))
    
    # File Content Secrets
    token_path = defaults.get('FABRIC_TOKEN_LOCATION') or defaults.get('FABRIC_TOKEN_FILE')
    if token_path:
        print_secret("FABRIC_TOKEN_JSON", read_file(token_path))
        
    bastion_key_path = defaults.get('FABRIC_BASTION_KEY_LOCATION')
    if bastion_key_path:
        print_secret("FABRIC_BASTION_KEY", read_file(bastion_key_path))
        
    slice_key_path = defaults.get('FABRIC_SLICE_PRIVATE_KEY_FILE')
    if slice_key_path:
        print_secret("FABRIC_SLICE_KEY", read_file(slice_key_path))
        
    slice_pub_key_path = defaults.get('FABRIC_SLICE_PUBLIC_KEY_FILE')
    if slice_pub_key_path:
        print_secret("FABRIC_SLICE_PUB_KEY", read_file(slice_pub_key_path))

import os
import configparser

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
            print(f"Set ENV: {key.upper()} = {value}")

# Redirect stdout to a file to avoid encoding issues
import sys
sys.stdout = open('debug_log.txt', 'w', encoding='utf-8')

print(f"Current FABRIC_TOKEN_FILE: {os.environ.get('FABRIC_TOKEN_FILE')}")
token_path = os.environ.get('FABRIC_TOKEN_FILE')
print(f"Token path repr: {repr(token_path)}")

if token_path:
    # Check directory listing
    dir_name = os.path.dirname(token_path)
    print(f"Listing directory: {dir_name}")
    try:
        if os.path.exists(dir_name):
            files = os.listdir(dir_name)
            print(f"Files in {dir_name}: {files}")
            if os.path.basename(token_path) in files:
                print("  -> File IS in the directory listing!")
            else:
                print("  -> File is NOT in the directory listing.")
        else:
            print(f"  -> Directory {dir_name} does not exist.")
    except Exception as e:
        print(f"Error listing directory: {e}")

    if os.path.exists(token_path):
        print(f"Token file FOUND at {token_path}")
    else:
        print(f"Token file MISSING at {token_path}")

print("Attempting to initialize fablib...")
try:
    from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager
    fablib = fablib_manager()
    print("SUCCESS: fablib initialized!")
except Exception as e:
    print(f"FAILURE: {e}")

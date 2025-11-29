import os
import configparser

# 1. Setup Environment like the deploy script
if os.name == 'nt' and 'HOME' not in os.environ:
    os.environ['HOME'] = os.environ.get('USERPROFILE', 'c:\\')

rc_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabric_rc')
os.environ['FABRIC_RC_FILE'] = rc_file

print(f"Checking configuration...")
print(f"FABRIC_RC_FILE: {rc_file}")

# 2. Check if fabric_rc exists
if os.path.exists(rc_file):
    print(f"  [OK] fabric_rc found.")
else:
    print(f"  [FAIL] fabric_rc NOT found at {rc_file}")
    exit(1)

# 3. Parse fabric_rc manually to see what's inside
config = configparser.ConfigParser()
config.read(rc_file)

if 'DEFAULT' in config:
    print("  [OK] DEFAULT section found.")
    token_file = config['DEFAULT'].get('FABRIC_TOKEN_FILE')
    print(f"  FABRIC_TOKEN_FILE in config: '{token_file}'")
    
    if token_file:
        # 4. Check if the token file exists
        if os.path.exists(token_file):
            print(f"  [OK] Token file exists at {token_file}")
        else:
            print(f"  [FAIL] Token file does NOT exist at {token_file}")
            print("  -> Please make sure you downloaded the token and saved it to this path.")
    else:
        print("  [FAIL] FABRIC_TOKEN_FILE not set in fabric_rc")
else:
    print("  [FAIL] DEFAULT section missing in fabric_rc")

# 5. Try initializing fablib
print("\nAttempting to initialize fablib...")
try:
    from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager
    fablib = fablib_manager()
    print("  [OK] fablib initialized successfully!")
except Exception as e:
    print(f"  [FAIL] fablib initialization failed: {e}")

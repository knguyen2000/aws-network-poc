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

from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager

def teardown():
    try:
        fablib = fablib_manager()
        # Configuration
        SLICE_NAME = 'ai-traffic-synth'
        
        try:
            slice = fablib.get_slice(name=SLICE_NAME)
            print(f"Slice '{SLICE_NAME}' found. Deleting...")
            slice.delete()
            print("Done!")
        except Exception as e:
            print(f"Slice '{SLICE_NAME}' not found or error: {e}")

    except Exception as e:
        print(f"Error in teardown: {e}")

if __name__ == "__main__":
    teardown()

import os
import configparser
import sys

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

try:
    from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager
    fablib = fablib_manager()
    
    # Create a dummy slice
    slice = fablib.new_slice(name='debug-slice-inspect')
    
    print("Available methods on Slice object:")
    methods = [m for m in dir(slice) if not m.startswith('_')]
    for m in sorted(methods):
        print(f" - {m}")

except Exception as e:
    print(f"Error: {e}")

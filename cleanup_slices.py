import os
import configparser
import sys
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

try:
    from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib_manager
    fablib = fablib_manager()
    
    print("Fetching all slices...")
    slices = fablib.get_slices()
    
    if not slices:
        print("No slices found. You are clean!")
        sys.exit(0)

    print(f"Found {len(slices)} slices:")
    for slice in slices:
        print(f" - {slice.get_name()} (State: {slice.get_state()})")

    # Ask for confirmation if running interactively, otherwise just delete known test slices
    # Since we are running via automation, we will target our specific project names
    target_names = ['net-perf-test', 'ai-traffic-synth']
    
    for slice in slices:
        if slice.get_name() in target_names:
            print(f"\nDeleting slice '{slice.get_name()}'...")
            try:
                slice.delete()
                print("Delete request sent.")
            except Exception as e:
                print(f"Error deleting {slice.get_name()}: {e}")
    
    print("\nWaiting for deletion to complete...")
    # Simple wait loop
    for i in range(15):
        remaining = [s for s in fablib.get_slices() if s.get_name() in target_names]
        if not remaining:
            print("All target slices deleted successfully!")
            break
        print(f"Waiting... {len(remaining)} slices still active.")
        time.sleep(10)

except Exception as e:
    print(f"Error: {e}")

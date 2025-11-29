import os
import configparser
import logging

# Setup Environment
if os.name == 'nt' and 'HOME' not in os.environ:
    os.environ['HOME'] = os.environ.get('USERPROFILE', 'c:\\')

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
    fablib.show_config()

    print("Creating minimal slice...")
    slice = fablib.new_slice(name='test-minimal-slice')
    
    # Just add one simple node to see if it submits
    print("Adding one node...")
    node = slice.add_node(name='node1', site='NCSA', image='default_ubuntu_22')
    node.set_capacities(cores=1, ram=2)

    print("Submitting slice...")
    slice.submit()
    print("SUCCESS: Slice submitted!")
    
    print("Deleting slice...")
    slice.delete()

except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()

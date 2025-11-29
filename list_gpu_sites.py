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
    
    print("\nSites with Tesla T4 GPUs:")
    print(f"{'Site':<15} | {'T4 Available':<15} | {'T4 Total':<15}")
    print("-" * 50)
    
    # Get resources (this object contains the topology)
    # We will manually iterate instead of using list_sites() which might use pandas/threading
    resources = fablib.get_resources()
    
    for site_name, site in resources.get_topology().get_sites().items():
        try:
            # Check for Tesla T4 component
            t4_available = site.get_component_available('GPU_TeslaT4')
            t4_capacity = site.get_component_capacity('GPU_TeslaT4')
            
            if t4_capacity > 0:
                print(f"{site_name:<15} | {t4_available:<15} | {t4_capacity:<15}")
        except:
            continue
            
except Exception as e:
    print(f"Error: {e}")

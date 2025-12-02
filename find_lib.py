import fabrictestbed_extensions
import os
print(os.path.dirname(fabrictestbed_extensions.__file__))

try:
    from fabric_python_client import utils
    print(utils.__file__)
except ImportError:
    print("fabric_python_client not found directly")

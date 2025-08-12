import json
import os

def load_config(filename="config.json"):
    """Load the configuration from a JSON file located in the same directory as this script."""
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to the configuration file
    config_path = os.path.join(script_dir, filename)
    
    with open(config_path, "r") as file:
        config = json.load(file)
    return config
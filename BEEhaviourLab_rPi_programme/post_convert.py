import os
from pathlib import Path

from threads.USB_mic import convert_wav_to_flac
from threads.pi_cam import convert_h264_to_mp4

from load_config import load_config

# Convert video and audio files in post - To be used if time between
# recording segments is too short for compression to finish (need to
# comment out lines for automatic conversion on main.py)

def find_and_convert_h264_files(start_directory):
    for root, dirs, files in os.walk(start_directory):
        for file in files:
            if file.endswith(".h264"):
                full_path = Path(root) / file
                convert_h264_to_mp4(str(full_path))
                
def find_and_convert_wav_files(start_directory):
    for root, dirs, files in os.walk(start_directory):
        for file in files:
            if file.endswith(".wav"):
                full_path = Path(root) / file
                convert_wav_to_flac(str(full_path))

# Load the configuration for this Raspberry Pi
config = load_config()

# access path to ssd
start_directory = config["ssd_path"] # Name folder on SSD to save files

print("finding and converting video files...")
find_and_convert_h264_files(start_directory)

print("finding and converting audio files...")
find_and_convert_wav_files(start_directory)

print("Compression & conversions complete.")
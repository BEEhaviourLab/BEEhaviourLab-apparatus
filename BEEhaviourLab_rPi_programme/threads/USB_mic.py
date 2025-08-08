import os
import subprocess
import threading
import time
import re

def find_usb_mic():
    try:
        # Run the arecord -l command and capture its output
        result = subprocess.check_output(['arecord', '-l']).decode('utf-8')
        
        # Look for lines that describe a USB mic
        matches = re.finditer(r'card (\d+):.*?device (\d+): USB', result, re.MULTILINE)
        
        for match in matches:
            # Extract the card and device numbers
            card, device = match.groups()
            return int(card), int(device)
        
        raise ValueError("USB microphone not found.")
    except subprocess.CalledProcessError:
        raise RuntimeError("Error executing arecord command.")
    
def record_audio(Rec_time, audio_file, card, device):
    # Define command to record audio using arecord
    card_device = 'plughw:' + str(card) + ',' + str(device)
    
    arecord_command = [
        'arecord',
        '-D', card_device, # use appropriate card,device numbers
        '-c', '1', 	#mono audio - use 2 for stereo
        '-r', '90000', #sample rate
        '-f', 'S16_LE',	# Audio format
        '-d', str(Rec_time), #Recording duration in seconds
        audio_file	#output .wav file
    ]
    
    # Run the arecord command
    subprocess.run(arecord_command)

def convert_wav_to_flac(wav_file):
    
    flac_file = os.path.splitext(wav_file)[0] + '.flac'
    
    ffmpeg_aud_command = [
        'ffmpeg',
        '-i', wav_file,  # Input file
        '-vn',  # No video
        '-ar', '90000',  # Sample rate
        '-ac', '1',  # Audio channels
        '-compression_level', '8',  # Mid compression level
        '-c:a', 'flac',  # Codec audio flac
        flac_file  # Output file
    ]
    
    # Run the ffmpeg command to convert wav to flac:
    #subprocess.run(ffmpeg_command)
    #return flac_file
    
    try:
        subprocess.run(ffmpeg_aud_command, check=True)
        print(f"Converted {wav_file} to {flac_file}")
        
        # Optionally, delete the original .wav file
        os.remove(wav_file)
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to convert {wav_file} to {flac_file}: {e}")

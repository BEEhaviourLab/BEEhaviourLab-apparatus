import RPi.GPIO as GPIO
import time
from itertools import product
import threading

def time_clapper(rPi_num, BUZZER_PIN, LED_PIN, Rec_time, buzz_file):
    # GPIO setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.IN)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)
    
    timestamps = []  # list to store timestamps

    # Function to activate the LED and buzzer
    def activate_components(duration):
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        pwm = GPIO.PWM(BUZZER_PIN, 1000)
        pwm.start(30)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.output(LED_PIN, GPIO.HIGH)
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        pwm.stop()
        GPIO.setup(BUZZER_PIN, GPIO.IN)
        GPIO.output(LED_PIN, GPIO.LOW)
        

    # Generate permutations
    permutations = list(product([0, 1], repeat=5))

    # Get the specific permutation
    selected_permutation = permutations[rPi_num - 1]
    
    # Wait time before FIRST buzz
    time.sleep(5)  
    
    current_timestamp = time.time()
    timestamps.append(current_timestamp)
    
    # Control the LED and buzzer using the selected permutation
    for digit in selected_permutation:
        if digit == 0:
            activate_components(0.1)
        else:
            activate_components(0.25)
        time.sleep(0.1)
    
    current_timestamp = time.time()
    timestamps.append(current_timestamp)
    
    
    # Wait time before second buzz (10s before end of recording)
    time.sleep(Rec_time - 15) 
    
    current_timestamp = time.time()
    timestamps.append(current_timestamp)
    
    # Control the LED and buzzer using the selected permutation
    for digit in selected_permutation:
        if digit == 0:
            activate_components(0.1)
        else:
            activate_components(0.25)
        time.sleep(0.1)
    
    current_timestamp = time.time()
    timestamps.append(current_timestamp)
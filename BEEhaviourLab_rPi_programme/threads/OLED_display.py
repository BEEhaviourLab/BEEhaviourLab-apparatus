import time
import datetime
import adafruit_ssd1306
import busio
import board
import queue
import RPi.GPIO as GPIO

def OLED_wipe(Name, data_queue, i2c):
    GPIO.setmode(GPIO.BCM)
    display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
    display.fill(0)
    display.text(f"{Name}", 0, 0, 1)
    display.text(f"Ready...", 0, 12, 1)
    display.show()
    time.sleep(1)
    GPIO.cleanup()
    
def OLED(Name, data_queue, Rec_time, start_time, i2c):

    display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
    display.fill(0)
    display.show()

    try:
        while time.time() - start_time < Rec_time: 
            temp, rh = data_queue.get()
            elapsed_time_s = time.time() - start_time
            elapsed_time = datetime.timedelta(seconds=elapsed_time_s)
            hours, remainder = divmod(elapsed_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            elapsed_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            display.fill(0)
            display.text(f"{Name}", 0, 0, 1)
            display.text(f"{temp:.1f} C, {rh:.1f}% rh", 0, 12, 1)
            display.text(f"REC time: {elapsed_time_str}", 0, 24, 1)
            display.show()
            
            time.sleep(2)  # Increased sleep to 2.5 seconds for reduced update rate

        # Display the "Done!" message once after the recording time has passed
        display.fill(0)
        display.text("Done!", 0, 0, 1)
        display.text(f"Rec time: {elapsed_time_str}", 0, 24, 1)
        display.show()

    except KeyboardInterrupt:
        pass

    finally:
        display.fill(0)
        display.text(f"{Name}", 0, 0, 1)
        display.text("Recording done!", 0, 12, 1)
        display.text(f"Rec time: {elapsed_time_str}", 0, 24, 1)
        display.show()

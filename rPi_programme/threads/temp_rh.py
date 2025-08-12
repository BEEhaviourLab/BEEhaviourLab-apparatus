import time
#first time, pip install adafruit-circuitpython-dht
import adafruit_dht
import board
import json
import datetime


def DHT(DHT_file, data_queue, start_time, seg_time, Rec_time):
    #Initialize DHT22 sensor
    dht_sensor = adafruit_dht.DHT22(board.D23, use_pulseio=False) 
    last_temp = None
    last_rh = None
    data_list = []
    
    while time.time() - seg_time < Rec_time:
        try:
            #Read temp and humidity from sensor
            temp = dht_sensor.temperature
            rh = dht_sensor.humidity
            if temp is not None and rh is not None:
                last_temp = temp
                last_rh = rh
                
                print(f"Temp: {temp:.1f} °C, Humidity: {rh:.1f}%")
            
                elapsed_time = time.time() - start_time #calculate elapsed time
                timex = datetime.datetime.fromtimestamp(elapsed_time)
                formatted_time = timex.strftime('%H:%M:%S')
                #put data into the queue
                data_queue.put((temp, rh))
            
                #append data to the list
                data_point = {"time": formatted_time, "temperature": temp, "humidity": rh}
                data_list.append(data_point)
                    
            else:
                print("Failed to retrieve data from sensor.")
                
        except Exception as e:
            print("An error occurred:", str(e))
            
        # Wait for 2 seconds before reading data again
        time.sleep(2)
    
    # Save the data_list to the JSON file
    with open(DHT_file, 'w') as json_file:
        json.dump(data_list, json_file, indent=4)

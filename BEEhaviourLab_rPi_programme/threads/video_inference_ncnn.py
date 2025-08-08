import cv2
import json
import os
import numpy as np
import ncnn

def 







(video_file, day_folder, day, Name, replicate, ID, 
                      param_path='rPi_program/bee_detector/model.param',
                      bin_path='rPi_program/bee_detector/model.bin',
                      input_size=(416, 416),
                      conf_threshold=0.5,
                      skip_frames=2):
    try:
        # Load NCNN model
        net = ncnn.Net()
        net.load_param(param_path)
        net.load_model(bin_path)
        
        # Create video capture buffer
        cap = cv2.VideoCapture(video_file)
        frame_count = 0
        inference_data = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Skip frames for faster processing
            if frame_count % skip_frames != 0:
                frame_count += 1
                continue
            
            # Preprocess frame
            resized = cv2.resize(frame, input_size)
            # Convert to RGB
            img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            # Normalize to float32
            img = img.astype(np.float32) / 255.0
            
            # Create NCNN mat and run inference
            mat_in = ncnn.Mat.from_pixels_resize(
                img, 
                ncnn.Mat.PIXEL_RGB, 
                img.shape[1], 
                img.shape[0], 
                input_size[0], 
                input_size[1]
            )
            
            # Normalize
            mean_vals = [0, 0, 0]
            norm_vals = [1/255.0, 1/255.0, 1/255.0]
            mat_in.substract_mean_normalize(mean_vals, norm_vals)
            
            # Create extractor
            ex = net.create_extractor()
            ex.input("input", mat_in)
            
            # Get output
            ret, mat_out = ex.extract("output")
            
            # Process detections
            detections = []
            if ret == 0:  # Success
                for i in range(mat_out.h):
                    values = mat_out.row(i)
                    class_id = values[0]
                    confidence = values[1]
                    
                    if confidence > conf_threshold:
                        # bbox coordinates are normalized [0-1]
                        x1, y1, x2, y2 = values[2:6]
                        
                        # Convert to actual coordinates
                        original_h, original_w = frame.shape[:2]
                        x1 = int(x1 * original_w)
                        y1 = int(y1 * original_h)
                        x2 = int(x2 * original_w)
                        y2 = int(y2 * original_h)
                        
                        detections.append({
                            'bbox': [x1, y1, x2, y2],
                            'confidence': float(confidence),
                            'class_id': int(class_id)
                        })
            
            frame_data = {
                'frame': frame_count,
                'detections': detections
            }
            
            inference_data.append(frame_data)
            frame_count += skip_frames
        
        cap.release()
        
        # Save results
        inference_file = os.path.join(
            day_folder, 
            f"{day}_{Name}_{replicate}_{ID}_ncnn_results.json"
        )
        
        with open(inference_file, 'w') as f:
            json.dump(inference_data, f)
            
        print(f"NCNN inference completed for {video_file}")
        
    except Exception as e:
        print(f"Error during NCNN inference: {e}") 
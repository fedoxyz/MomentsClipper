import cv2
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import shutil
import os
import tempfile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Replace with your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def time_to_seconds(time_str):
    """ Convert time format mm:ss to total seconds """
    minutes, seconds = map(int, time_str.split(':'))
    return minutes * 60 + seconds

def clip_video(input_file, intervals, output_file):
    """ Clips the video based on given intervals and combines them.
    
    Args:
        input_file (str): Path to the input video file.
        intervals (list of tuples): List of (start_time, end_time) tuples in seconds.
        output_file (str): Path for the output video file.
    """
    cap = cv2.VideoCapture(input_file)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
    
    for start, end in intervals:
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or (cap.get(cv2.CAP_PROP_POS_MSEC) > end * 1000):
                break
            out.write(frame)
    
    cap.release()
    out.release()

def cleanup_temp_dir(temp_dir):
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(temp_dir)

@app.post("/clip-video/")
async def create_clip(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    intervals: str = Form(...)
):
    print(f"Received video: {video.filename}")
    print(f"Received intervals: {intervals}")
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Save the uploaded video to the temporary directory
        temp_video_path = os.path.join(temp_dir, video.filename)
        with open(temp_video_path, "wb") as buffer:
            content = await video.read()
            buffer.write(content)
        
        # Parse intervals
        interval_list = [tuple(map(float, interval.split('-'))) for interval in intervals.split(',')]
        
        # Create output file path
        output_file = os.path.join(temp_dir, "output.mp4")
        
        # Clip the video
        clip_video(temp_video_path, interval_list, output_file)
        
        # Add cleanup task to run after response is sent
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        # Return the clipped video as a file response
        return FileResponse(output_file, media_type="video/mp4", filename="clipped_video.mp4")
    
    except Exception as e:
        # Clean up the temporary directory in case of an error
        cleanup_temp_dir(temp_dir)
        raise e

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


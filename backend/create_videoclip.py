from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, ImageClip, vfx

import moviepy.config as conf
conf.change_settings({"FFMPEG_BINARY": "/usr/bin/ffmpeg"})

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Replace with your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clip_video(input_file, intervals, output_file, audio_file=None):
    try:
        # Load video
        video = VideoFileClip(input_file)
        clips = [video.subclip(start, end) for start, end in intervals]

        # Merge clips into one
        main_clip = concatenate_videoclips(clips)

        # Define target resolution (9:16)
        target_width = 1080
        target_height = 1920
        scale_factor = 1.1
        transition_duration = 0.5

        # Keep the blurred background as it is
        blurred_bg = main_clip.resize((1920*2, 1080*2))

        # Resize main video while maintaining aspect ratio
        main_clip = main_clip.resize(
            newsize=(int(main_clip.w * scale_factor), int(main_clip.h * scale_factor))
        ).set_position("center")

        # Load watermark
        watermark_path = "assets/watermark.png"
        watermark = None
        if os.path.exists(watermark_path):
            watermark = ImageClip(watermark_path).set_duration(main_clip.duration)
            watermark = watermark.resize(width=int(target_width * 1.0))
            watermark = watermark.set_position(("center", target_height * 0.81)).set_opacity(0.5)

        # Load outro
        outro_path = "assets/outro.mp4"
        outro = VideoFileClip(outro_path) if os.path.exists(outro_path) else None

        if outro:
            outro = outro.set_position("center").resize(width=int(target_width * 1.0))

            # Apply fade-out to **both the main clip & the blurred background**
            blurred_bg = blurred_bg.fadeout(transition_duration)
            main_clip = main_clip.fadeout(transition_duration)

            if watermark:
                watermark = watermark.fadeout(transition_duration)
            
            # Remove black background using chroma keying
            outro = outro.fx(vfx.mask_color, color=[0, 0, 0], thr=80, s=10)
            # Fade in the outro, ensuring smooth blending
            outro = outro.fadein(transition_duration).set_start(main_clip.duration - transition_duration)

        # Create final composition (single CompositeVideoClip)
        layers = [blurred_bg.set_position("center"), main_clip]
        if watermark:
            layers.append(watermark)
        if outro:
            layers.append(outro)

        final_clip = CompositeVideoClip(layers, size=(target_width, target_height))

        # Handle audio
        if audio_file:
            main_audio = AudioFileClip(audio_file).subclip(0, final_clip.duration)
            final_clip = final_clip.set_audio(main_audio)

        # Export final video
        final_clip.write_videofile(output_file, codec="libx264", audio_codec="aac", preset="ultrafast")

        # Close resources
        video.close()
        if audio_file:
            main_audio.close()
        if outro:
            outro.close()
        final_clip.close()

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        raise
    except Exception as e:
        print(f"Error in video processing: {e}")
        raise

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
    intervals: str = Form(...),
    audio: UploadFile = File(None)
):
    print(f"Received video: {video.filename}")
    print(f"Received intervals: {intervals}")
    if audio:
        print(f"Received audio: {audio.filename}")
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Save the uploaded video to the temporary directory
        temp_video_path = os.path.join(temp_dir, video.filename)
        with open(temp_video_path, "wb") as buffer:
            content = await video.read()
            buffer.write(content)
        
        # Save the uploaded audio to the temporary directory if provided
        temp_audio_path = None
        if audio:
            temp_audio_path = os.path.join(temp_dir, audio.filename)
            with open(temp_audio_path, "wb") as buffer:
                content = await audio.read()
                buffer.write(content)
        
        # Parse intervals
        interval_list = [tuple(map(float, interval.split('-'))) for interval in intervals.split(',')]
        
        # Create output file path
        output_file = os.path.join(temp_dir, "output.mp4")
        
        # Clip the video and add audio
        clip_video(temp_video_path, interval_list, output_file, temp_audio_path)
        
        # Add cleanup task to run after response is sent
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        # Return the clipped video as a file response
        return FileResponse(output_file, media_type="video/mp4", filename="clipped_video_with_audio.mp4")
    
    except Exception as e:
        # Clean up the temporary directory in case of an error
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, ImageClip, vfx
import random
from typing import List
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

def create_multiple_clips(input_file, intervals, output_dir, audio_file=None, max_duration=17):
    try:
        # Load video
        video = VideoFileClip(input_file)
        
        # Create individual clips
        all_clips = [video.subclip(start, end) for start, end in intervals]
        intro_clip = all_clips[0]  # Save the intro clip separately
        content_clips = all_clips[1:]  # All other clips
        
        # Generate random combinations
        combinations = generate_truly_random_combinations(content_clips, max_duration, num_combinations=30)
        
        for i, combo_clips in enumerate(combinations):
            print(f"Processing combination {i}")
            print(f"Combination {i} after conversion: length={len(combo_clips)}")
            
            for j, clip in enumerate(combo_clips):
                print(f"  Clip {j}: type={type(clip)}, duration={getattr(clip, 'duration', 'N/A')}")
            
            # Always start with the intro clip
            main_clip = concatenate_videoclips([intro_clip] + combo_clips)
            print(f"Main clip created: type={type(main_clip)}, duration={getattr(main_clip, 'duration', 'N/A')}")
            
            # Rest of the processing remains the same
            target_width, target_height = 1080, 1920
            scale_factor = 1.2
            transition_duration = 0.5

            blurred_bg = main_clip.resize((1920*2, 1080*2))

            main_clip = main_clip.resize(
                newsize=(int(main_clip.w * scale_factor), int(main_clip.h * scale_factor))
            ).set_position("center")

            watermark_path = "assets/watermark.png"
            watermark = None
            if os.path.exists(watermark_path):
                watermark = ImageClip(watermark_path).set_duration(main_clip.duration)
                watermark = watermark.resize(width=int(target_width * 0.88))
                watermark = watermark.set_position(("center", target_height * 0.11)).set_opacity(0.9)

            outro_path = "assets/outro.mp4"
            outro = VideoFileClip(outro_path) if os.path.exists(outro_path) else None

            if outro:
                outro = outro.set_position("center").resize(width=int(target_width * 1.0))
                blurred_bg = blurred_bg.fadeout(transition_duration)
                main_clip = main_clip.fadeout(transition_duration)
                if watermark:
                    watermark = watermark.fadeout(transition_duration)
                outro = outro.fx(vfx.mask_color, color=[0, 0, 0], thr=80, s=10)
                outro = outro.fadein(transition_duration).set_start(main_clip.duration - transition_duration)

            layers = [blurred_bg.set_position("center"), main_clip]
            if watermark:
                layers.append(watermark)
            if outro:
                layers.append(outro)

            final_clip = CompositeVideoClip(layers, size=(target_width, target_height))

            if audio_file:
                main_audio = AudioFileClip(audio_file).subclip(0, final_clip.duration)
                final_clip = final_clip.set_audio(main_audio)

            # Export final video
            output_file = os.path.join(output_dir, f"clip_{i+1}.mp4")
            final_clip.write_videofile(output_file, codec="libx264", audio_codec="aac", preset="ultrafast")

            # Close resources
            if audio_file:
                main_audio.close()
            final_clip.close()

        # Close resources
        video.close()
        if outro:
            outro.close()

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        raise
    except Exception as e:
        print(f"Error in video processing: {e}")
        raise

def generate_truly_random_combinations(clips, max_duration, num_combinations=30):
    all_combinations = []
    attempts = 0
    max_attempts = num_combinations * 20  # More attempts to find unique combinations
    
    # Track combinations we've already seen using a set of frozensets of clip indices
    seen_combinations = set()
    
    while len(all_combinations) < num_combinations and attempts < max_attempts:
        attempts += 1
        
        # Create a completely random permutation of the clips
        clip_indices = list(range(len(clips)))
        random.shuffle(clip_indices)
        
        # Try to fit clips by selecting them in the shuffled order
        selected_indices = []
        total_duration = 0
        
        # Add clips until we reach the max duration
        for idx in clip_indices:
            clip_duration = clips[idx].duration
            if total_duration + clip_duration <= max_duration:
                selected_indices.append(idx)
                total_duration += clip_duration
        
        # We need at least one clip in a combination
        if not selected_indices:
            continue
            
        # Shuffle the selected indices again to ensure the order is random
        random.shuffle(selected_indices)
        
        # Convert to a frozenset for checking uniqueness (order doesn't matter for uniqueness)
        combo_key = frozenset(selected_indices)
        
        # Only add if this is a new combination
        if combo_key not in seen_combinations:
            seen_combinations.add(combo_key)
            # Add the actual clips in the shuffled order
            all_combinations.append([clips[idx] for idx in selected_indices])
    
    # If we didn't get enough combinations, we'll return what we have
    return all_combinations

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
        output_dir = os.path.join("./", "clips")
        
        # Clip the video and add audio
        create_multiple_clips(temp_video_path, interval_list, output_dir, temp_audio_path)
        
        # Add cleanup task to run after response is sent
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        return True
        # Return the clipped video as a file response
        #return FileResponse(output_file, media_type="video/mp4", filename="clipped_video_with_audio.mp4")
    
    except Exception as e:
        # Clean up the temporary directory in case of an error
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


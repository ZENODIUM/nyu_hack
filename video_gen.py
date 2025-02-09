import os
import requests
import librosa
from moviepy import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from gtts import gTTS
from pypexels import PyPexels

def generate_video_with_text(second_parts, combined_text, output_file="final_output_video.mp4"):
    # Pexels API setup
    PEXELS_API_KEY = '0fYfPoddp4VMD6mKGw853H2JEBfCTH4BpqeU0MY03xBybBGsCf9J1T2m'
    py_pexels = PyPexels(api_key=PEXELS_API_KEY)

    # Generate audio and calculate durations using librosa
    audio_file = "temp_audio.mp3"
    tts = gTTS(text=combined_text)
    tts.save(audio_file)
    
    # Calculate time durations using librosa
    y, sr = librosa.load(audio_file)
    total_duration = librosa.get_duration(y=y, sr=sr)
    sentences = combined_text.split(".")
    n = len(sentences)
    time_durations = [(i*total_duration/n, (i+1)*total_duration/n) for i in range(n)]

    # Fetch videos from Pexels and download them
    video_files = []
    for obj in second_parts:
        video_url = None
        search_videos_page = py_pexels.videos_search(query=obj, per_page=1)
        for video in search_videos_page.entries:
            if video.video_files:
                video_url = video.video_files[0].get('link')
                break
        if video_url:
            video_file = f"{obj.replace(' ', '_')}.mp4"
            downloaded_file = download_file(video_url, video_file)
            if downloaded_file:
                video_files.append(downloaded_file)

    # Process video clips with text overlay
    final_clips = []
    for i, video_file in enumerate(video_files):
        try:
            start_time, end_time = time_durations[i]
            target_duration = end_time - start_time
            
            # Original video processing logic
            clip = VideoFileClip(video_file).resized((1280, 720)).with_fps(30)
            clip = clip.subclipped(0, target_duration)

            # Text overlay logic
            text = sentences[i] if i < len(sentences) else ""
            text_clip = TextClip(
                text=text,
                color='white',
                bg_color='black',
                size=(1280, 100),
                method='caption',
                vertical_align='bottom',
                font="font/Arial.ttf",
                horizontal_align='center',
                text_align='center',
                duration=target_duration
            )
            video_with_text = CompositeVideoClip([clip, text_clip])
            final_clips.append(video_with_text)

        except Exception as e:
            print(f"Error processing {video_file}: {e}")

    # Combine final video and add audio
    if final_clips:
        final_video = concatenate_videoclips(final_clips)
        audio_clip = AudioFileClip(audio_file)
        final_video_with_audio = final_video.with_audio(audio_clip)
        static_dir = "static"
        output_file = os.path.join(static_dir, "final_output_video.mp4")
        final_video_with_audio.write_videofile(output_file, codec="libx264", audio_codec="aac")
        return output_file
    return None


def download_file(url, filename):
    """Modified download function to save files in 'downloads' folder"""
    downloads_dir = "downloads"
    os.makedirs(downloads_dir, exist_ok=True)  # Create 'downloads' folder if it doesn't exist
    filepath = os.path.join(downloads_dir, filename)

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        return filepath
    else:
        print(f"Failed to download {url}")
        return None

def clean_downloads_folder():
    """Delete all files in the 'downloads' folder"""
    downloads_dir = "downloads"
    if os.path.exists(downloads_dir):
        for file in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)  # Remove the file
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")

# Example usage
# output_path = generate_video_with_text(
#     second_parts=['sapling', 'trees', 'oak tree', 'sun', 'roots', 'stronger sapling'],
#     combined_text="A small sapling, bent low by a storm, felt immense sadness. It worried it would never stand tall and strong like the other trees. A wise old oak tree nearby whispered, 'Don't despair, little one.' The storm will pass, and the sun will shine again, nourishing your roots. The sapling took heart, remembering the sun's warmth and patiently waited. When the storm subsided, the sapling straightened, stronger and more resilient than before."
# )
# print(f"Generated video at: {output_path}")

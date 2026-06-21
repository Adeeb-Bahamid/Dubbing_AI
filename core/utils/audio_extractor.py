#audio_extractor.py
import subprocess
def extract_audio(video_path, output_audio_path):
    cmd = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'libmp3lame', '-ar', '16000', '-ac', '1','b:a','64k-', output_audio_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
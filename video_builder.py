import subprocess

class VideoBuilder:
    def __init__(self, video_path, audio_path, subtitle_path):
        self.video_path = video_path
        self.audio_path = audio_path
        self.subtitle_path = subtitle_path

    def build_video(self, output_path):
        command = [
            'ffmpeg',
            '-i', self.video_path,
            '-i', self.audio_path,
            '-vf', f"subtitles={self.subtitle_path}",
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-b:v', '3000k',
            '-maxrate', '3000k',
            '-bufsize', '6000k',
            '-vf', 'scale=3840:2160',
            '-shortest',
            output_path
        ]

        subprocess.run(command)

if __name__ == '__main__':
    video_path = 'path/to/minecraft_footage.mp4'
    audio_path = 'path/to/voiceover.mp3'
    subtitle_path = 'path/to/subtitles.srt'
    output_path = 'path/to/output_video.mp4'

    builder = VideoBuilder(video_path, audio_path, subtitle_path)
    builder.build_video(output_path)

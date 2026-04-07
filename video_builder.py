import subprocess


class VideoBuilder:
    """
    Build a Minecraft Short from raw footage, voiceover audio, and subtitles.

    Output: vertical 1080x1920 video (YouTube Shorts format) encoded with
    H.264 at a quality-controlled bitrate, ready for upload.
    """

    DEFAULT_SETTINGS = {
        'width': 1080,
        'height': 1920,
        'fps': 30,
        'video_bitrate': '5000k',
        'max_bitrate': '5000k',
        'buf_size': '10000k',
        'preset': 'veryfast',
        'audio_codec': 'aac',
        'audio_bitrate': '192k',
    }

    def __init__(self, video_path: str, audio_path: str, subtitle_path: str, settings: dict | None = None):
        self.video_path = video_path
        self.audio_path = audio_path
        self.subtitle_path = subtitle_path
        self.settings = {**self.DEFAULT_SETTINGS, **(settings or {})}

    def build_video(self, output_path: str) -> str:
        """
        Compose the final Short and write it to output_path.

        Video filter chain (single -vf pass):
          1. scale to target resolution
          2. burn in subtitles

        Returns output_path on success; raises subprocess.CalledProcessError on failure.
        """
        s = self.settings
        w, h = s['width'], s['height']
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,subtitles={self.subtitle_path}"

        command = [
            'ffmpeg', '-y',
            '-i', self.video_path,
            '-i', self.audio_path,
            '-vf', vf,
            '-c:v', 'libx264',
            '-preset', s['preset'],
            '-b:v', s['video_bitrate'],
            '-maxrate', s['max_bitrate'],
            '-bufsize', s['buf_size'],
            '-r', str(s['fps']),
            '-c:a', s['audio_codec'],
            '-b:a', s['audio_bitrate'],
            '-shortest',
            output_path,
        ]

        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path


if __name__ == '__main__':
    builder = VideoBuilder(
        video_path='path/to/minecraft_footage.mp4',
        audio_path='path/to/voiceover.mp3',
        subtitle_path='path/to/subtitles.srt',
    )
    builder.build_video('output_short.mp4')

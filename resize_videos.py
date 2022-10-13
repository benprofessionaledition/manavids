from collections import namedtuple
import ffmpeg
import numpy as np
import subprocess
import shlex
import json

import logging
logging.basicConfig(level=logging.DEBUG)

# function to find the resolution of the input video file
VideoInfo = namedtuple('VideoInfo', ['height', 'width', 'duration_seconds'])

SCALING_DEFAULT=10.52
SCALING_CATS=14.43

def probe_video(filename: str) -> VideoInfo:
    cmd = "ffprobe -v quiet -print_format json -show_streams"
    args = shlex.split(cmd)
    args.append(filename)
    # run the ffprobe process, decode stdout into utf-8 & convert to JSON
    ffprobe_output = subprocess.check_output(args).decode('utf-8')
    ffprobe_output = json.loads(ffprobe_output)

    # find height and width
    vidstream = ffprobe_output['streams'][0]
    height = vidstream['height']
    width = vidstream['width']
    duration = vidstream['duration']
    return VideoInfo(int(height), int(width), float(duration))

def crop_to_square(filepath, scaling_constant=SCALING_DEFAULT):
    # crop to 1:1, change speed, clip at 3 and 6 seconds, paste reversed, export at 480x480
    info = probe_video(filepath)

    # figure out normalized timestamps
    curr_duration = info.duration_seconds
    scaling_factor = scaling_constant / curr_duration

    stream = (
        ffmpeg
        .input(filepath)
        .filter('crop', 'in_h', 'in_h') # crop to 1:1
        .filter('setpts', f'PTS*{scaling_factor}') # make them play for exactly the same length, since the exported videos will be slightly different
        .filter('trim', start=3, end=6) # clip before 3 seconds, after 6 seconds
        # .filter('fps', fps=30, round='up')
        .output("resources/cropped.mp4")
        .overwrite_output()
        .run()
    )


if __name__ == '__main__':
    crop_to_square("resources/PulsedogeGenerative_00.mp4")
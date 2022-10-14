from collections import namedtuple
import os
import sys
import ffmpeg
import subprocess
import shlex
import json
import argparse
from tqdm import tqdm

import logging
logging.basicConfig(level=logging.DEBUG)

# function to find the resolution of the input video file
VideoInfo = namedtuple('VideoInfo', ['height', 'width', 'duration_seconds'])

SCALING_DEFAULT = 10.52
SCALING_CATS = 14.43


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


def crop_to_square(input_file: str, output_file: str, output_res: str, scaling_constant: float=SCALING_DEFAULT):
    # crop to 1:1, change speed, clip at 3 and 6 seconds, paste reversed, export at 480x480
    info = probe_video(input_file)

    # figure out normalized timestamps
    curr_duration = info.duration_seconds
    scaling_factor = scaling_constant / curr_duration

    stream = (
        ffmpeg
        .input(input_file)
        .filter('crop', 'in_h', 'in_h')  # crop to 1:1
        # make them play for exactly the same length, since the exported videos will be slightly different
        .filter('setpts', f'PTS*{scaling_factor}')
        # clip before 3 seconds, after 6 seconds
        .filter('trim', start=3, end=6)
        # reset pts so the whole thing is 3 seconds
        .filter('setpts', 'PTS-STARTPTS')
        # 30 fps, 480x480
        .filter('fps', fps=30, round='up')
        .filter('scale', output_res, output_res)
        .split()
    )

    stream_rev = (
        stream[1]
        .filter('reverse')
        .filter('setpts', 'PTS-STARTPTS')
    )

    (
        ffmpeg.concat(stream[0], stream_rev)
        .output(output_file)
        .overwrite_output()
        .run()
    )

def main(args):
    parser = argparse.ArgumentParser(description="Mana's video processing script")
    parser.add_argument("input", help="The input directory to process")
    parser.add_argument("--output-dir", default=None, help="The output directory. If none specified, creates a directory called \"output\" inside the input directory")
    parser.add_argument("--time-scale", default=10.52, help="The timescale to normalize input files to")
    parser.add_argument("--output-resolution", default="480", help="The output resolution. All output is square, so only one number is required")
    args = parser.parse_args(args)
    
    input_dir = args.input
    if args.output_dir is None:
        output_dir = os.path.join(input_dir, "processed_output")
    else:
        output_dir = args.output_dir

    time_scale = args.time_scale
    output_resolution = args.output_resolution
    
    for filename in tqdm(os.listdir(input_dir)):
        input_file = os.path.join(input_dir, filename)
        output_file = os.path.join(output_dir, filename)
        time_scale=float(time_scale)
        crop_to_square(input_file, output_file, output_resolution, time_scale)


if __name__ == '__main__':
    main(sys.argv[1:])

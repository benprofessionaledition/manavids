import atexit
from collections import namedtuple
import os
import shutil
import sys
import time
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

def _process_input_output_dir(args: argparse.Namespace):
    input_dir = args.input
    if args.output_dir is None:
        output_dir = os.path.join(input_dir, "processed_output")
    else:
        output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    return input_dir, output_dir

def resize(args: argparse.Namespace):
    input_dir, output_dir = _process_input_output_dir(args)
    time_scale: float = args.time_scale
    output_resolution: int = args.output_resolution
    
    for filename in tqdm(os.listdir(input_dir)):
        if not filename.endswith(".mp4"):
            continue
        input_file = os.path.join(input_dir, filename)
        output_file = os.path.join(output_dir, filename)
        time_scale=float(time_scale)
        crop_to_square(input_file, output_file, output_resolution, time_scale)

def _ls(directory):
    return sorted((os.path.join(directory, f)) for f in os.listdir(directory))

def stitch(args: argparse.Namespace, clean: bool=True):
    input_dir, output_dir = _process_input_output_dir(args)
    """
    These are the ways we can do this:
    1. The stupid way, but it's known to work with ffmpeg: create very short ~0.1s videos of the respective
    parts of each video, then stitch all together
    2. The intuitive way: create a new video and append the relevant parts of every file. This makes sense 
    but I don't think it works with videos/ffmpeg
    3. Another possibly less stupid way: save all the frames individually, instead of videos, to the dir and 
    then make a video out of them
    """
    # get all videos
    video_filenames = sorted([os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".mp4")])

    # make a tmp dir
    timestr = str(int(time.time()))
    tmp_dir = os.path.join(output_dir, f"tmp{timestr}")
    os.makedirs(tmp_dir, exist_ok=True)

    # create "subvideos"
    # The following would skip the first 30 seconds, and then extract the next 10 seconds to a file called output.wmv:
    # ffmpeg -ss 30 -i input.wmv -c copy -t 10 output.wmv
    # In the above command, the timestamps are in seconds (s.msec), but timestamps can also be in HH:MM:SS.xxx format. The following is equivalent:
    # ffmpeg -ss 00:00:30.0 -i input.wmv -c copy -t 00:00:10.0 output.wmv
    
    # assume they're all the same length
    info = probe_video(video_filenames[0])
    total_duration = info.duration_seconds
    
    # we're going to make it loop over all of them
    target_duration = args.clip_duration
    num_vids = len(video_filenames)
    num_clips = int(total_duration / target_duration) # round down
    for e, i in enumerate(range(num_clips)):
        clip_video = video_filenames[i % num_vids]
        # round to avoid fp shit
        clip_start = round(i * target_duration, 2)
        clip_end = round(clip_start + target_duration, 2)
        output_filename = os.path.join(tmp_dir, f"{e:06d}.mp4")
        # this creates fucked up videos
        # cmd = f"ffmpeg -ss {clip_start} -i {clip_video} -c copy -t {target_duration} {output_filename}"
        # subprocess.run(shlex.split(cmd))

        (
            ffmpeg
                .input(clip_video)
                # clip before 3 seconds, after 6 seconds
                .filter('trim', start=clip_start, end=clip_end)
                # reset pts so the whole thing is 3 seconds
                .filter('setpts', 'PTS-STARTPTS')
                # save
                .output(output_filename)
                .overwrite_output()
                .run()
        )


    # concat video files: ffmpeg -f concat -safe 0 -i mylist.txt -c copy output.mp4
    # the blessed way to concat files is to create a text file of filenames
    filenames = [f"file '{f}'" for f in _ls(tmp_dir)]
    txt_filename = os.path.join(tmp_dir, "files.txt")
    with open(txt_filename, "w+") as outf:
        outf.writelines("\n".join(filenames))
    output_filename = os.path.join(output_dir, "output.mp4")
    cmd = f"ffmpeg -f concat -safe 0 -i {txt_filename} -c copy {output_filename}"
    subprocess.run(shlex.split(cmd))
    # shutil.rmtree(tmp_dir)

def main(args):

    parser = argparse.ArgumentParser(description="Wifey's video processing script")
    
    # note to ben - you need to add subparser-specific args before global ones for some reason
    subparsers = parser.add_subparsers()
    sub_resize = subparsers.add_parser("resize", help="Resize a directory of videos")
    sub_resize.add_argument("--time-scale", default=10.52, help="The timescale to normalize input files to")
    sub_resize.add_argument("--output-resolution", default="480", help="The output resolution. All output is square, so only one number is required")
    sub_resize.set_defaults(func=resize)

    sub_stitch = subparsers.add_parser("stitch", help="Stitches all videos in a directory into one video")
    sub_stitch.add_argument("--clip-duration", default=0.2, type=float, help="the duration for each subclip")
    sub_stitch.set_defaults(func=stitch)

    parser.add_argument("input", help="The input directory to process")
    parser.add_argument("--output-dir", default=None, help="The output directory. If none specified, creates a directory called \"output\" inside the input directory")
    
    args = parser.parse_args(args)
    args.func(args)
    
    


if __name__ == '__main__':
    main(sys.argv[1:])

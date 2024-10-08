from collections import namedtuple
import os
import random
import shutil
import sys
import time
import ffmpeg
import subprocess
import shlex
import json
import argparse
from joblib import Parallel, delayed

import logging

logging.basicConfig(level=logging.DEBUG)

# function to find the resolution of the input video file
VideoInfo = namedtuple("VideoInfo", ["height", "width", "duration_seconds"])

SCALING_DEFAULT = 10.52
SCALING_CATS = 14.43


def probe_video(filename: str) -> VideoInfo:
    cmd = "ffprobe -v quiet -print_format json -show_streams"
    args = shlex.split(cmd)
    args.append(filename)
    # run the ffprobe process, decode stdout into utf-8 & convert to JSON
    ffprobe_output = subprocess.check_output(args).decode("utf-8")
    ffprobe_output = json.loads(ffprobe_output)

    # find height and width
    vidstream = ffprobe_output["streams"][0]
    height = vidstream["height"]
    width = vidstream["width"]
    duration = vidstream["duration"]
    return VideoInfo(int(height), int(width), float(duration))


def bounce_video(stream, output_file):
    stream_rev = stream[1].filter("reverse").filter("setpts", "PTS-STARTPTS")
    (ffmpeg.concat(stream[0], stream_rev).output(output_file).overwrite_output().run())


def bounce_only(input_file: str, output_file: str):
    stream = ffmpeg.input(input_file).split()
    bounce_video(stream, output_file)


def resize_and_bounce(input_file: str, 
                      output_file: str, 
                      output_res: str, 
                      scaling_constant: float = SCALING_DEFAULT, 
                      clip_start: int = 3, 
                      clip_end: int = 6):
    # crop to 1:1, change speed, clip at 3 and 6 seconds, paste reversed, export at 480x480
    info = probe_video(input_file)

    # figure out normalized timestamps
    curr_duration = info.duration_seconds
    scaling_factor = scaling_constant / curr_duration

    stream = (
        ffmpeg.input(input_file)
        .filter("crop", "in_h", "in_h")  # crop to 1:1
        # make them play for exactly the same length, since the exported videos will be slightly different
        .filter("setpts", f"PTS*{scaling_factor}")
        # clip before 3 seconds, after 6 seconds
        .filter("trim", start=clip_start, end=clip_end)
        # reset pts so the whole thing is 3 seconds
        .filter("setpts", "PTS-STARTPTS")
        # 30 fps, 480x480
        .filter("fps", fps=30, round="up")
        .filter("scale", output_res, output_res)
        .split()
    )
    bounce_video(stream, output_file)


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
    clip_start = args.clip_start
    clip_end = args.clip_end

    def __execute(filename):
        nonlocal input_dir, output_dir, time_scale
        if not filename.endswith(".mp4"):
            return
        input_file = os.path.join(input_dir, filename)
        output_file = os.path.join(output_dir, filename)
        time_scale = float(time_scale)
        resize_and_bounce(input_file, output_file, output_resolution, time_scale, clip_start=clip_start, clip_end=clip_end)

    filenames = [f for f in os.listdir(input_dir) if f.endswith(".mp4")]

    # joblib has the worst syntax ever
    Parallel(n_jobs=-1)(delayed(__execute)(f) for f in filenames)


def bounce(args: argparse.Namespace):
    # todo: this is copied and pasted from above, could prob just make the same function work
    input_dir, output_dir = _process_input_output_dir(args)

    def __execute(filename):
        nonlocal input_dir, output_dir
        if not filename.endswith(".mp4"):
            return
        input_file = os.path.join(input_dir, filename)
        output_file = os.path.join(output_dir, filename)
        bounce_only(input_file, output_file)

    filenames = [f for f in os.listdir(input_dir) if f.endswith(".mp4")]

    # joblib has the worst syntax ever
    Parallel(n_jobs=-1)(delayed(__execute)(f) for f in filenames)


def _ls(directory):
    return sorted((os.path.join(directory, f)) for f in os.listdir(directory))


def stitch(args: argparse.Namespace):
    """
    Method creates very short ~0.1s videos of the respective
    parts of each video, then stitch all together
    """
    input_dir, output_dir = _process_input_output_dir(args)
    # get all videos
    if args.skip_every < 1:
        raise RuntimeError("Cannot skip less than 1")
    video_filenames = sorted([os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".mp4")])
    video_filenames = video_filenames[:: args.skip_every]

    if args.preserve_first and not args.randomize:
        logging.warning("'Preserve first' specified without 'randomize.' This will have no effect")

    if args.randomize:
        if args.preserve_first:
            fnames_rest = video_filenames[1:]
            random.shuffle(fnames_rest)
            video_filenames[1:] = fnames_rest
        else:
            random.shuffle(video_filenames)

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
    num_clips = int(total_duration / target_duration)  # round down

    # next make a bunch of (index, filename) tuples and store them in a list so we can joblib it
    index_vidname_tuples = [(i, video_filenames[i % num_vids]) for i in range(num_clips)]

    def __execute(i, clip_video):
        # round to avoid fp shit
        nonlocal target_duration, tmp_dir
        clip_start = round(i * target_duration, 2)
        clip_end = round(clip_start + target_duration, 2)
        output_filename = os.path.join(tmp_dir, f"{i:06d}.mp4")
        (
            ffmpeg.input(clip_video)
            # clip before 3 seconds, after 6 seconds
            .filter("trim", start=clip_start, end=clip_end)
            # reset pts so the whole thing is 3 seconds
            .filter("setpts", "PTS-STARTPTS")
            # save
            .output(output_filename)
            .overwrite_output()
            .run()
        )

    Parallel(n_jobs=-1, prefer="threads")(delayed(__execute)(i, f) for i, f in index_vidname_tuples)
    # concat video files: ffmpeg -f concat -safe 0 -i mylist.txt -c copy output.mp4
    # the blessed way to concat files is to create a text file of filenames: "file [filepath]"
    filenames = [f"file '{f}'" for f in _ls(tmp_dir)]
    txt_filename = os.path.join(tmp_dir, "files.txt")
    with open(txt_filename, "w+") as outf:
        outf.writelines("\n".join(filenames))
    output_filename = os.path.join(output_dir, f"output{timestr}.mp4")
    # blow it away because we lose the interactive console with joblib and ffmpeg wants input
    if os.path.exists(output_filename):
        os.remove(output_filename)
    cmd = f"ffmpeg -f concat -safe 0 -i {txt_filename} -c copy {output_filename}"
    subprocess.run(shlex.split(cmd))
    shutil.rmtree(tmp_dir)


def main(args):

    parser = argparse.ArgumentParser(description="Wifey's video processing script")

    # note to ben - you need to add subparser-specific args before global ones for some reason
    subparsers = parser.add_subparsers()
    sub_resize = subparsers.add_parser("resize", help="Resize a directory of videos")
    sub_resize.add_argument("--time-scale", default=10.52, type=float, help="The timescale to normalize input files to")
    sub_resize.add_argument("--output-resolution", default="1080", help="The output resolution. All output is square, so only one number is required")
    sub_resize.add_argument("--clip-start", default=3.0, type=float, help="Clip start timestamp")
    sub_resize.add_argument("--clip-end", default=6.0, type=float, help="Clip end timestamp")
    sub_resize.set_defaults(func=resize)

    sub_stitch = subparsers.add_parser("stitch", help="Stitches all videos in a directory into one video")
    sub_stitch.add_argument("--skip-every", default=1, type=int, help="skips every N of the input")
    sub_stitch.add_argument("--clip-duration", default=0.2, type=float, help="the duration for each subclip")
    sub_stitch.add_argument("--randomize", action="store_true", help="If specified, will randomize the order of images")
    sub_stitch.add_argument(
        "--preserve-first", action="store_true", default=True, help="If set, will preserve the first video even if others are randomized. Default true"
    )
    sub_stitch.set_defaults(func=stitch)

    sub_bounce = subparsers.add_parser("bounce", help="Make a directory of videos 'bounce' back and forth, with no resizing or anything")
    sub_bounce.set_defaults(func=bounce)

    parser.add_argument("input", help="The input directory to process")
    parser.add_argument(
        "--output-dir", default=None, help='The output directory. If none specified, creates a directory called "output" inside the input directory'
    )

    args = parser.parse_args(args)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])

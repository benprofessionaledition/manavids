"""
Converts a folder full of images to videos
"""

import ffmpeg
import os
from pathlib import Path
import sys
import logging
import argparse

from joblib import Parallel, delayed

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def convert_video_png(file_in: str, export_directory: str):
    # base cmd: ffmpeg -skip_frame nokey -i file -vsync 0 -frame_pts true out%d.png
    logger.debug(f"Converting {file_in}")
    file_in_fname = Path(file_in).stem
    (
        ffmpeg.input(file_in)
        .filter('skip_frame', 'nokey')
        .vsync(0)
        .filter('framepts', 'true')
        .output(f'{export_directory}/{file_in_fname}_out%d.png')
        .run()
    )

def convert_video_gif(file_in: str, export_directory: str):
    logger.debug(f"Converting {file_in}")
    file_in_fname = Path(file_in).stem
    (
        ffmpeg.input(file_in)
        .output(f'{export_directory}/{file_in_fname}.gif', vf='fps=25,scale=320:-1:flags=lanczos', format='gif')
        .run()
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Converts videos to images")
    parser.add_argument("import_directory", help="The directory where all the videos are")
    parser.add_argument("--png", action="store_true", help="Convert videos to PNG images")
    parser.add_argument("--gif", action="store_true", help="Convert videos to GIF images")
    args = parser.parse_args()

    import_dir = args.import_directory
    if not os.path.exists(import_dir):
        raise ValueError("Import directory doesn't exist")
    output_dir = os.path.join(import_dir, "processed_videos")
    os.makedirs(output_dir, exist_ok=True)

    files = [os.path.join(import_dir, f) for f in os.listdir(import_dir) if f.endswith(".mp4")]
    if args.png:
        func = convert_video_png
    elif args.gif:
        func = convert_video_gif
    else:
        parser.error("Please specify either --png or --gif flag")

    Parallel()(delayed(func)(filename, output_dir) for filename in files)

    logger.info("Converted %d files. Their output can be found at: %s", len(files), output_dir)
    sys.exit(0)
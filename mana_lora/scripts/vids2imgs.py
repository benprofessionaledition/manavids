"""
Converts a folder full of images to videos
"""

import ffmpeg
import os
from pathlib import Path
import sys
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

IMPORT_DIRECTORY = "~/mana_videos/"
EXPORT_DIRECTORY = "~/mana_videos/processed_output/"

def convert_video(file_in: str):
    # base cmd: ffmpeg -skip_frame nokey -i file -vsync 0 -frame_pts true out%d.png
    logger.debug(f"Converting {file_in}")
    file_in_fname = Path(file_in).stem
    (
        ffmpeg.input(file_in)
        .filter('skip_frame', 'nokey')
        .vsync(0)
        .filter('framepts', 'true')
        .output(f'{EXPORT_DIRECTORY}/{file_in_fname}_out%d.png')
        .run()
    )

if __name__ == "__main__":
    for file in os.listdir(IMPORT_DIRECTORY):
        if file.endswith(".mp4"):
            convert_video(file)
            sys.exit(0)
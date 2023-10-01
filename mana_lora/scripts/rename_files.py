import copy
import json
import os
import argparse
import pathlib
import sys
from typing import List
import random


def recursive_combine_filenames(agg, dir_stack, directory) -> List[str]:
    filenames = []
    current_file_path = os.path.join(*dir_stack)
    if not os.path.isdir(directory):
        filename = dir_stack.pop()
        file_prefix = dir_stack.pop()
        new_filename = os.path.join(*dir_stack, file_prefix + filename)
        agg.append(new_filename)


def main():
    parser = argparse.ArgumentParser("Mana's tool for renaming a bunch of files")
    parser.add_argument(
        "input_dir", help="the input directory that contains all the other directories"
    )
    parser.add_argument(
        "--first_image",
        help="the name of the first video, e.g. .../Flames/1.mp4 would be Flames1",
    )
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args(sys.argv[1:])

    input_dir = args.input_dir
    print(input_dir)
    abspath = os.path.abspath(input_dir)
    print(abspath)
    first_name = args.first_image
    print(first_name)

    # get all the subdirectories
    fnames = []
    for s in os.listdir(abspath):
        subdir = os.path.join(abspath, s)
        if os.path.isdir(subdir):
            for f in os.listdir(subdir):
                old_path = os.path.join(subdir, f)
                if not os.path.isdir(old_path):
                    if first_name is not None and first_name == old_path:
                        fnames.insert(0, old_path)
                    else:
                        fnames.append(old_path)

    # next assign them random indices and shuffle
    fnames_copy = copy.deepcopy(fnames[1:])
    random.shuffle(fnames_copy)
    fnames = [fnames[0]] + fnames_copy
    fnames_final = {}
    for i, old_path in enumerate(fnames):
        path = pathlib.Path(old_path)
        new_path = pathlib.Path(path.parent.parent, str(i+1) + path.suffix)
        fnames_final[old_path] = str(new_path)
    
    print(fnames_final)
    print(f"Found {len(fnames_final)} files to rename")
    if not args.dry_run:
        with open(os.path.join(input_dir, "files_renamed.json"), "w+") as fout:
            json.dump(fnames_final, fout)
        for o, n in fnames_final.items():
            os.rename(o, n)


if __name__ == "__main__":
    main()

# Mana's Fun Utilities

This is a collection of Python scripts for Mana. 

Scripts include: 

`resize_videos.py` - Resize a directory full of videos
`combine_stuff_as_csv.py` - Do some combinatorics crap to come up with a list of combinations of stuff (e.g. components for art)

## How to deal with Python on Windows

* Use a Windows installer, otherwise you have to compile from source and do god knows what else
* To use Python, use `py` instead of `python`
* To activate a virtualenv, use `.\.venv\Scripts\Activate.ps1`
* The rest of it is basically normal afaik


## How to Install

Assume everything has to be run in Powershell as an administrator. 

1. Install Python 3.8+. This is outside the scope of this documentation, just download a binary installer, maybe use pre-3.10 if possible but it probably doesn't matter. See Above for hints
1. Run this command to make it so Powershell can run scripts:
    ```
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Unrestricted
    ```
1.  Install FFmpeg on Windows using this guide: https://www.wikihow.com/Install-FFmpeg-on-Windows
1.  Run the scripts, see above. Should work.

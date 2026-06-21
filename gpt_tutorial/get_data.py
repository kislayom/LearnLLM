"""
Create input.txt for train.py.

Tries to download the "tiny Shakespeare" dataset (~1MB). If there's no network
access, it falls back to a small built-in sample so the tutorial still runs
fully offline (the model just won't have as much to learn from).
"""

import os
import urllib.request

URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"

FALLBACK = (
    "To be, or not to be, that is the question:\n"
    "Whether 'tis nobler in the mind to suffer\n"
    "The slings and arrows of outrageous fortune,\n"
    "Or to take arms against a sea of troubles\n"
    "And by opposing end them. To die: to sleep;\n"
) * 200  # repeated so there's enough text to form batches


def main():
    if os.path.exists("input.txt"):
        print("input.txt already exists — nothing to do.")
        return
    try:
        print("Downloading tiny Shakespeare ...")
        urllib.request.urlretrieve(URL, "input.txt")
        size = os.path.getsize("input.txt")
        print(f"Saved input.txt ({size/1024:.0f} KB).")
    except Exception as e:
        print(f"Download failed ({e}). Writing built-in fallback sample instead.")
        with open("input.txt", "w", encoding="utf-8") as f:
            f.write(FALLBACK)
        print(f"Saved fallback input.txt ({os.path.getsize('input.txt')/1024:.0f} KB).")


if __name__ == "__main__":
    main()

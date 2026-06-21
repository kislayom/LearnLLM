"""
Fetch a training corpus into input.txt for train.py.

Usage:
    python get_data.py                 # default: tiny shakespeare
    python get_data.py tinystories     # simple short stories (great for tiny models)
    python get_data.py sherlock        # Sherlock Holmes (Project Gutenberg)
    python get_data.py --list          # show all options

If a download fails (e.g. no network), a small built-in sample is written so the
tutorial still runs fully offline. See DATA.md for details on each dataset.
"""

import os
import sys
import urllib.request

DATASETS = {
    "shakespeare": {
        "url": "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt",
        "size": "~1 MB",
        "desc": "Tiny Shakespeare — the classic char-level demo; quick, recognizable English.",
    },
    "tinystories": {
        "url": "https://huggingface.co/datasets/roneneldan/TinyStories/resolve/main/TinyStoriesV2-GPT4-valid.txt",
        "size": "~20 MB",
        "desc": "TinyStories (validation split) — short, simple stories; even tiny models learn coherent English.",
    },
    "sherlock": {
        "url": "https://www.gutenberg.org/files/1661/1661-0.txt",
        "size": "~600 KB",
        "desc": "The Adventures of Sherlock Holmes (Project Gutenberg, public domain).",
    },
}

FALLBACK = (
    "To be, or not to be, that is the question:\n"
    "Whether 'tis nobler in the mind to suffer\n"
    "The slings and arrows of outrageous fortune,\n"
    "Or to take arms against a sea of troubles\n"
    "And by opposing end them. To die: to sleep;\n"
) * 200


def list_datasets():
    print("Available datasets:\n")
    for name, d in DATASETS.items():
        print(f"  {name:<13} {d['size']:<9} {d['desc']}")
    print("\nUsage: python get_data.py <name>")


def main():
    args = sys.argv[1:]
    if args and args[0] in ("--list", "-l", "list"):
        list_datasets()
        return

    name = args[0] if args else "shakespeare"
    if name not in DATASETS:
        print(f"Unknown dataset '{name}'.\n")
        list_datasets()
        sys.exit(1)

    if os.path.exists("input.txt"):
        ans = input("input.txt already exists. Overwrite? [y/N] ").strip().lower()
        if ans != "y":
            print("Keeping existing input.txt.")
            return

    ds = DATASETS[name]
    try:
        print(f"Downloading '{name}' ({ds['size']}) ...")
        req = urllib.request.Request(ds["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open("input.txt", "wb") as f:
            f.write(r.read())
        print(f"Saved input.txt ({os.path.getsize('input.txt')/1024:.0f} KB) from {name}.")
    except Exception as e:
        print(f"Download failed ({e}). Writing built-in fallback sample instead.")
        with open("input.txt", "w", encoding="utf-8") as f:
            f.write(FALLBACK)
        print(f"Saved fallback input.txt ({os.path.getsize('input.txt')/1024:.0f} KB).")


if __name__ == "__main__":
    main()

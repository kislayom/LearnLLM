import subprocess, sys, os
with open("sample.txt", "w") as f:
    f.write("hello world\nfoo bar baz\n")
w = subprocess.run([sys.executable, "wordcount.py", "sample.txt"],
                   capture_output=True, text=True)
assert w.stdout.strip() == "5", f"words: {w.stdout!r} {w.stderr!r}"
l = subprocess.run([sys.executable, "wordcount.py", "--lines", "sample.txt"],
                   capture_output=True, text=True)
assert l.stdout.strip() == "2", f"lines: {l.stdout!r} {l.stderr!r}"
print("ok")

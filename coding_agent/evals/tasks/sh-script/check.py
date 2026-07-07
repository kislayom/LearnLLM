import os, subprocess, sys
with open("small.txt", "w") as f: f.write("a")
with open("big.txt", "w") as f: f.write("x" * 5000)
assert os.path.exists("biggest.sh"), "biggest.sh missing"
r = subprocess.run(["bash", "biggest.sh"], capture_output=True, text=True)
out = r.stdout.strip().split("/")[-1]
assert out == "big.txt", f"got {r.stdout!r} {r.stderr!r}"
print("ok")

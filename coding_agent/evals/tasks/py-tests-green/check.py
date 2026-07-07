import subprocess, sys
r = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_queue_lib"],
                   capture_output=True, text=True)
print((r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "")
# also ensure they didn't cheat by editing the tests
src = open("test_queue_lib.py").read()
assert "test_fifo_order" in src and "test_capacity_enforced" in src
sys.exit(r.returncode)

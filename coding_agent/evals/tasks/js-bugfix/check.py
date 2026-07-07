import shutil, subprocess, sys
if not shutil.which("node"):
    print("node not installed"); sys.exit(2)
script = ("const {slugify}=require('./slug.js');"
          "const a=slugify('Hello  World!');"
          "if(a!=='hello-world'){console.error('got '+a);process.exit(1)};"
          "const b=slugify('A--B');"
          "if(b!=='a-b'){console.error('got '+b);process.exit(1)};"
          "console.log('ok')")
r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
print(r.stdout + r.stderr)
sys.exit(r.returncode)

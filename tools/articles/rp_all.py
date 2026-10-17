import os, re, subprocess, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
for pre in 'ardzufjgck':
    toks = sorted((f[:-3] for f in os.listdir('art') if re.fullmatch(rf'{pre}\d+\.py', f)), key=lambda t: int(t[1:]))
    r = subprocess.run(['python3', 'publish.py', *toks, '--save'], capture_output=True, text=True)
    open(f'out/_republish_{pre}.log', 'w').write(r.stdout + r.stderr)
    print(pre, len(toks), 'tokens;', r.stdout.count('saved '), 'saved;', 'rc', r.returncode, flush=True)

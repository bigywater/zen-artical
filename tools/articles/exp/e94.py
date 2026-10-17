import os, sys, subprocess, tempfile, textwrap, json, zipfile, shutil, re

W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
V = os.path.join(os.environ['HERE'], 'venv/bin')
def P(x): return x.replace(W, '<项目>').replace(os.environ['HERE'], '<scratch>')
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['BUILD_LOG'] = os.path.join(W, 'backend.log')

os.makedirs('proj/backend'); os.makedirs('proj/src/hello_pkg')
open('proj/pyproject.toml', 'w').write(textwrap.dedent('''
    [build-system]
    requires = []
    build-backend = "mybackend"
    backend-path = ["backend"]

    [project]
    name = "hello-pkg"
    version = "0.1.0"
    description = "演示用"
    requires-python = ">=3.10"
'''))
open('proj/src/hello_pkg/__init__.py', 'w').write("def hi(): return 'hello from hello_pkg'\n")
shutil.copy(os.path.join(os.environ['HERE'], 'exp/mybackend.py'), 'proj/backend/mybackend.py')

def runlog(cmd, label):
    if os.path.exists('backend.log'): os.remove('backend.log')
    r = subprocess.run(cmd, capture_output=True, text=True, env=E, cwd=os.path.join(W, 'proj'))
    print(f"\n$ {label}\n  返回码 {r.returncode}")
    recs = [json.loads(l) for l in open('backend.log')] if os.path.exists('backend.log') else []
    for x in recs: print(f"  后端被调用: {x['hook']:<34} pid={x['pid']} ppid={x['ppid']}  python={P(x['python'])}  cwd={P(x['cwd'])}")
    if r.returncode: print("  stderr 末尾:", P(r.stderr.strip())[-300:])
    return r, recs

print("== 一、项目里只有一个 pyproject.toml 和一个自己写的 build backend(mybackend.py, 通过 backend-path 指向) ==")
print(open('proj/pyproject.toml').read().strip())

print("\n== 二、python -m build --wheel: 前端与后端的关系 ==")
print("  前端(build)的 python =", P(os.path.join(V, 'python')))
r, recs1 = runlog([os.path.join(V, 'python'), '-m', 'build', '--wheel', '--outdir', os.path.join(W, 'dist1')], "python -m build --wheel  (默认: 隔离环境)")
print("  产物:", os.listdir('dist1'))
r, recs2 = runlog([os.path.join(V, 'python'), '-m', 'build', '--wheel', '--no-isolation', '--outdir', os.path.join(W, 'dist2')], "python -m build --wheel --no-isolation")

print("\n== 三、pip 作为前端: pip install . 会调用哪些钩子 ==")
r, recs3 = runlog([os.path.join(V, 'python'), '-m', 'pip', 'install', '--no-deps', '--no-index', '--target', os.path.join(W, 'site_t'), '.'], "pip install --target site_t .")
print("  安装出来的文件:", sorted(os.listdir('site_t')) if os.path.exists(os.path.join(W, 'site_t')) else '(无)')
sys.path.insert(0, os.path.join(W, 'site_t')); import hello_pkg; print("  import hello_pkg; hello_pkg.hi() =", hello_pkg.hi())

print("\n== 四、wheel 只是一个 zip ==")
whl = os.path.join('dist1', os.listdir('dist1')[0])
with zipfile.ZipFile(whl) as z:
    for i in z.infolist(): print(f"  {i.filename:<45} {i.file_size:>5} 字节")
    print("  METADATA 内容:\n    " + z.read('hello_pkg-0.1.0.dist-info/METADATA').decode().strip().replace('\n', '\n    '))

print("\n== 五、后端崩溃时前端看到什么 ==")
E["BACKEND_CRASH"] = "1"
r = subprocess.run([os.path.join(V, 'python'), '-m', 'build', '--wheel', '--no-isolation', '--outdir', os.path.join(W, 'dist3')], capture_output=True, text=True, env=E, cwd=os.path.join(W, 'proj'))
print("  返回码", r.returncode, "| stderr 最后两行:", P(' / '.join(r.stderr.strip().splitlines()[-2:])))
json.dump({'r1': recs1, 'r2': recs2, 'r3': recs3}, open(os.path.join(os.environ['HERE'], 'out/94.json'), 'w'), ensure_ascii=False)

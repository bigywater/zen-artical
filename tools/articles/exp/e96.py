import os, sys, subprocess, tempfile, textwrap, json, shutil

HERE = os.environ['HERE']; W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None); E['BUILD_LOG'] = os.path.join(W, 'b.log')
def P(x): return x.replace(W, '<工作目录>')
def sh(args, **kw): return subprocess.run(args, capture_output=True, text=True, env=E, **kw)
PIP = [HERE + '/venv/bin/python', '-m', 'pip']
def newenv(name):
    sh([sys.executable, '-m', 'venv', name]); return os.path.join(W, name, 'bin/python')
def sp(env): return os.path.join(W, env, 'lib/python3.14/site-packages')
def ls(env): return sorted(x for x in os.listdir(sp(env)) if not x.startswith(('pip', '_distutils_hack', '__pycache__')))
def code(py, snippet): return sh([py, '-c', snippet]).stdout.strip()

def mkproj(name, backend):
    os.makedirs(f'{name}/src/hello_pkg')
    if backend == 'mine':
        os.makedirs(f'{name}/backend'); shutil.copy(HERE + '/exp/mybackend3.py', f'{name}/backend/mybackend.py')
        bs = 'requires = []\nbuild-backend = "mybackend"\nbackend-path = ["backend"]'
    else:
        bs = 'requires = ["setuptools>=64"]\nbuild-backend = "setuptools.build_meta"'
    open(f'{name}/pyproject.toml', 'w').write(f'[build-system]\n{bs}\n\n[project]\nname = "hello-pkg"\nversion = "0.1.0"\n\n[project.scripts]\nhello-one = "hello_pkg:main"\n' + ('\n[tool.setuptools.packages.find]\nwhere = ["src"]\n' if backend == 'setuptools' else ''))
    open(f'{name}/src/hello_pkg/__init__.py', 'w').write("VERSION_TEXT = 'v1'\ndef main(): print('main v1')\n")

print("== 一、普通安装: 装的是一份拷贝 ==")
mkproj('projA', 'mine'); pyA = newenv('envA')
sh(PIP + ['--python', pyA, 'install', '--no-deps', '--no-index', './projA'])
print("  site-packages 里:", ls('envA'))
print("  hello_pkg.__file__ =", P(code(pyA, "import hello_pkg; print(hello_pkg.__file__)")))
open('projA/src/hello_pkg/__init__.py', 'w').write("VERSION_TEXT = 'v2 (改过源码)'\ndef main(): print('main v2')\n")
print("  改了项目里的源码(v1 → v2)之后, 新进程里 hello_pkg.VERSION_TEXT =", code(pyA, "import hello_pkg; print(hello_pkg.VERSION_TEXT)"), " ← 仍是旧的")

print("\n== 二、可编辑安装(我的最小后端, PEP 660 的 build_editable) ==")
open('projA/src/hello_pkg/__init__.py', 'w').write("VERSION_TEXT = 'v1'\ndef main(): print('main v1')\n")
pyB = newenv('envB')
r = sh(PIP + ['--python', pyB, 'install', '--no-deps', '--no-index', '-e', './projA'])
print("  pip install -e ./projA → 返回码", r.returncode, "|", r.stdout.strip().splitlines()[-1])
print("  site-packages 里:", ls('envB'))
pth = [f for f in ls('envB') if f.endswith('.pth')][0]
print("  ", pth, "的内容:", P(open(os.path.join(sp('envB'), pth)).read().strip()))
print("  hello_pkg.__file__ =", P(code(pyB, "import hello_pkg; print(hello_pkg.__file__)")))
print("  sys.path 里有项目的 src 目录?", any('projA/src' in p for p in code(pyB, "import sys; print(sys.path)").split(',')))
di = [f for f in ls('envB') if f.endswith('.dist-info')][0]
print("  dist-info/direct_url.json =", P(open(os.path.join(sp('envB'), di, 'direct_url.json')).read().strip()))
open('projA/src/hello_pkg/__init__.py', 'w').write("VERSION_TEXT = 'v2 (改过源码)'\ndef main(): print('main v2')\n")
print("  改源码(v1 → v2)之后, 新进程里 VERSION_TEXT =", code(pyB, "import hello_pkg; print(hello_pkg.VERSION_TEXT)"), " ← 立刻生效, 没有重新安装")
os.makedirs('projA/src/newpkg'); open('projA/src/newpkg/__init__.py', 'w').write("X = 1\n")
print("  在 src 下新增一个包 newpkg 之后, 直接 import newpkg →", code(pyB, "import newpkg; print('成功', newpkg.X)") or sh([pyB, '-c', 'import newpkg']).stderr.strip().splitlines()[-1])

print("\n== 三、什么改动不会自动生效: 元数据与命令行入口 ==")
s = open('projA/pyproject.toml').read().replace('hello-one = "hello_pkg:main"', 'hello-one = "hello_pkg:main"\nhello-two = "hello_pkg:main"')
open('projA/pyproject.toml', 'w').write(s)
print("  往 pyproject.toml 里新增脚本 hello-two 之后, env/bin/ 里:", sorted(x for x in os.listdir(os.path.join(W, 'envB/bin')) if 'hello' in x))
sh(PIP + ['--python', pyB, 'install', '--no-deps', '--no-index', '-e', './projA'])
print("  重新 pip install -e 之后:", sorted(x for x in os.listdir(os.path.join(W, 'envB/bin')) if 'hello' in x))

print("\n== 四、真实的 setuptools 后端做的可编辑安装(需要联网拉取 setuptools) ==")
mkproj('projS', 'setuptools'); pyC = newenv('envC')
r = sh(PIP + ['--python', pyC, 'install', '--no-deps', '-e', './projS'])
print("  pip install -e ./projS(setuptools)→ 返回码", r.returncode, "|", (r.stdout.strip().splitlines() or [r.stderr[-150:]])[-1])
print("  site-packages 里:", ls('envC'))
for f in ls('envC'):
    if f.endswith('.pth'): print("  ", f, "的内容:", P(open(os.path.join(sp('envC'), f)).read().strip()))
print("  hello_pkg.__file__ =", P(code(pyC, "import hello_pkg; print(hello_pkg.__file__)")))
os.makedirs('projS/src/newpkg'); open('projS/src/newpkg/__init__.py', 'w').write("X = 1\n")
print("  setuptools 版:在 src 下新增包 newpkg 之后 import newpkg →", code(pyC, "import newpkg; print('成功')") or sh([pyC, '-c', 'import newpkg']).stderr.strip().splitlines()[-1])

print("\n== 五、卸载 ==")
sh(PIP + ['--python', pyB, 'uninstall', '-y', 'hello-pkg'])
print("  卸载可编辑安装后, site-packages 里:", ls('envB'), "| 项目源码还在吗?", os.path.exists('projA/src/hello_pkg/__init__.py'))

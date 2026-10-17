import subprocess, sys, os, tempfile, json, textwrap

W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
def P(x): return x.replace(W, '<工作目录>')
def run(args, cwd=W, input=None):
    e = dict(os.environ); e.pop('HTTP_PROXY', None); e.pop('HTTPS_PROXY', None); e.pop('PYTHONPATH', None)
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=e, cwd=cwd, timeout=60); return P((r.stdout + r.stderr).strip())
def w(path, body):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); open(path, 'w').write(textwrap.dedent(body))

w('pkg/__init__.py', "")
w('pkg/util.py', "def hi(): return 'util.hi'\n")
w('pkg/tool.py', '''
    import sys
    print("__name__      =", repr(__name__))
    print("__package__   =", repr(__package__))
    print("__spec__      =", None if __spec__ is None else "ModuleSpec(name=%r)" % __spec__.name)
    print("sys.path[0]   =", repr(sys.path[0]))
    try:
        from .util import hi; print("相对导入 from .util import hi →", hi())
    except ImportError as e: print("相对导入 →", type(e).__name__ + ":", e)
''')
print("== 一、同一个文件, 两种运行方式 ==")
print("$ python pkg/tool.py                (当成脚本)"); print(run(['pkg/tool.py']))
print("\n$ python -m pkg.tool               (当成模块)"); print(run(['-m', 'pkg.tool']))
print("\n$ python -c 'import pkg.tool'      (被 import)"); print(run(['-c', 'import pkg.tool']))

print("\n== 二、__main__ 被执行两次的陷阱 ==")
w('a.py', '''
    print("  [a.py] 开始执行, __name__ =", repr(__name__))
    import b
    print("  [a.py] 结束, __name__ =", repr(__name__))
    X = 1
''')
w('b.py', '''
    print("  [b.py] 开始, 它 import a")
    import a
    print("  [b.py] 结束, a 是", a.__name__, "| a.__file__ 的文件名 =", a.__file__.split('/')[-1])
''')
print("$ python a.py"); print(run(['a.py']))

print("\n== 三、把类定义在 __main__ 里, pickle 出来在别处读不了 ==")
w('save.py', '''
    import pickle
    class Point:
        def __init__(self, x): self.x = x
    open("p.pkl", "wb").write(pickle.dumps(Point(3)))
    print("已保存, pickle 里记录的类路径:", pickle.dumps(Point(3))[:60])
''')
w('load.py', '''
    import pickle
    print(pickle.loads(open("p.pkl", "rb").read()))
''')
print("$ python save.py"); print(run(['save.py']))
print("$ python load.py"); print(run(['load.py']).splitlines()[-1])

print("\n== 四、macOS 默认的 spawn: 没有 __main__ 保护会怎样 ==")
w('mp_bad.py', '''
    import multiprocessing as mp
    def f(): print("子进程在跑")
    p = mp.Process(target=f); p.start(); p.join()
''')
w('mp_ok.py', '''
    import multiprocessing as mp
    def f(): print("子进程在跑")
    if __name__ == "__main__":
        p = mp.Process(target=f); p.start(); p.join(); print("父进程结束, 默认启动方式 =", mp.get_start_method())
''')
out = run(['mp_bad.py']); lines = out.splitlines()
print("$ python mp_bad.py   (没有 if __name__ == '__main__' 保护)")
k = next(i for i, l in enumerate(lines) if l.startswith('RuntimeError'))
print("\n".join(l.strip() for l in lines[k:k + 4] if l.strip()))
print("\n$ python mp_ok.py"); print(run(['mp_ok.py']))

print("\n== 五、目录和 zip 也能被当成程序运行 ==")
w('app/__main__.py', 'print("app/__main__.py 被执行, __name__ =", repr(__name__), ", sys.path[0] =", __import__("sys").path[0])\n')
print("$ python app/"); print(run(['app/']))
print("$ python -m app"); print(run(['-m', 'app']))

print("\n== 六、runpy: 在代码里模拟 python 运行 ==")
w('script_x.py', 'print("script_x: __name__ =", repr(__name__))\n')
print(run(['-c', 'import runpy; runpy.run_path("script_x.py"); runpy.run_path("script_x.py", run_name="__main__")']))

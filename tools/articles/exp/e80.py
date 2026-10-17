import zipfile, os, sys, tempfile, subprocess, shutil, textwrap, json, time, importlib, py_compile
work = os.path.realpath(tempfile.mkdtemp()); os.chdir(work)
os.makedirs('src/mypkg'); 
open('src/mypkg/__init__.py', 'w').write("VERSION = '1.0'\n")
open('src/mypkg/mod.py', 'w').write(textwrap.dedent('''
    import os
    def where(): return __file__
    def read_neighbor():
        return open(os.path.join(os.path.dirname(__file__), "data.txt")).read()
'''))
open('src/mypkg/data.txt', 'w').write("hello from data.txt\n")
def mkzip(name, files):
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, path in files: z.write(path, arc)
mkzip('app.zip', [('mypkg/__init__.py', 'src/mypkg/__init__.py'), ('mypkg/mod.py', 'src/mypkg/mod.py'), ('mypkg/data.txt', 'src/mypkg/data.txt')])
def lst(): return sorted(zipfile.ZipFile('app.zip').namelist())

print("== 一、把 zip 放进 sys.path, 然后 import ==")
print("zip 里的文件:", lst())
sys.path.insert(0, os.path.abspath('app.zip'))
import mypkg, mypkg.mod
print("mypkg.__file__      =", mypkg.__file__.replace(work, '<临时目录>'))
print("mypkg.mod.__file__  =", mypkg.mod.__file__.replace(work, '<临时目录>'))
print("mypkg.__loader__    =", type(mypkg.__loader__))
print("mypkg.__spec__.origin =", mypkg.__spec__.origin.replace(work, '<临时目录>'))
print("sys.path_importer_cache[zip] 的类型 =", type(sys.path_importer_cache[os.path.abspath('app.zip')]))
print("sys.path_hooks =", [getattr(h, '__name__', repr(h)) for h in sys.path_hooks])
print("import 之后 zip 里的文件:", lst(), "→ 变化了吗?", lst() != ['mypkg/__init__.py', 'mypkg/data.txt', 'mypkg/mod.py'])
print("zip 旁边有 __pycache__ 吗?", os.path.exists('__pycache__'), "| src 目录有吗?", os.path.exists('src/mypkg/__pycache__'))

print("\n== 二、包里的数据文件: 相对 __file__ 打开 vs 官方接口 ==")
try: mypkg.mod.read_neighbor()
except Exception as e: print("open(dirname(__file__)/data.txt) →", type(e).__name__ + ":", str(e).replace(work, '<临时目录>'))
import pkgutil, importlib.resources as res
print("pkgutil.get_data('mypkg', 'data.txt') →", pkgutil.get_data('mypkg', 'data.txt'))
print("importlib.resources.files('mypkg').joinpath('data.txt').read_text() →", repr(res.files('mypkg').joinpath('data.txt').read_text()))

print("\n== 三、扩展模块(.so)不能从 zip 里加载 ==")
import sysconfig
so = os.path.join(sysconfig.get_config_var('DESTSHARED'), 'array.cpython-314-darwin.so')
mkzip('ext.zip', [('array.cpython-314-darwin.so', so), ('myext.cpython-314-darwin.so', so)])
print("zip 里放了两份真实 .so: array.cpython-314-darwin.so 和改名的 myext.cpython-314-darwin.so; zip 排在 sys.path 第一位")
code = "import sys; sys.path.insert(0, 'ext.zip'); import array; print('import array → 实际来自', array.__file__)"
r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
print("  ", r.stdout.strip().replace(os.path.dirname(so), '<lib-dynload>'), r.stderr.strip()[-200:])
code = "import sys; sys.path.insert(0, 'ext.zip'); import myext"
r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
print("   import myext →", r.stderr.strip().splitlines()[-1])

print("\n== 四、python app.pyz: 可执行 zip ==")
os.makedirs('zapp'); open('zapp/__main__.py', 'w').write("import mypkg\nprint('__main__ 在 zip 里运行, mypkg.VERSION =', mypkg.VERSION, '| __file__ =', __file__.split('/')[-2:])\n")
shutil.copytree('src/mypkg', 'zapp/mypkg')
subprocess.run([sys.executable, '-m', 'zipapp', 'zapp', '-o', 'app.pyz', '-p', '/usr/bin/env python3'], check=True)
print("head -c 40 app.pyz =", open('app.pyz', 'rb').read(40))
print("python3 app.pyz →", subprocess.run([sys.executable, 'app.pyz'], capture_output=True, text=True).stdout.strip())

print("\n== 五、导入速度: 目录(已缓存 pyc) vs zip(源码) vs zip(预编译 pyc) ==")
big = "\n".join(f"def f{i}(x):\n    return x * {i} + {i}\n" for i in range(3000))
os.makedirs('bigsrc/bigmod'); open('bigsrc/bigmod/__init__.py', 'w').write(big)
mkzip('big_src.zip', [('bigmod/__init__.py', 'bigsrc/bigmod/__init__.py')])
py_compile.compile('bigsrc/bigmod/__init__.py', cfile='bigsrc/bigmod/__init__.pyc', doraise=True)
mkzip('big_pyc.zip', [('bigmod/__init__.pyc', 'bigsrc/bigmod/__init__.pyc')])
subprocess.run([sys.executable, '-c', "import sys; sys.path.insert(0,'bigsrc'); import bigmod"], check=True)  # 预热 pycache
print("源文件行数:", big.count('\n'), "| big_src.zip 大小:", os.path.getsize('big_src.zip'), "字节 | big_pyc.zip:", os.path.getsize('big_pyc.zip'), "字节")
def t(path):
    code = f"import time,sys; sys.path.insert(0,{path!r}); t=time.perf_counter(); import bigmod; print((time.perf_counter()-t)*1000)"
    return sorted(float(subprocess.run([sys.executable, '-c', code], capture_output=True, text=True).stdout) for _ in range(9))[4]
res_ = {}
for name, p in (("目录 + __pycache__", 'bigsrc'), ("zip 里放 .py", 'big_src.zip'), ("zip 里放 .pyc", 'big_pyc.zip')):
    res_[name] = t(p); print(f"  {name:<20} import 用时(9 次取中位数): {res_[name]:7.2f} ms")
print("zip 里放 .py 之后再跑, zip 内容有变化吗?", sorted(zipfile.ZipFile('big_src.zip').namelist()))
json.dump(res_, open(os.environ.get('OUTJSON', '/dev/null'), 'w'))

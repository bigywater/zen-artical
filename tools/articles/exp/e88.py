import importlib, importlib.util, importlib.machinery, sys, os, tempfile, json, types, time

W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W); sys.path.insert(0, W)
def write(name, body): open(f"{name}.py", "w").write(body)

print("== 一、按字符串导入: import_module vs __import__ ==")
m = importlib.import_module("json.decoder")
print("  importlib.import_module('json.decoder') →", m.__name__)
r = __import__("json.decoder")
print("  __import__('json.decoder') 返回的是顶层包:", r.__name__, "| fromlist=['x'] 之后返回:", __import__("json.decoder", fromlist=["x"]).__name__)
print("  相对导入需要 package 参数:", importlib.import_module(".encoder", package="json").__name__)
try: importlib.import_module("no_such_plugin")
except ModuleNotFoundError as e: print("  不存在的模块 →", type(e).__name__ + ":", e, "| e.name =", e.name)

print("\n== 二、reload: 模块对象还是那个, 但只更新了自己的字典 ==")
write("cfg", "VALUE = 1\nclass K: pass\n")
import cfg
old_id = id(cfg); old_K = cfg.K; k_inst = cfg.K()
from cfg import VALUE as imported_value
write("cfg", "VALUE = 2\nclass K: pass\nNEW = 'only in v2'\n")
importlib.reload(cfg)
print("  reload 前后 id(cfg) 相同?", id(cfg) == old_id, "| cfg.VALUE =", cfg.VALUE, "| cfg.NEW =", cfg.NEW)
print("  但先前 from cfg import VALUE 的那个名字还是:", imported_value, "(旧值)")
print("  旧的类对象 old_K is cfg.K?", old_K is cfg.K, "| 旧实例 isinstance(k_inst, cfg.K)?", isinstance(k_inst, cfg.K), " ← reload 之后旧实例不再是新类的实例")

print("\n== 三、reload 不会删除已经不存在的名字 ==")
write("cfg2", "A = 1\nB = 2\n"); import cfg2
write("cfg2", "A = 10\n"); importlib.reload(cfg2)
print("  文件里已经删掉 B, reload 后 hasattr(cfg2, 'B') =", hasattr(cfg2, 'B'), "(旧名字残留)")

print("\n== 四、从任意路径加载一个文件, 不经过 sys.path ==")
os.makedirs("plugins"); open("plugins/my-plugin.py", "w").write("NAME = '我是插件'\ndef run(): return 'run 被调用'\n")
spec = importlib.util.spec_from_file_location("myplugin", "plugins/my-plugin.py")
mod = importlib.util.module_from_spec(spec)
print("  module_from_spec 之后, 代码执行了吗?", hasattr(mod, "NAME"), "| 已经在 sys.modules 里吗?", "myplugin" in sys.modules)
spec.loader.exec_module(mod)
print("  exec_module 之后: mod.NAME =", mod.NAME, "| mod.run() =", mod.run(), "| 在 sys.modules 里吗?", "myplugin" in sys.modules)
print("  文件名 my-plugin.py 里有连字符, 用普通 import 写不出来, 用这种方式没问题")

print("\n== 五、find_spec: 不执行就知道模块在哪 ==")
for n in ("json", "os.path", "cfg", "no_such_plugin", "numpy_not_installed"):
    s = importlib.util.find_spec(n)
    print(f"  find_spec({n!r:<22}) →", (s.origin.replace(W, '<工作目录>') if s and s.origin else s))
before = "colorsys" in sys.modules; importlib.util.find_spec("colorsys")
print(f"  colorsys 还没导入过。find_spec 之前 in sys.modules = {before}, 之后 = {'colorsys' in sys.modules} (只查找, 不执行)")

print("\n== 六、reload 的副作用: 模块级代码会再执行一次 ==")
write("counter", "import builtins\nbuiltins._counter_runs = getattr(builtins, '_counter_runs', 0) + 1\nprint('  [counter.py 被执行, 第', builtins._counter_runs, '次]')\n")
import counter
importlib.reload(counter); importlib.reload(counter)

print("\n== 七、延迟导入: 只在真正用到时才导入 ==")
import importlib.util as iu
def lazy(name):
    spec = iu.find_spec(name); loader = iu.LazyLoader(spec.loader); spec.loader = loader
    module = iu.module_from_spec(spec); sys.modules[name] = module; loader.exec_module(module); return module
write("heavy", "import time; time.sleep(0.3)\nprint('  [heavy 模块顶层代码开始执行]')\nVALUE = 42\n")
t = time.perf_counter(); h = lazy("heavy"); t1 = (time.perf_counter() - t) * 1000
print(f"  lazy('heavy') 返回用时 {t1:.2f} ms, 模块顶层代码执行了吗? (上面没有出现 [heavy ...] 就是没有)")
t = time.perf_counter(); v = h.VALUE; t2 = (time.perf_counter() - t) * 1000
print(f"  第一次访问 h.VALUE = {v}, 用时 {t2:.1f} ms  ← 这时才真正执行了模块")
json.dump({'t': [t1, t2]}, open(os.path.join(os.environ.get('HERE', '.'), 'out/88.json'), 'w'))

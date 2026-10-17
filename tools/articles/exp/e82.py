import dis, time, json, sys, os, traceback

print("== 一、三种 mode ==")
for mode, s in (("eval", "1 + 2"), ("eval", "x = 1"), ("exec", "x = 1\ny = x + 1"), ("single", "1 + 2"), ("single", "x = 5")):
    try:
        c = compile(s, "<demo>", mode); print(f"  compile({s!r:<18}, mode={mode!r:<8}) → 成功, co_names={c.co_names}, co_consts={c.co_consts}")
    except SyntaxError as e: print(f"  compile({s!r:<18}, mode={mode!r:<8}) → SyntaxError: {e.msg}")
print("  eval('1 + 2') 返回:", eval("1 + 2"), "| exec('1 + 2') 返回:", exec("1 + 2"))
print("  mode='single' 执行表达式语句会像交互式解释器那样打印:")
exec(compile("1 + 2", "<demo>", "single"))

print("\n== 二、命名空间:代码写进了哪个字典 ==")
ns = {}
exec("x = 10\ndef f(): return x * 2", ns)
print("  exec 之后 ns 里的键:", [k for k in ns])
print("  ns['__builtins__'] 的类型:", type(ns['__builtins__']).__name__, "(exec 自动塞进去的)")
print("  ns['f']() =", ns['f']())
def in_func():
    exec("z = 99")
    try: return z
    except NameError as e: return f"NameError: {e}"
print("  在函数里 exec('z = 99') 然后读 z →", in_func())
def in_func2():
    d = {}
    exec("z = 99", globals(), d); return d
print("  给 exec 传一个显式 locals 字典 →", in_func2())

print("\n== 三、空 __builtins__ 不是沙箱 ==")
try: exec("print('hi')", {"__builtins__": {}})
except NameError as e: print("  exec('print(...)', {'__builtins__': {}}) → NameError:", e)
escape = "[c for c in ().__class__.__base__.__subclasses__() if c.__name__ == 'catch_warnings'][0]()._module.__builtins__['__import__']('os').getpid()"
r = eval(escape, {"__builtins__": {}})
print("  仍然没有任何内置名字, 却通过对象的类关系拿回了 __import__ 并调用了 os.getpid() →", r, "| 与当前进程 pid 相同?", r == os.getpid())
print("  ().__class__.__base__.__subclasses__() 里有 %d 个类可以被脚本摸到" % len(eval("().__class__.__base__.__subclasses__()", {"__builtins__": {}})))

print("\n== 四、code 对象里有什么 ==")
def add(a, b=2):
    c = a + b
    return c * 2
co = add.__code__
print("  co_argcount =", co.co_argcount, "| co_varnames =", co.co_varnames, "| co_consts =", co.co_consts, "| co_names =", co.co_names, "| co_filename =", os.path.basename(co.co_filename), "| co_firstlineno =", co.co_firstlineno)
print("  co_code 前 8 字节:", co.co_code[:8].hex(), " → 字节码是 bytes")
co2 = compile("v = 6 * 7", "<calc>", "exec"); ns2 = {}; exec(co2, ns2); print("  exec(code) →", ns2['v'])

print("\n== 五、文件名出现在回溯里 ==")
try: exec(compile("a = 1\nb = 1 / 0", "<用户配置第3行>", "exec"))
except ZeroDivisionError:
    for l in traceback.format_exc().splitlines():
        if l.strip().startswith('File "<用户配置第3行>"') or l.startswith("ZeroDivisionError"): print("  " + l.strip())
try: compile("x = = 1", "<用户配置>", "exec")
except SyntaxError as e: print("  SyntaxError 里的文件名/行号:", e.filename, e.lineno)

print("\n== 六、optimize 参数与 assert ==")
for lvl in (0, 1):
    try:
        exec(compile("assert 1 == 2, 'boom'\nprint('  optimize=%d: assert 之后的代码执行了')" % lvl, "<a>", "exec", optimize=lvl))
    except AssertionError as e: print(f"  optimize={lvl}: AssertionError: {e}")

print("\n== 七、每次 eval(字符串) 都要重新编译 ==")
N = 50000; expr = "a * 2 + b * 3 - (a + b) // 7"
env = {"a": 5, "b": 9}
t = time.perf_counter()
for _ in range(N): eval(expr, env)
t_str = (time.perf_counter() - t) / N * 1e9
code = compile(expr, "<e>", "eval"); t = time.perf_counter()
for _ in range(N): eval(code, env)
t_code = (time.perf_counter() - t) / N * 1e9
t = time.perf_counter()
for _ in range(N): env["a"] * 2 + env["b"] * 3 - (env["a"] + env["b"]) // 7
t_native = (time.perf_counter() - t) / N * 1e9
print(f"  eval(字符串) {t_str:8.0f} ns/次 | eval(预编译 code) {t_code:8.0f} ns/次 | 直接写成 Python 表达式 {t_native:8.0f} ns/次")

print("\n== 八、逐条 exec, 观察命名空间 ==")
stmts = ["x = 3", "y = x * 2", "def sq(n): return n * n", "z = sq(y)"]
ns3 = {}; snaps = []
for s in stmts:
    exec(s, ns3); snaps.append({k: (v if not callable(v) else '<function %s>' % v.__name__) for k, v in ns3.items() if k != '__builtins__'})
    print(f"  exec({s!r:<26}) → ns = {snaps[-1]}")
print("  eval('z + 1', ns) =", eval("z + 1", ns3))
json.dump({'stmts': stmts, 'snaps': snaps, 'ev': eval("z + 1", ns3), 't': [t_str, t_code, t_native]}, open('out/82.json', 'w'), ensure_ascii=False, default=str)

import concurrent.interpreters as interpreters
from concurrent.futures import InterpreterPoolExecutor, ThreadPoolExecutor, ProcessPoolExecutor
import sys, time, threading, json, os, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w92mod
from w92mod import work, noop, echo, Bar

def main():
    print("== 一、创建、隔离 ==")
    main = interpreters.get_main()
    t = time.perf_counter(); it = interpreters.create(); dt = (time.perf_counter() - t) * 1000
    print(f"  main = {main}, interpreters.create() 用时 {dt:.2f} ms → {it}")
    print("  list_all():", interpreters.list_all())
    X = "主解释器的全局变量"
    it.exec("Y = '子解释器里的全局变量'; import sys; sys.my_flag = True; sys_id = id(sys)")
    print("  子解释器里定义的 Y, 主解释器能看到吗?", 'Y' in globals())
    print("  子解释器给 sys 加的属性, 主解释器的 sys 有吗?", hasattr(sys, 'my_flag'))
    it.exec("import builtins; seen = 'X' in globals()")
    r = it.call(eval, "'X' in globals()") if False else None
    def probe(): return 'X' in globals()
    print("  子解释器看得到主解释器的全局变量 X 吗?", it.call(probe))
    print("  sys.modules 是各自独立的: 主解释器 len =", len(sys.modules), "| 子解释器 len =", it.call(lambda: len(__import__('sys').modules)))

    print("\n== 二、跨解释器传参和返回值: 能传什么 ==")
    class Foo: pass
    for label, v in (("int 42", 42), ("str", "hello"), ("bytes", b"ab"), ("tuple (1, 'a')", (1, 'a')), ("None", None), ("list [1, 2]", [1, 2]), ("dict", {'a': 1}), ("object()", object()), ("lambda", lambda: 1), ("主脚本里定义的类 Foo()", Foo()), ("模块里定义的类 Bar()", Bar()), ("threading.Lock()", threading.Lock()), ("打开的文件", open(os.devnull))):
        try: got = it.call(echo, v); print(f"  it.call(echo, {label:<16}) → 成功, 返回 {got!r:.60}  (is_shareable={interpreters.is_shareable(v)})")
        except Exception as e: print(f"  it.call(echo, {label:<16}) → {type(e).__name__}: {str(e).splitlines()[0][:70]}")
    print("\n== 二·补、子解释器 __main__ 里看不到主解释器定义的函数 ==")
    def local_fn(): return 1
    try: print("  it.call(在 main() 里定义的 local_fn) → 成功", interpreters.create().call(local_fn))
    except Exception as e: print("  it.call(在 main() 里定义的 local_fn) →", type(e).__name__ + ":", str(e).splitlines()[0][:90])
    print("  it.call(w92mod.noop)(定义在可导入模块里) →", interpreters.create().call(noop))
    try: interpreters.create().exec("print(work)")
    except interpreters.ExecutionFailed as e: print("  子解释器 exec('print(work)') → ExecutionFailed:", e.excinfo.msg)

    print("\n== 三、子解释器里出错 ==")
    try: it.exec("1 / 0")
    except interpreters.ExecutionFailed as e: print("  exec('1 / 0') → ExecutionFailed;  e.excinfo.type =", e.excinfo.type, "| msg =", e.excinfo.msg)
    print("  出错之后子解释器仍可用:", it.call(lambda: 'still alive'))
    it.close()

    print("\n== 四、CPU 密集任务: 线程 / 子解释器 / 进程 ==")
    def timeit(make, n, reps=3):
        best = 1e9
        for _ in range(reps):
            t = time.perf_counter()
            with make(max_workers=n) as ex:
                list(ex.map(work, [3_000_000] * n))
            best = min(best, time.perf_counter() - t)
        return best
    t = time.perf_counter()
    for _ in range(4): work()
    seq = time.perf_counter() - t
    print(f"  串行做 4 份: {seq*1000:.1f} ms")
    res = {}
    for name, make in (("ThreadPoolExecutor", ThreadPoolExecutor), ("InterpreterPoolExecutor", InterpreterPoolExecutor), ("ProcessPoolExecutor", ProcessPoolExecutor)):
        res[name] = timeit(make, 4)
        print(f"  {name:<24} 4 个 worker 做 4 份: {res[name]*1000:7.1f} ms  → 相对串行加速 {seq/res[name]:.2f}x")

    print("\n== 五、启动一个 worker 的成本 ==")
    ts = {}
    t = time.perf_counter()
    for _ in range(20): i2 = interpreters.create(); i2.call(noop); i2.close()
    ts['create+call+close 一个子解释器'] = (time.perf_counter() - t) / 20 * 1000
    t = time.perf_counter()
    for _ in range(20):
        th = threading.Thread(target=noop); th.start(); th.join()
    ts['创建并等待一个线程'] = (time.perf_counter() - t) / 20 * 1000
    ctx = mp.get_context('spawn'); t = time.perf_counter()
    for _ in range(5): p = ctx.Process(target=noop); p.start(); p.join()
    ts['spawn 一个进程(macOS 默认)'] = (time.perf_counter() - t) / 5 * 1000
    for k, v in ts.items(): print(f"  {k:<28} {v:8.2f} ms")
    json.dump({'seq': seq, 'res': res, 'ts': ts}, open('out/92.json', 'w'), ensure_ascii=False)

if __name__ == '__main__':
    main()

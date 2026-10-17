import atexit
def make(n):
    def f(*a, **k): print(f"  handler {n} 执行, 参数={a} {k}")
    f.__name__ = f"h{n}"; return f
atexit.register(make(1))
atexit.register(make(2), "x", k=1)
@atexit.register
def decorated(): print("  handler decorated 执行 (用装饰器注册)")
print("main 结束, 注册顺序: h1, h2, decorated")

import atexit
def f(): print("  f 执行")
def g(): print("  g 执行")
atexit.register(f); atexit.register(f); atexit.register(g)
print("注册后 handler 个数:", atexit._ncallbacks())
atexit.unregister(f)
print("unregister(f) 之后个数:", atexit._ncallbacks(), "(f 注册了两次, 一次全部移除)")

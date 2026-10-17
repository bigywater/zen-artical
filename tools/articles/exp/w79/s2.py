import atexit
@atexit.register
def a(): print("  a 执行")
@atexit.register
def boom(): raise RuntimeError("清理函数里出错了")
@atexit.register
def c(): print("  c 执行 (最后注册, 最先执行)")
print("main 结束")

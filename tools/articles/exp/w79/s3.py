import atexit
def late(): print("  late: 在退出阶段里注册的 handler 执行了")
@atexit.register
def first():
    print("  first 执行, 并在其中再注册 late")
    atexit.register(late)
print("main 结束")

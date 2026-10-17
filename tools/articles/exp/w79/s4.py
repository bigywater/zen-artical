import atexit, threading, time
T0 = time.time()
def log(m): print(f"  [{time.time()-T0:4.2f}s] {m}", flush=True)
def nd():
    time.sleep(0.6); log("非守护线程 干完活")
def dm():
    for i in range(30):
        time.sleep(0.1)
    log("守护线程 干完活 (如果看到这行说明它没被杀)")
threading.Thread(target=nd).start()
threading.Thread(target=dm, daemon=True).start()
atexit.register(lambda: log("atexit handler 执行"))
log("main 函数返回")

import socket, sys, time, errno, os

events = []
def hook(ev, args):
    if ev.startswith('socket.'):
        a = ['<socket fd=%d>' % x.fileno() if isinstance(x, socket.socket) else repr(x) for x in args]
        events.append(f"{ev}({', '.join(a)})")
sys.addaudithook(hook)
T0 = time.time()
marks = []
def stage(name, pause=0.7):
    marks.append((time.time(), name)); print(f"[{time.time()-T0:5.2f}s] {name}"); sys.stdout.flush(); time.sleep(pause)

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("srv.fileno() =", srv.fileno(), "| family =", srv.family.name, "| type =", srv.type.name)
srv.bind(('127.0.0.1', 0)); port = srv.getsockname()[1]
open(os.environ['PORTFILE'], 'w').write(str(port))
time.sleep(0.6)
stage(f"S1 bind 完成, 端口 {port}, 还没 listen")
srv.listen(5)
stage("S2 srv.listen(5) 之后")
cli = socket.socket(); t = time.perf_counter()
cli.connect(('127.0.0.1', port)); dt = (time.perf_counter()-t)*1000
print(f"     cli.connect() 返回耗时 {dt:.3f} ms, cli fd={cli.fileno()}, 本端={cli.getsockname()}, 对端={cli.getpeername()}")
stage("S3 cli.connect() 已返回, 但服务端从未调用 accept()")
conn, addr = srv.accept()
print(f"     srv.accept() -> {addr}, 新 fd={conn.fileno()} (监听 fd={srv.fileno()})")
stage("S4 srv.accept() 之后")
for m in (b"hello|", b"world|", b"tcp!"):
    print(f"     cli.send({m!r}) 返回 {cli.send(m)}")
time.sleep(0.1)
data = conn.recv(4096)
print(f"     conn.recv(4096) 一次拿到 {data!r}")
stage("S5 数据收发后")
cli.close()
stage("S6 客户端 cli.close() 之后 (服务端 conn 还开着)")
print(f"     conn.recv(10) -> {conn.recv(10)!r}  (b'' 即 EOF)")
conn.close()
stage("S7 服务端 conn.close() 之后", 1.0)
srv.close()
stage("S8 监听 socket 也关掉之后", 1.2)
try:
    socket.create_connection(('127.0.0.1', port), timeout=2)
except OSError as e:
    print(f"     无人监听时 connect: {type(e).__name__} errno={e.errno} {errno.errorcode[e.errno]} - {e.strerror}")
print("--- 审计钩子看到的 socket 事件 ---")
for e in events: print(e)
import json; json.dump(marks, open(os.environ['MARKFILE'], 'w'))

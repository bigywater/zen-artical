"""独立进程:建立 N 个订阅连接并持续排空(用 selectors,避免测量进程被拖慢)。"""
import sys, socket, selectors, time
port, N, chan = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
sel = selectors.DefaultSelector()
cmd = b'*2\r\n$9\r\nSUBSCRIBE\r\n$%d\r\n%s\r\n' % (len(chan), chan.encode())
for _ in range(N):
    s = socket.create_connection(('127.0.0.1', port)); s.sendall(cmd); s.setblocking(False); sel.register(s, selectors.EVENT_READ)
print('ready', flush=True)
while True:
    for k, _ in sel.select(1):
        try: k.fileobj.recv(1 << 20)
        except BlockingIOError: pass

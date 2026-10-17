import socket, sys, time
port = int(sys.argv[1]); log = open(sys.argv[2], 'a', buffering=1)
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('0.0.0.0', port)); s.listen(64)
if len(sys.argv) > 3 and sys.argv[3] == 'tfo': s.setsockopt(socket.IPPROTO_TCP, socket.TCP_FASTOPEN, 16)
while True:
    c, a = s.accept(); c.settimeout(2)
    try:
        d = c.recv(100); log.write(f'{time.time():.3f} {d.decode()}\n'); c.sendall(b'R' * 10); c.recv(10)
    except Exception as e: log.write(f'{time.time():.3f} ERR {e!r}\n')
    c.close()

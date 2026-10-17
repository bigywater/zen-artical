import socket, sys
s = socket.create_connection((sys.argv[1], 5201), timeout=20); m0 = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG)
s.sendall(b'x' * 10_000_000); m1 = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG); s.shutdown(socket.SHUT_WR); s.settimeout(5)
try: s.recv(1)
except Exception: pass
print(m0, m1)

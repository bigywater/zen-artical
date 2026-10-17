import socket
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('0.0.0.0', 5201)); s.listen(8)
while True:
    c, _ = s.accept()
    while c.recv(1 << 20): pass
    c.close()

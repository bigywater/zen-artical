import sys, os, time, socket, threading, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import client
from kazoo.exceptions import NodeExistsError
zport, port, mode = sys.argv[1], int(sys.argv[2]), sys.argv[3]
z = client(f'127.0.0.1:{zport}', timeout=3); path = f'/svc/orders/127.0.0.1:{port}'
def reg():
    try: z.create(path, json.dumps({'port': port, 'weight': 1}).encode(), ephemeral=True, makepath=True)
    except NodeExistsError: pass
reg()
if mode == 'rereg_sync': z.add_listener(lambda s: reg() if str(s) == 'CONNECTED' else None)
if mode == 'rereg_thread': z.add_listener(lambda s: threading.Thread(target=reg).start() if str(s) == 'CONNECTED' else None)
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(('127.0.0.1', port)); srv.listen(100)
while True:
    c, _ = srv.accept()
    try: c.recv(100); c.sendall(b'ok')
    except Exception: pass
    c.close()

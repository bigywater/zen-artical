import socket, sys, time
mode, host, port, n, gap = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5]); tag = sys.argv[6] if len(sys.argv) > 6 else 'msg'
for i in range(n):
    s = socket.socket(); t0 = time.time(); data = f'{tag}{i}'.encode()
    try:
        if mode == 'tfo': s.sendto(data, socket.MSG_FASTOPEN, (host, port))
        else: s.connect((host, port)); s.sendall(data)
        s.settimeout(15); s.recv(20); print(i, round((time.time() - t0) * 1000, 1), flush=True)
    except Exception as e: print(i, 'ERR', repr(e), round((time.time() - t0) * 1000, 1), flush=True)
    s.close(); time.sleep(gap)

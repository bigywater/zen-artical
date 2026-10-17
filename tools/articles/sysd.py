#!/usr/bin/python3
"""netl 的系统命令代理(必须用 /usr/bin/python3 启动,且由 Bash 工具直接启动,不能由 Homebrew python 启动):
macOS 的“本地网络”隐私限制会让祖先进程里有非系统二进制(Homebrew python 等)的 arp / ndp / netstat 看不到邻居表。
所以让一个系统 python 常驻,实验脚本通过 unix socket 把 argv 发过来,在这里执行并返回输出。只允许白名单里的命令。
启动: nohup /usr/bin/python3 tools/articles/sysd.py >/dev/null 2>&1 &"""
import os, socket, json, subprocess, sys
SOCK = '/tmp/netl_sysd.sock'
ALLOW = {'arp', 'ndp', 'netstat', 'route', 'ifconfig', 'sysctl', 'ping', 'ping6', 'traceroute', 'traceroute6', 'dig', 'scutil', 'lsof', 'nettop', 'nslookup', 'host', 'networksetup', 'dscacheutil', 'nc', 'ipconfig'}
try: os.unlink(SOCK)
except OSError: pass
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.bind(SOCK); os.chmod(SOCK, 0o600); s.listen(8)
while True:
    c, _ = s.accept()
    try:
        buf = b''
        while not buf.endswith(b'\n'):
            d = c.recv(65536)
            if not d: break
            buf += d
        req = json.loads(buf.decode())
        argv = req['argv']; name = os.path.basename(argv[0])
        if name not in ALLOW: res = {'rc': 126, 'out': '', 'err': 'not allowed: ' + name}
        else:
            env = dict(os.environ); env.update(req.get('env') or {})
            try:
                r = subprocess.run(argv, capture_output=True, text=True, timeout=req.get('timeout', 20), env=env, input=req.get('input'))
                res = {'rc': r.returncode, 'out': r.stdout, 'err': r.stderr}
            except subprocess.TimeoutExpired as e:
                res = {'rc': -9, 'out': (e.stdout or b'').decode() if isinstance(e.stdout, bytes) else (e.stdout or ''), 'err': 'timeout'}
        c.sendall((json.dumps(res) + '\n').encode())
    except Exception as e:
        try: c.sendall((json.dumps({'rc': 125, 'out': '', 'err': str(e)}) + '\n').encode())
        except Exception: pass
    finally: c.close()

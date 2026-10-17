import sys, os, re, time, subprocess, tarfile, io, threading, http.server, socketserver, hashlib, zipfile; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c4')
img('alpine:3.20')
purge()
def mk_tar(path, compress):
    with tarfile.open(path, 'w:gz' if compress else 'w') as t:
        for name, data in (('hello/a.txt', b'A\n'), ('hello/b.txt', b'B\n')):
            ti = tarfile.TarInfo(name); ti.size = len(data); ti.mode = 0o644; t.addfile(ti, io.BytesIO(data))
def ls_image(tag, path):
    rc, o = dk('run', '--rm', *LAB, tag, 'sh', '-c', f'find {path} -maxdepth 3 | sort; echo ---; ls -la {path} 2>&1 | head -8')
    return o
files = {'app.txt': 'app\n'}
d = ctx('c4a', files)
mk_tar(d / 'pack.tar', False); mk_tar(d / 'pack.tar.gz', True)
with zipfile.ZipFile(d / 'pack.zip', 'w') as z: z.writestr('hello/a.txt', 'A\n')
print('== 一:COPY 与 ADD 对本地压缩包的处理(Docker Engine 29.8.2,BuildKit)')
df = '''FROM alpine:3.20
COPY pack.tar /copy/
COPY pack.tar.gz /copy/
COPY pack.zip /copy/
ADD pack.tar /add/
ADD pack.tar.gz /add/
ADD pack.zip /add/
'''
(d / 'Dockerfile').write_text(df)
rc, o = build(d, 'bwlab-c4a')
print(f'  构建退出码 {rc}')
rc, o = dk('run', '--rm', *LAB, 'bwlab-c4a', 'sh', '-c', 'echo "[COPY 的结果 /copy]"; find /copy | sort; echo "[ADD 的结果 /add]"; find /add | sort')
for l in o.split('\n'): print('  ' + l)
print('== 二:ADD 目录、COPY 目录的结果相同吗;文件权限和属主')
d2 = ctx('c4b', {'dir/x.txt': 'x\n', 'dir/sub/y.sh': '#!/bin/sh\necho y\n', 'run.sh': '#!/bin/sh\necho hi\n'})
os.chmod(d2 / 'run.sh', 0o755); os.chmod(d2 / 'dir/x.txt', 0o640)
(d2 / 'Dockerfile').write_text('FROM alpine:3.20\nCOPY dir /c/dir\nADD dir /a/dir\nCOPY run.sh /c/run.sh\nCOPY --chmod=0600 --chown=1000:1000 run.sh /c/run600.sh\n')
rc, o = build(d2, 'bwlab-c4b')
rc, o = dk('run', '--rm', *LAB, 'bwlab-c4b', 'sh', '-c', 'cd /; ls -ln /c/dir/x.txt /a/dir/x.txt /c/run.sh /c/run600.sh | sed "s/  */ /g"; diff -r /c/dir /a/dir && echo "COPY dir 与 ADD dir 的内容完全相同"')
for l in o.split('\n'): print('  ' + l)
print('== 三:ADD 远程 URL(守护进程去下载):在宿主机起一个本地 HTTP 服务,让构建去取')
port = free_port()
srv_dir = DT / 'c4_www'; srv_dir.mkdir(exist_ok=True)
payload = b'remote file\n' * 100
(srv_dir / 'data.txt').write_bytes(payload)
mk_tar(srv_dir / 'remote.tar.gz', True)
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(srv_dir), **k)
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('0.0.0.0', port), Q); threading.Thread(target=httpd.serve_forever, daemon=True).start()
sha = hashlib.sha256(payload).hexdigest()
d3 = ctx('c4c', {'Dockerfile': f'FROM alpine:3.20\nADD http://host.docker.internal:{port}/data.txt /remote/data.txt\nADD http://host.docker.internal:{port}/remote.tar.gz /remote/\n'})
rc, o = build(d3, 'bwlab-c4c')
print(f'  构建退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if 'ERROR' in l or 'DONE' in l and 'ADD' in l)[:200])
if rc == 0:
    rc, o = dk('run', '--rm', *LAB, 'bwlab-c4c', 'sh', '-c', 'ls -ln /remote | sed "s/  */ /g"; echo ---; file /remote/remote.tar.gz 2>/dev/null || head -c 4 /remote/remote.tar.gz | od -An -tx1')
    for l in o.split('\n'): print('  ' + l)
d4 = ctx('c4d', {'Dockerfile': f'FROM alpine:3.20\nADD --checksum=sha256:{sha} http://host.docker.internal:{port}/data.txt /ok.txt\n'})
rc, o = build(d4, 'bwlab-c4d')
print(f'  [--checksum 正确] 退出码 {rc}')
d5 = ctx('c4e', {'Dockerfile': f'FROM alpine:3.20\nADD --checksum=sha256:{"0" * 64} http://host.docker.internal:{port}/data.txt /bad.txt\n'})
rc, o = build(d5, 'bwlab-c4e')
print(f'  [--checksum 错误] 退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if 'digest' in l or 'checksum' in l.lower())[:260])
httpd.shutdown()
purge()

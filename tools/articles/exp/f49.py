import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f49'); R = {}
import hashlib
from flask import Flask, Response, request, send_file, abort
from werkzeug.http import parse_range_header
d = mkapp('f49', {'app.py': '''
import re, os
from flask import Flask, Response, request, send_file, abort
app = Flask(__name__)
@app.get("/file")
def f(): return send_file("data.bin", conditional=True)
@app.get("/gen")
def gen():
    def g():
        for i in range(10): yield bytes([65 + i]) * 100
    return Response(g(), mimetype="application/octet-stream")
@app.get("/custom")
def custom():
    path = "data.bin"; size = os.path.getsize(path); rng = request.range
    if rng is None or rng.units != "bytes" or len(rng.ranges) != 1: return send_file(path, conditional=False)
    start, end = rng.range_for_length(size) or (None, None)
    if start is None: return Response(status=416, headers={"Content-Range": f"bytes */{size}"})
    with open(path, "rb") as fh: fh.seek(start); body = fh.read(end - start)
    r = Response(body, 206, mimetype="application/octet-stream"); r.headers["Content-Range"] = f"bytes {start}-{end - 1}/{size}"; r.headers["Accept-Ranges"] = "bytes"; return r
'''})
(d / 'data.bin').write_bytes(bytes(range(256)) * 40)  # 10240 字节
data = (d / 'data.bin').read_bytes(); N = len(data)
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '--workers', '1', 'app:app']) as s:
    def curl(args, path='/file', body=False):
        r = subprocess.run(['curl', '-s', '-i' if not body else '-s', *args, f'http://127.0.0.1:{s.port}{path}'], capture_output=True); return r.stdout
    def rq(rng=None, path='/file', extra=None):
        h = {'Range': rng} if rng else {}; h.update(extra or {}); st, hd, b, dt = s.get(path, headers=h); H = {k: v for k, v in hd}; return st, H, b
    print(f'== 一:send_file 的 Range 支持(文件 {N} 字节,内容是 0..255 循环 40 遍)')
    st, H, b = rq(); print('  无 Range:', st, '| Accept-Ranges =', H.get('Accept-Ranges'), '| Content-Length =', H.get('Content-Length')); R['full'] = [st, H.get('Accept-Ranges'), H.get('Content-Length')]
    R['rows'] = {}
    for rng in ('bytes=0-99', 'bytes=100-199', 'bytes=-50', 'bytes=10000-', 'bytes=0-0', 'bytes=10239-10239', 'bytes=0-999999', 'bytes=10240-', 'bytes=20000-30000', 'bytes=5-2', 'bytes=0-9,20-29', 'items=0-5', 'bytes=abc'):
        st, H, b = rq(rng); ok = (b == data[int(rng.split('=')[1].split('-')[0]):int(rng.split('=')[1].split('-')[1]) + 1]) if st == 206 and rng.startswith('bytes=') and rng.split('=')[1].split('-')[0].isdigit() and rng.split('=')[1].split('-')[1].isdigit() and ',' not in rng else None
        R['rows'][rng] = [st, H.get('Content-Range'), H.get('Content-Length'), len(b), ok]; print(f'  Range: {rng:<20} → {st} | Content-Range: {H.get("Content-Range")} | 收到 {len(b):>5} 字节' + ('' if ok is None else f' | 内容与文件对应片段一致:{ok}'))
    print()
    print('== 二:If-Range:条件 Range——文件没变就返回片段,变了就返回完整内容(用 ETag 或 Last-Modified 做条件)')
    st, H, b = rq(); etag = H['ETag']; lm = H['Last-Modified']
    for label, ir in (('If-Range = 当前 ETag', etag), ('If-Range = 过期的 ETag', '"stale"'), ('If-Range = 当前 Last-Modified', lm)):
        st, H2, b2 = rq('bytes=0-9', extra={'If-Range': ir}); R.setdefault('ifrange', {})[label] = [st, len(b2)]; print(f'  Range: bytes=0-9 + {label:<28} → {st} 收到 {len(b2)} 字节')
    print()
    print('== 三:断点续传:先下载前 3000 字节,再用 curl -C - 续传,最后比较完整文件的 SHA-256')
    out = d / 'dl.bin'; out.unlink(missing_ok=True)
    r1 = subprocess.run(['curl', '-s', '-r', '0-2999', '-o', str(out), f'http://127.0.0.1:{s.port}/file']); print('  第一次(只取 0-2999)文件大小:', out.stat().st_size)
    r2 = subprocess.run(['curl', '-s', '-C', '-', '-o', str(out), '-w', '%{http_code} 本次传输 %{size_download} 字节', f'http://127.0.0.1:{s.port}/file'], capture_output=True, text=True); print('  curl -C - 续传:', r2.stdout.strip(), '| 最终文件大小', out.stat().st_size)
    ok = hashlib.sha256(out.read_bytes()).hexdigest() == hashlib.sha256(data).hexdigest(); print('  SHA-256 与原文件相同:', ok); R['resume'] = [r2.stdout.strip(), out.stat().st_size, ok]
    print()
    print('== 四:生成器响应不支持 Range(它没有 Accept-Ranges,Range 头被忽略,返回 200 完整内容);自己实现的 /custom 可以')
    st, H, b = rq('bytes=0-99', '/gen'); print('  /gen  Range: bytes=0-99 →', st, '| Accept-Ranges =', H.get('Accept-Ranges'), '| 收到', len(b), '字节'); R['gen'] = [st, H.get('Accept-Ranges'), len(b)]
    st, H, b = rq('bytes=100-199', '/custom'); print('  /custom Range: bytes=100-199 →', st, '| Content-Range =', H.get('Content-Range'), '| 收到', len(b), '字节 | 内容正确:', b == data[100:200]); R['custom'] = [st, H.get('Content-Range'), len(b), b == data[100:200]]
    st, H, b = rq('bytes=99999-', '/custom'); print('  /custom Range: bytes=99999- →', st, '| Content-Range =', H.get('Content-Range')); R['custom416'] = [st, H.get('Content-Range')]
    print()
    print('== 五:HEAD 与 Range:HEAD 请求带 Range')
    st, hd, b, _ = s.req('HEAD', '/file', headers={'Range': 'bytes=0-9'}); H = {k: v for k, v in hd}; print('  HEAD + Range: bytes=0-9 →', st, '| Content-Range =', H.get('Content-Range'), '| Content-Length =', H.get('Content-Length'), '| 正文', len(b)); R['head'] = [st, H.get('Content-Range'), H.get('Content-Length'), len(b)]
save('f49', R)

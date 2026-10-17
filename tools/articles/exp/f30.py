import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f30'); R = {}
import socket
from flask import Flask, request, url_for, redirect
a = Flask('uni'); a.logger.disabled = True
@a.route('/用户/<name>')
def user(name): return f'name={name!r} path={request.path!r} PATH_INFO={request.environ["PATH_INFO"]!r}'
@a.route('/files/<path:p>')
def files(p): return f'p={p!r}'
@a.route('/q')
def q(): return f'args={dict(request.args)!r} full_path={request.full_path!r} query_string={request.query_string!r} url={request.url!r}'
@a.route('/go')
def go(): return redirect('/目标/页 面?x=中文')
@a.route('/seg/<s>')
def seg(s): return f's={s!r}'
c = a.test_client()
print('== 一:路径里的中文:浏览器会发送百分号编码的 UTF-8;Flask 解码后视图里拿到的是 str')
R['p1'] = {}
for path in ('/%E7%94%A8%E6%88%B7/%E5%BC%A0%E4%B8%89', '/用户/张三', '/%e7%94%a8%e6%88%b7/ann'):
    r = c.get(path); R['p1'][path] = [r.status_code, r.get_data(as_text=True)]; print(f'  GET {path:<34} → {r.status_code} {r.get_data(as_text=True) if r.status_code == 200 else ""}')
print('  (WSGI 的 PATH_INFO 是把 UTF-8 字节按 latin-1 解成的 str,所以 environ 里看到的是乱码形式,Werkzeug 再把它还原)')
print()
print('== 二:查询字符串:+ 与 %20 都表示空格;%2B 才是加号;解码后的 args 与原始 query_string')
r = c.get('/q?name=a+b&x=%E4%B8%AD%E6%96%87&plus=1%2B1&sp=a%20b'); print('  ', r.get_data(as_text=True)); R['q'] = r.get_data(as_text=True)
print()
print('== 三:编码后的斜杠 %2F:在 string 段里与 path 段里的表现')
for path in ('/seg/a%2Fb', '/seg/a/b', '/files/a%2Fb', '/files/a/b'):
    r = c.get(path); R.setdefault('slash', {})[path] = [r.status_code, r.get_data(as_text=True)[:30]]; print(f'  GET {path:<16} → {r.status_code} {r.get_data(as_text=True)[:30] if r.status_code == 200 else ""}')
print()
print('== 四:不合法的 UTF-8:%FF、截断的序列')
for path in ('/seg/%FF', '/seg/%E4%B8', '/seg/%ZZ', '/seg/a%00b'):
    r = c.get(path); R.setdefault('bad', {})[path] = [r.status_code, r.get_data(as_text=True)[:60]]; print(f'  GET {path:<14} → {r.status_code} {r.get_data(as_text=True)[:60]!r}')
print()
print('== 五:url_for 与 redirect 的编码:生成百分号编码的 ASCII URL')
with a.test_request_context('/'):
    R['uf'] = [url_for('user', name='张三'), url_for('q', name='中文 空格&号', x='a/b')]; print('  url_for("user", name="张三") →', R['uf'][0]); print('  url_for("q", name="中文 空格&号", x="a/b") →', R['uf'][1])
r = c.get('/go'); print('  redirect("/目标/页 面?x=中文") → Location =', r.headers.get('Location')); R['loc'] = r.headers.get('Location')
print()
print('== 六:真实 HTTP:用 gunicorn 起服务,用原始套接字发一个没有编码的中文 URL(浏览器不会这么发,但脚本会)')
d = mkapp('f30', {'app.py': 'from flask import Flask, request\napp = Flask(__name__)\n@app.route("/用户/<name>")\ndef user(name): return f"name={name} len={len(name)}"\n'})
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    for label, raw in (('已编码', b'GET /%E7%94%A8%E6%88%B7/%E5%BC%A0%E4%B8%89 HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'), ('原始 UTF-8 字节', 'GET /用户/张三 HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'.encode()), ('原始 latin-1 非法字节', b'GET /\xe7\xff HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n')):
        sk = socket.create_connection(('127.0.0.1', s.port)); sk.sendall(raw); buf = b''
        while True:
            x = sk.recv(4096)
            if not x: break
            buf += x
        sk.close(); line = buf.split(b'\r\n')[0].decode(); body = buf.split(b'\r\n\r\n', 1)[1].decode('utf-8', 'replace')[:50]; R.setdefault('real', {})[label] = [line, body]; print(f'  {label:<22} → {line} | {body!r}')
save('f30', R)

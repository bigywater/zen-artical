import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f127'); R = {}
import http.client as hc
from flask import Flask, request, url_for, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
def mk(**cfg):
    a = Flask('h'); a.logger.disabled = True; a.config.update(cfg)
    @a.get('/info')
    def info(): return jsonify(host=request.host, link=url_for('info', _external=True))
    return a
def get(a, host, path='/info', **hdr):
    r = a.test_client().get(path, headers={'Host': host, **hdr}); return r.status_code, (r.get_json() if r.is_json else r.get_data(as_text=True)[:60].replace('\n', ' '))
print('== 一:默认:request.host 与 url_for(_external=True) 直接取自请求里的 Host 头')
a = mk(); R['default'] = {}
for h in ('example.com', 'other.test', 'example.com:8080'):
    r = get(a, h); print(f'  Host: {h:<18} → {r[0]} {r[1]}'); R['default'][h] = r
print('  (任何 Host 都被接受;生成密码重置链接、邮件里的绝对地址如果直接用 request.host / url_for(_external=True),地址就由请求方决定)')
print()
print('== 二:TRUSTED_HOSTS(Flask 3.1):只接受名单里的 Host')
a = mk(TRUSTED_HOSTS=['example.com', '.example.org']); R['trusted'] = {}
for h in ('example.com', 'example.com:8080', 'EXAMPLE.com', 'other.test', 'www.example.org', 'example.org', 'evil-example.com', ''):
    try: r = get(a, h) if h else get(a, '')
    except Exception as e: r = (type(e).__name__, str(e)[:60])
    print(f'  Host: {h!r:<20} → {r[0]} {str(r[1])[:70]}'); R['trusted'][h] = [r[0], str(r[1])[:90]]
print()
print('== 三:SERVER_NAME:设置后路由按这个域名匹配')
a = mk(SERVER_NAME='example.com'); R['server_name'] = {}
for h in ('example.com', 'other.test'):
    r = get(a, h); print(f'  SERVER_NAME=example.com,Host: {h:<12} → {r[0]} {str(r[1])[:70]}'); R['server_name'][h] = [r[0], str(r[1])[:90]]
with a.app_context(): print('  请求之外(应用上下文里)url_for(_external=True):', url_for('info', _external=True)); R['ctx_url'] = url_for('info', _external=True)
print()
print('== 四:不依赖 Host 生成外部链接:用配置里的固定基地址')
a = mk(); BASE = 'https://app.example.com'
@a.get('/link')
def link(): return jsonify(link=BASE + url_for('info'), host_based=url_for('info', _external=True))
r = a.test_client().get('/link', headers={'Host': 'other.test'}); print('  Host: other.test →', r.get_json()); R['fixed_base'] = r.get_json()
print()
print('== 五:反向代理后面:X-Forwarded-Host 只在用了 ProxyFix(x_host=1) 时才生效')
for label, wrap in (('没有 ProxyFix', False), ('ProxyFix(x_host=1)', True)):
    a = mk()
    if wrap: a.wsgi_app = ProxyFix(a.wsgi_app, x_host=1)
    r = get(a, 'internal:8000', **{'X-Forwarded-Host': 'public.example.com'}); print(f'  {label:<20} Host: internal:8000, X-Forwarded-Host: public.example.com → {r[1]}'); R.setdefault('xfh', {})[label] = r[1]
print('  (只有前面确实有会覆盖这个头的可信代理时才应该启用;否则客户端自己就能伪造)')
print()
print('== 六:真实 gunicorn:自定义 Host 头')
d = mkapp('f127', {'app.py': "from flask import Flask, request, jsonify, url_for\napp = Flask(__name__); app.config['TRUSTED_HOSTS'] = ['example.com']\n@app.get('/info')\ndef info(): return jsonify(host=request.host)\n"})
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    R['live'] = {}
    for h in ('example.com', 'other.test', f'127.0.0.1:{s.port}'):
        co = hc.HTTPConnection('127.0.0.1', s.port, timeout=5); co.putrequest('GET', '/info', skip_host=True); co.putheader('Host', h); co.endheaders(); r = co.getresponse(); b = r.read().decode().strip().replace('\n', ' ')[:70]; co.close()
        print(f'  Host: {h:<18} → {r.status} {b}'); R['live'][h] = r.status
save('f127', R)

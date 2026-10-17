import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f29'); R = {}
from flask import Flask, request, url_for
def build(**kw):
    a = Flask('sd', **kw); a.logger.disabled = True
    a.add_url_rule('/', 'www_index', lambda: 'www 首页')
    a.add_url_rule('/', 'api_index', lambda: 'api 首页', subdomain='api')
    a.add_url_rule('/', 'user_index', lambda user: f'用户 {user} 的站点', subdomain='<user>')
    return a
def probe(a, hosts, path='/'):
    c = a.test_client(); return {h: c.get(path, base_url=f'http://{h}').get_data(as_text=True).strip()[:40] if c.get(path, base_url=f'http://{h}').status_code == 200 else str(c.get(path, base_url=f'http://{h}').status_code) for h in hosts}
hosts = ['example.test', 'www.example.test', 'api.example.test', 'ann.example.test', 'a.b.example.test', 'other.test', 'localhost']
print('== 一:没有 SERVER_NAME(默认):子域名规则不会参与匹配')
a = build(); print('  规则:', [(str(r), r.endpoint, r.subdomain) for r in a.url_map.iter_rules() if r.endpoint != 'static']); R['rules'] = [(str(r), r.endpoint, r.subdomain) for r in a.url_map.iter_rules() if r.endpoint != 'static']
R['nosn'] = probe(a, hosts); [print(f'  Host {h:<20} → {v}') for h, v in R['nosn'].items()]
print()
print('== 二:只设置 SERVER_NAME、不开 subdomain_matching(默认 False):子域名规则仍然不参与匹配')
a = build(); a.config['SERVER_NAME'] = 'example.test'
R['sn'] = probe(a, hosts); [print(f'  Host {h:<20} → {v}') for h, v in R['sn'].items()]
print()
print('== 三:Flask(subdomain_matching=True) + SERVER_NAME:子域名按主机名匹配;主机名不属于 SERVER_NAME 时')
import warnings
a = build(subdomain_matching=True); a.config['SERVER_NAME'] = 'example.test'
with warnings.catch_warnings(record=True) as W:
    warnings.simplefilter('always'); R['sm'] = probe(a, hosts)
[print(f'  Host {h:<20} → {v}') for h, v in R['sm'].items()]
print('  警告(UserWarning):', sorted({str(w.message)[:110] for w in W})[:3]); R['warn'] = sorted({str(w.message) for w in W})[:3]
print()
print('== 三b:SERVER_NAME 带端口时,Host 头也要带同样的端口')
a = Flask('sd2', subdomain_matching=True); a.logger.disabled = True; a.add_url_rule('/', 'idx', lambda: '主域'); a.add_url_rule('/', 'api', lambda: 'api 子域', subdomain='api'); a.config['SERVER_NAME'] = 'example.test:8000'
with warnings.catch_warnings(): warnings.simplefilter('ignore'); R['port'] = probe(a, ['example.test:8000', 'api.example.test:8000', 'api.example.test', 'api.example.test:9999'])
[print(f'  Host {h:<26} → {v}') for h, v in R['port'].items()]
print()
print('== 四:url_for 对子域名路由:生成包含主机的完整 URL')
a = build(subdomain_matching=True); a.config['SERVER_NAME'] = 'example.test:5000'
with a.test_request_context('/', base_url='http://example.test:5000'): R['uf'] = [url_for('api_index'), url_for('user_index', user='ann'), url_for('www_index'), url_for('www_index', _external=True)]; print('  url_for("api_index") →', R['uf'][0], '| url_for("user_index", user="ann") →', R['uf'][1], '| url_for("www_index") →', R['uf'][2], '| _external →', R['uf'][3])
print()
print('== 五:真实 HTTP:用 gunicorn 起服务,用 Host 头模拟不同子域名(不需要改 hosts 文件)')
d = mkapp('f29', {'app.py': '''
from flask import Flask
app = Flask(__name__, subdomain_matching=True)
app.config["SERVER_NAME"] = "example.test:{PORT}"
app.add_url_rule("/", "www", lambda: "www 首页")
app.add_url_rule("/", "api", lambda: "api 首页", subdomain="api")
app.add_url_rule("/", "user", lambda user: f"用户 {user}", subdomain="<user>")
'''.replace('{PORT}', '__PORT__')})
port = free_port(); (d / 'app.py').write_text((d / 'app.py').read_text().replace('__PORT__', str(port)))
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app'], port=port) as s:
    R['real'] = {}
    for hh in (f'example.test:{port}', f'api.example.test:{port}', f'ann.example.test:{port}', f'example.test', f'evil.test:{port}'):
        st, h, b, dt = s.get('/', headers={'Host': hh}); R['real'][hh] = [st, b.decode().strip()[:30]]; print(f'  Host: {hh:<24} → {st} {b.decode().strip()[:30] if st == 200 else ""}')
print()
print('== 六:cookie 与子域名:Session cookie 默认只对设置它的主机生效;SESSION_COOKIE_DOMAIN 可以让子域名共享(验证 Set-Cookie 头)')
a = Flask('ck', subdomain_matching=True); a.secret_key = 'k'; a.logger.disabled = True; a.config['SERVER_NAME'] = 'example.test'
@a.get('/set')
def setck(): 
    from flask import session; session['x'] = 1; return 'ok'
r = a.test_client().get('/set', base_url='http://example.test'); R['ck1'] = r.headers.get('Set-Cookie'); print('  默认:', R['ck1'])
a.config['SESSION_COOKIE_DOMAIN'] = '.example.test'; r = a.test_client().get('/set', base_url='http://example.test'); R['ck2'] = r.headers.get('Set-Cookie'); print('  SESSION_COOKIE_DOMAIN=".example.test":', R['ck2'])
save('f29', R)

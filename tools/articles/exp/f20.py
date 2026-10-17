import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f20'); R = {}
from flask import Flask, url_for
a = Flask('ts'); a.logger.disabled = True
a.add_url_rule('/projects/', 'projects', lambda: 'projects 列表')
a.add_url_rule('/about', 'about', lambda: 'about 页面')
a.add_url_rule('/loose', 'loose', lambda: 'loose', strict_slashes=False)
a.add_url_rule('/loose2/', 'loose2', lambda: 'loose2', strict_slashes=False)
a.add_url_rule('/submit/', 'submit', lambda: 'submitted', methods=['POST'])
c = a.test_client()
print('== 一:规则以 / 结尾(/projects/)与不以 / 结尾(/about)时,带不带斜杠访问的结果')
print(f'  {"请求":<20} {"状态":<6} Location / 正文')
R['rows'] = {}
for p in ('/projects/', '/projects', '/about', '/about/', '/loose', '/loose/', '/loose2', '/loose2/'):
    r = c.get(p); R['rows'][p] = [r.status_code, r.headers.get('Location'), r.get_data(as_text=True)[:30]]; print(f'  GET {p:<16} {r.status_code:<6} {r.headers.get("Location") or r.get_data(as_text=True).strip().splitlines()[1][:40] if r.status_code == 404 else (r.headers.get("Location") or r.get_data(as_text=True))}')
print()
print('== 二:重定向的状态码与方法:对不带斜杠的 POST 也会被重定向,308 保留方法与请求体;不跟随重定向时只看到 308')
r = c.post('/submit', data={'a': '1'}); print('  POST /submit(规则是 /submit/)→', r.status_code, '| Location =', r.headers.get('Location')); R['post308'] = [r.status_code, r.headers.get('Location')]
r = c.post('/submit', data={'a': '1'}, follow_redirects=True); print('  follow_redirects=True →', r.status_code, r.get_data(as_text=True), '| 重定向历史:', [(x.status_code, x.request.method) for x in r.history]); R['follow'] = [r.status_code, r.get_data(as_text=True), [(x.status_code, x.request.method) for x in r.history]]
print()
print('== 三:Location 头是相对路径还是绝对 URL')
r = c.get('/projects', base_url='http://example.test:8080'); print('  GET http://example.test:8080/projects → Location =', r.headers.get('Location'), '| autocorrect_location_header =', a.response_class.autocorrect_location_header); R['loc'] = [r.headers.get('Location'), a.response_class.autocorrect_location_header]
print()
print('== 四:url_for 生成的是规则里写的形式(带不带斜杠由规则决定)')
with a.test_request_context():
    R['url_for'] = {e: url_for(e) for e in ('projects_', 'about')} if False else None
    print('  url_for 的结果:', {ep: url_for(ep) for ep in [r.endpoint for r in a.url_map.iter_rules() if r.rule in ('/projects/', '/about', '/loose')]}); R['url_for'] = {ep: url_for(ep) for ep in [r.endpoint for r in a.url_map.iter_rules() if r.rule in ('/projects/', '/about', '/loose')]}
print()
print('== 五:全局设置 url_map.strict_slashes = False;以及同时注册 /x 与 /x/ 两条规则')
b = Flask('ts2'); b.logger.disabled = True; b.url_map.strict_slashes = False; b.add_url_rule('/projects/', 'projects', lambda: 'p'); b.add_url_rule('/about', 'about', lambda: 'a'); bc = b.test_client()
print('  strict_slashes = False:', {p: bc.get(p).status_code for p in ('/projects', '/projects/', '/about', '/about/')}); R['global'] = {p: bc.get(p).status_code for p in ('/projects', '/projects/', '/about', '/about/')}
e = Flask('ts3'); e.logger.disabled = True
try:
    e.add_url_rule('/x', 'x_plain', lambda: 'no-slash'); e.add_url_rule('/x/', 'x_slash', lambda: 'with-slash'); ec = e.test_client(); print('  同时注册 /x 与 /x/:', {p: (ec.get(p).status_code, ec.get(p).get_data(as_text=True)) for p in ('/x', '/x/')}); R['both'] = {p: [ec.get(p).status_code, ec.get(p).get_data(as_text=True)] for p in ('/x', '/x/')}
except Exception as ex: print('  同时注册失败:', type(ex).__name__, ex)
print()
print('== 六:代价:一个多余的重定向就是多一次往返;用 test client 量 /projects 与 /projects/ 各 5000 次(follow_redirects 打开)')
import timeit
c.get('/projects', follow_redirects=True); t_redirect = min(timeit.timeit(lambda: c.get('/projects', follow_redirects=True), number=3000) / 3000 * 1e6 for _ in range(3)); t_direct = min(timeit.timeit(lambda: c.get('/projects/'), number=3000) / 3000 * 1e6 for _ in range(3))
print(f'  直接访问 /projects/:{t_direct:.1f} µs;访问 /projects(重定向后再请求):{t_redirect:.1f} µs(约 {t_redirect / t_direct:.1f} 倍,因为多发了一个请求)'); R['cost'] = [t_direct, t_redirect]
save('f20', R)

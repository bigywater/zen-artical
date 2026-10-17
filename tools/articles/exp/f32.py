import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f32'); R = {}
from flask import Flask, request
app = Flask('qs'); app.logger.disabled = True
@app.get('/q')
def q():
    return {'args': request.args.to_dict(flat=False), 'first': request.args.get('k'), 'getlist': request.args.getlist('k'), 'raw': request.query_string.decode('latin-1')}
@app.get('/need')
def need(): return request.args['must']
c = app.test_client()
def show(qs): r = c.get('/q?' + qs); return r.get_json()
print('== 一:request.args 是 ImmutableMultiDict:同一个键出现多次时 get 取第一个,getlist 取全部')
R['multi'] = show('k=1&k=2&k=3'); print('  ?k=1&k=2&k=3 →', R['multi'])
with app.test_request_context('/q?k=1&k=2'): print('  类型:', type(request.args).__name__, '| 修改会怎样:', end=' ')
try:
    with app.test_request_context('/q?k=1'): request.args['k'] = '2'
except TypeError as e: print('TypeError:', e); R['immut'] = str(e)
print()
print('== 二:各种边界写法:空值、没有等号、重复的 &、空键、编码')
R['edge'] = {}
for qs in ('k=', 'k', 'k=&k=1', '&&k=1&&', '=v', 'a=1&a', 'k=a%26b', 'k=a+b', 'k=%E4%B8%AD', 'k=1;j=2', 'k[]=1&k[]=2', 'k=a=b'): R['edge'][qs] = show(qs)['args']; print(f'  ?{qs:<14} → {R["edge"][qs]}')
print()
print('== 三:类型转换:get(key, default, type=...) 失败时返回 default,不抛异常')
with app.test_request_context('/q?n=12&bad=abc&neg=-3&f=1.5&empty='):
    a = request.args; rows = [('get("n", type=int)', a.get('n', type=int)), ('get("bad", type=int)', a.get('bad', type=int)), ('get("bad", 0, type=int)', a.get('bad', 0, type=int)), ('get("neg", type=int)', a.get('neg', type=int)), ('get("f", type=float)', a.get('f', type=float)), ('get("empty", type=int)', a.get('empty', type=int)), ('get("missing")', a.get('missing')), ('get("missing", "x")', a.get('missing', 'x')), ('a["n"]', a['n'])]
    R['types'] = [[k, repr(v)] for k, v in rows]
    for k, v in rows: print(f'  {k:<26} → {v!r}')
    try: a['missing']
    except Exception as e: print('  a["missing"] →', type(e).__name__, '(KeyError 的子类,默认变成 400):', type(e).__mro__[1].__name__); R['badkey'] = [type(e).__name__, type(e).__mro__[1].__name__]
r = c.get('/missing-key') ; 
r = c.get('/need'); print('  视图里直接 request.args["must"] 缺失 →', r.status_code); R['need'] = r.status_code
print()
print('== 四:参数个数与长度的限制:MAX_FORM_PARTS 只管表单,查询字符串的限制在服务器(gunicorn 的 limit_request_line)')
r = c.get('/q?' + '&'.join(f'k{i}=1' for i in range(5000))); print('  test client 发 5000 个查询参数 →', r.status_code, '| 解析出', len(r.get_json()['args']), '个'); R['many'] = [r.status_code, len(r.get_json()['args'])]
d = __import__('fl').app('f32', {'app.py': 'from flask import Flask, request\napp = Flask(__name__)\n@app.get("/q")\ndef q(): return str(len(request.args))\n'})
with Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', 'app:app']) as s:
    R['limit'] = {}
    for n in (100, 1000, 1500):
        qs = '&'.join(f'k{i}=1' for i in range(n)); st, h, b, dt = s.get('/q?' + qs); R['limit'][n] = [st, len(qs), b.decode()[:40]]; print(f'  gunicorn 默认:{n} 个参数(查询串 {len(qs)} 字节)→ {st} {b.decode()[:40]!r}')
print('  gunicorn 默认的请求行上限 limit_request_line = 4094 字节(超过返回 4xx)')
print()
print('== 五:request.args 与 request.values、request.form 的关系:values 合并 args 与 form,args 优先')
with app.test_request_context('/q?k=from_args', method='POST', data={'k': 'from_form', 'only_form': '1'}):
    print('  args:', request.args.to_dict(), '| form:', request.form.to_dict(), '| values:', request.values.to_dict(flat=False)); R['values'] = [request.args.to_dict(), request.form.to_dict(), request.values.to_dict(flat=False)]
save('f32', R)

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f39'); R = {}
from flask import Flask, Response, make_response
from werkzeug.datastructures import Headers
app = Flask('rsp')
print('== 一:Response 的构造参数:response、status、headers、mimetype、content_type 的相互影响')
rows = [("Response('hi')", Response('hi')), ("Response('hi', 201)", Response('hi', 201)), ("Response('hi', '202 自定义')", Response('hi', '202 自定义')), ("Response('hi', mimetype='text/plain')", Response('hi', mimetype='text/plain')), ("Response('hi', content_type='text/csv')", Response('hi', content_type='text/csv')), ("Response('hi', content_type='text/plain; charset=latin-1')", Response('hi', content_type='text/plain; charset=latin-1')), ("Response('hi', headers={'X-A': '1'})", Response('hi', headers={'X-A': '1'})), ("Response(b'\\x00\\x01')", Response(b'\x00\x01')), ("Response(['a', 'b'])", Response(['a', 'b'])), ("Response()", Response())]
R['rows'] = {}
for k, r in rows: R['rows'][k] = [r.status, r.content_type, r.get_data(as_text=False)[:10].decode('latin-1'), dict(r.headers)]; print(f'  {k:<56} → {r.status} | {r.content_type} | {r.get_data()[:10]!r} | {dict(r.headers)}')
print()
print('== 二:status 与 status_code 互相同步;自定义状态短语;非法状态码')
r = Response('x'); r.status_code = 404; print('  设 status_code=404 后 status =', r.status); r.status = '418 我是茶壶'; print('  设 status="418 我是茶壶" 后 status_code =', r.status_code, '| status =', r.status); R['sync'] = [r.status_code, r.status]
for bad in (99, 1000, '999 x', 'abc'):
    try: x = Response('x', bad); print(f'  Response(status={bad!r}) → {x.status} / {x.status_code}'); R.setdefault('bad', {})[str(bad)] = [x.status, x.status_code]
    except Exception as e: print(f'  Response(status={bad!r}) → {type(e).__name__}: {e}'); R.setdefault('bad', {})[str(bad)] = f'{type(e).__name__}: {e}'
print()
print('== 三:headers 是 Headers 对象(不区分大小写、可重复):set / add / extend / remove / getlist')
r = Response('x'); print('  类型:', type(r.headers).__name__)
r.headers['X-One'] = '1'; r.headers.add('X-Multi', 'a'); r.headers.add('X-Multi', 'b'); r.headers.set('x-one', '1b'); r.headers.extend({'X-Ext': 'e'})
print('  结果:', r.headers.to_wsgi_list()); print('  getlist("X-Multi") =', r.headers.getlist('X-Multi'), '| r.headers["x-one"] =', r.headers['x-one'], '| "X-Ext" in headers:', 'X-Ext' in r.headers); R['headers'] = [r.headers.to_wsgi_list(), r.headers.getlist('X-Multi')]
del r.headers['X-Ext']; print('  删除 X-Ext 后:', [k for k, v in r.headers.to_wsgi_list()]); R['deleted'] = [k for k, v in r.headers.to_wsgi_list()]
print()
print('== 四:头里放换行符会怎样(防止响应拆分/头注入)')
r = Response('x')
for label, val in (('值里有 \\n', 'a\nSet-Cookie: evil=1'), ('值里有 \\r\\n', 'a\r\nX: y'), ('值里有 \\x00', 'a\x00b')):
    try: r.headers['X-Test'] = val; print(f'  {label} → 设置成功: {r.headers["X-Test"]!r}')
    except Exception as e: print(f'  {label} → {type(e).__name__}: {str(e)[:80]}'); R.setdefault('inject', {})[label] = f'{type(e).__name__}'
print()
print('== 五:get_data / set_data / content_length:set_data 会同步更新 Content-Length;直接改 response 属性则不会')
r = Response('hello'); print('  初始 Content-Length =', r.content_length, '| data =', r.get_data()); r.set_data('你好,世界'); print('  set_data 之后 Content-Length =', r.content_length, '(UTF-8 字节数)', '| 字符数 =', len('你好,世界')); R['len'] = [r.content_length, len('你好,世界')]
r = Response(['a', 'b', 'c']); print('  迭代器形式的 response:Content-Length =', r.content_length, '| is_sequence =', r.is_sequence, '| is_streamed =', r.is_streamed); R['seq'] = [r.content_length, r.is_sequence, r.is_streamed]
def gen(): yield 'a'; yield 'b'
r = Response(gen()); print('  生成器形式:Content-Length =', r.content_length, '| is_sequence =', r.is_sequence, '| is_streamed =', r.is_streamed); R['gen'] = [r.content_length, r.is_sequence, r.is_streamed]
print()
print('== 六:最终的 WSGI 三元组:response(environ, start_response) 调用后 start_response 收到什么;HEAD 请求不发送正文')
from werkzeug.test import EnvironBuilder
r = Response('body 内容', 200, {'X-A': '1'}); cap = {}
def sr(status, headers, exc_info=None): cap['status'], cap['headers'] = status, headers
it = r(EnvironBuilder('/', method='GET').get_environ(), sr); print('  GET:', cap['status'], cap['headers'], '| 正文', list(it)); R['wsgi_get'] = [cap['status'], cap['headers']]
r = Response('body 内容'); it = r(EnvironBuilder('/', method='HEAD').get_environ(), sr); print('  HEAD:', cap['status'], '| Content-Length =', dict(cap['headers']).get('Content-Length'), '| 正文', list(it)); R['wsgi_head'] = [dict(cap['headers']).get('Content-Length'), list(it)]
save('f39', R)

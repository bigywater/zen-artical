import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f19'); R = {}
from flask import Flask, url_for, abort
from werkzeug.routing import BaseConverter, ValidationError
USERS = {1: 'ann', 2: 'bob'}
class ListConverter(BaseConverter):
    regex = r'[\w-]+(?:,[\w-]+)*'
    def to_python(self, value): return value.split(',')
    def to_url(self, values): return ','.join(BaseConverter.to_url(self, v) for v in values)
class UserConverter(BaseConverter):
    regex = r'\d+'
    def to_python(self, value):
        uid = int(value)
        if uid not in USERS: raise ValidationError()
        return {'id': uid, 'name': USERS[uid]}
    def to_url(self, user): return str(user['id'])
SRC = '''
    class ListConverter(BaseConverter):
        regex = r"[\\w-]+(?:,[\\w-]+)*"
        def to_python(self, value): return value.split(",")
        def to_url(self, values): return ",".join(BaseConverter.to_url(self, v) for v in values)
    class UserConverter(BaseConverter):
        regex = r"\\d+"
        def to_python(self, value):
            uid = int(value)
            if uid not in USERS: raise ValidationError()
            return {"id": uid, "name": USERS[uid]}
        def to_url(self, user): return str(user["id"])
    app.url_map.converters["list"] = ListConverter
    app.url_map.converters["user"] = UserConverter
'''
print('== 一:两个自定义转换器:list(逗号分隔成列表)和 user(把 ID 转成对象,不存在就 404)')
src(SRC, '转换器定义与注册')
a = Flask('cc'); a.logger.disabled = True
a.url_map.converters['list'] = ListConverter; a.url_map.converters['user'] = UserConverter
@a.get('/tags/<list:tags>')
def tags(tags): return f'{type(tags).__name__}:{tags}'
@a.get('/u/<user:u>')
def user(u): return f'{type(u).__name__}:{u}'
c = a.test_client(); R['req'] = {}
for p in ('/tags/a,b,c', '/tags/solo', '/tags/a,,b', '/u/1', '/u/2', '/u/3', '/u/abc'):
    r = c.get(p); R['req'][p] = [r.status_code, r.get_data(as_text=True)[:40]]; print(f'  GET {p:<14} → {r.status_code} {r.get_data(as_text=True)[:40] if r.status_code == 200 else ""}')
print()
print('== 二:to_url:url_for 反向生成时调用转换器的 to_url')
with a.test_request_context():
    R['url_for'] = [url_for('tags', tags=['x', 'y', 'z']), url_for('user', u={'id': 2, 'name': 'bob'}), url_for('tags', tags=['a b', 'c'])]
    print('  url_for("tags", tags=["x","y","z"]) →', R['url_for'][0]); print('  url_for("user", u={"id": 2, ...}) →', R['url_for'][1]); print('  url_for("tags", tags=["a b","c"]) →', R['url_for'][2], '(to_url 里调用 BaseConverter.to_url 做了 URL 转义)')
print()
print('== 三:转换器必须在注册路由之前加入 url_map.converters;用了没注册的转换器')
b = Flask('cc2')
try: b.add_url_rule('/z/<list:v>', 'z', lambda v: 'x')
except Exception as e: print('  使用未注册的 list 转换器 →', type(e).__name__ + ':', str(e)); R['unreg'] = [type(e).__name__, str(e)]
print()
print('== 四:转换失败(ValidationError)与视图里 abort(404):都得到 404;看 before_request 与视图是否被执行')
ev = []
d = Flask('cc3'); d.logger.disabled = True; d.url_map.converters['user'] = UserConverter
@d.before_request
def br(): ev.append('before_request')
@d.get('/u/<user:u>')
def u2(u): ev.append('view'); return 'ok'
@d.get('/v/<int:n>')
def v2(n): ev.append('view'); abort(404)
for p in ('/u/3', '/v/1'):
    ev.clear(); r = d.test_client().get(p); print(f'  GET {p:<6} → {r.status_code};触发的回调:{ev}'); R.setdefault('when', {})[p] = [r.status_code, list(ev)]
print()
print('== 五:转换器的开销:匹配 /u/<user:u> 与 /u/<int:u>(test client,各 5000 次取最小;user 转换器里有一次字典查找)')
import timeit
e1 = Flask('t1'); e1.url_map.converters['user'] = UserConverter; e1.get('/u/<user:u>')(lambda u: 'x'); e2 = Flask('t2'); e2.get('/u/<int:u>')(lambda u: 'x')
c1, c2 = e1.test_client(), e2.test_client(); c1.get('/u/1'); c2.get('/u/1')
t1_ = min(timeit.timeit(lambda: c1.get('/u/1'), number=5000) / 5000 * 1e6 for _ in range(3)); t2_ = min(timeit.timeit(lambda: c2.get('/u/1'), number=5000) / 5000 * 1e6 for _ in range(3))
print(f'  自定义 user 转换器 {t1_:.1f} µs/请求;内置 int {t2_:.1f} µs/请求;差 {t1_ - t2_:.1f} µs'); R['cost'] = [t1_, t2_]
save('f19', R)

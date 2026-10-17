import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f164'); R = {}
import json, timeit, datetime as dt, decimal, orjson, dataclasses
from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider, JSONProvider
N = 10000
plain = [{'id': i, 'name': f'user{i}', 'email': f'user{i}@example.com', 'score': i * 1.5, 'active': i % 2 == 0, 'tags': ['a', 'b', 'c']} for i in range(N)]
rich = [{**r, 'created': dt.datetime(2026, 1, 1, 12, 0, i % 60), 'balance': decimal.Decimal(f'{i}.25')} for i, r in enumerate(plain)]
def best(fn, n=5): return min(timeit.repeat(fn, number=1, repeat=n)) * 1000
print(f'== 一:{N} 行(每行 6 个字段):标准库 json 各选项 vs orjson')
R['plain'] = {}
for label, fn in (('json.dumps 默认', lambda: json.dumps(plain)), ('json.dumps sort_keys=True', lambda: json.dumps(plain, sort_keys=True)), ('json.dumps ensure_ascii=False', lambda: json.dumps(plain, ensure_ascii=False)), ('json.dumps 紧凑 separators', lambda: json.dumps(plain, separators=(',', ':'))), ('orjson.dumps', lambda: orjson.dumps(plain)), ('orjson.dumps + OPT_SORT_KEYS', lambda: orjson.dumps(plain, option=orjson.OPT_SORT_KEYS))):
    R['plain'][label] = best(fn); print(f'  {label:<32} {R["plain"][label]:7.2f} ms')
print()
print(f'== 二:含 datetime 与 Decimal 的 {N} 行:标准库要靠 default 钩子逐个转换,orjson 原生支持(Decimal 要自己转)')
def default(o):
    if isinstance(o, (dt.datetime, dt.date)): return o.isoformat()
    if isinstance(o, decimal.Decimal): return str(o)
    raise TypeError
def od(o):
    if isinstance(o, decimal.Decimal): return str(o)
    raise TypeError
R['rich'] = {}
for label, fn in (('json.dumps + default 钩子', lambda: json.dumps(rich, default=default)), ('orjson.dumps(datetime 原生,Decimal 用 default)', lambda: orjson.dumps(rich, default=od))):
    R['rich'][label] = best(fn); print(f'  {label:<44} {R["rich"][label]:7.2f} ms')
print('  default 钩子被调用的次数(每行 2 个对象):', 2 * N)
print()
print('== 三:Flask 的 jsonify / 返回 dict 走的路径:DefaultJSONProvider(sort_keys 默认 True)vs 换成 orjson 的 provider')
class OrjsonProvider(JSONProvider):
    def dumps(self, obj, **kw): return orjson.dumps(obj, default=od, option=orjson.OPT_NON_STR_KEYS).decode()
    def loads(self, s, **kw): return orjson.loads(s)
    def response(self, *args, **kwargs):
        obj = self._prepare_response_obj(args, kwargs); return self._app.response_class(orjson.dumps(obj, default=od), mimetype='application/json')
def mk(provider=None):
    a = Flask('j'); a.logger.disabled = True
    if provider: a.json = provider(a)
    @a.get('/plain')
    def p(): return plain
    @a.get('/rich')
    def r(): return jsonify(rich)
    return a
R['flask'] = {}
for label, prov in (('Flask 默认 provider', None), ('orjson provider', OrjsonProvider)):
    a = mk(prov); c = a.test_client(); c.get('/plain'); c.get('/rich'); tp = best(lambda: c.get('/plain'), 3); tr = best(lambda: c.get('/rich'), 3); sz = len(c.get('/plain').data); print(f'  {label:<22} /plain {tp:7.1f} ms | /rich {tr:7.1f} ms | /plain 响应 {sz / 1e6:.2f} MB'); R['flask'][label] = [tp, tr, sz]
print()
print('== 四:哪一步占大头:把「查询出来的对象转成 dict」与「dict 转成 JSON」分开计时(10000 个简单对象)')
@dataclasses.dataclass
class Row:
    id: int; name: str; email: str; score: float; active: bool; tags: list
objs = [Row(**r) for r in plain]
to_dict = best(lambda: [dataclasses.asdict(o) for o in objs], 3); manual = best(lambda: [{'id': o.id, 'name': o.name, 'email': o.email, 'score': o.score, 'active': o.active, 'tags': o.tags} for o in objs]); dump = best(lambda: json.dumps(plain)); odump = best(lambda: orjson.dumps(objs))
print(f'  dataclasses.asdict {to_dict:7.1f} ms | 手写字典推导 {manual:5.1f} ms | json.dumps(dict 列表){dump:6.1f} ms | orjson 直接序列化 dataclass 对象 {odump:5.1f} ms'); R['steps'] = [to_dict, manual, dump, odump]
save('f164', R)

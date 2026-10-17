import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f115'); R = {}
import json, decimal, datetime as dt, timeit
from marshmallow import Schema, fields, validate, validates, validates_schema, post_load, pre_load, ValidationError, EXCLUDE, INCLUDE, RAISE, post_dump
class User:
    def __init__(self, id, name, email, password, created, balance, secret='x'): self.id, self.name, self.email, self.password, self.created, self.balance, self.secret = id, name, email, password, created, balance, secret
class PostS(Schema):
    id = fields.Int(); title = fields.Str(required=True)
class UserS(Schema):
    id = fields.Int(dump_only=True); name = fields.Str(required=True, validate=validate.Length(min=1, max=20)); email = fields.Email(required=True)
    password = fields.Str(load_only=True, required=True); created = fields.DateTime(dump_only=True); balance = fields.Decimal(places=2, as_string=True)
    display = fields.Method('get_display', dump_only=True); posts = fields.List(fields.Nested(PostS), dump_default=[])
    full_name = fields.Str(attribute='name', data_key='fullName', dump_only=True)
    def get_display(self, obj): return f'{obj.name} <{obj.email}>'
u = User(1, 'ann', 'ann@x.test', 'secret-pw', dt.datetime(2026, 1, 2, 3, 4, 5), decimal.Decimal('10.5'))
print('== 一:dump(对象 → dict):只输出声明过的字段,load_only 不输出,各种类型的序列化')
out = UserS().dump(u); print('  ', json.dumps(out, ensure_ascii=False)); R['dump'] = out
print('  对象上的 secret、password 属性:', 'secret' in out, '/', 'password' in out, '(没声明或 load_only 的不会泄漏)')
print('  data_key 改名:fullName =', out['fullName'], '| Method 字段 display =', out['display'], '| Decimal as_string:', repr(out['balance']), '| 日期:', out['created'])
print()
print('== 二:load(dict → 数据):校验 + 类型转换;错误信息的结构')
ok = UserS().load({'name': 'bob', 'email': 'b@x.test', 'password': 'pw', 'balance': '3.14159'}); print('  合法输入 →', ok); R['load'] = {k: str(v) for k, v in ok.items()}
def tryl(label, data, **kw):
    try: r = UserS().load(data, **kw); out = f'通过 {r}'
    except ValidationError as e: out = json.dumps(e.messages, ensure_ascii=False)
    print(f'  {label:<26} → {out[:150]}'); return out
R['errs'] = {}
R['errs']['空'] = tryl('什么都没给', {})
R['errs']['多错'] = tryl('多个字段同时出错', {'name': '', 'email': 'nope', 'password': 'pw'})
R['errs']['类型'] = tryl('类型不对(name 是数字)', {'name': 123, 'email': 'a@x.test', 'password': 'pw'})
R['errs']['嵌套'] = tryl('嵌套的 posts 有错', {'name': 'a', 'email': 'a@x.test', 'password': 'pw', 'posts': [{'title': 'ok'}, {}]})
R['errs']['dump_only'] = tryl('传了 dump_only 的 id', {'id': 5, 'name': 'a', 'email': 'a@x.test', 'password': 'pw'})
print()
print('== 三:未知字段:unknown = RAISE(默认)、EXCLUDE、INCLUDE')
for label, unk in (('RAISE(默认)', RAISE), ('EXCLUDE', EXCLUDE), ('INCLUDE', INCLUDE)): R['errs'][label] = tryl(label, {'name': 'a', 'email': 'a@x.test', 'password': 'pw', 'extra': 1}, unknown=unk)
print()
print('== 四:部分更新 partial=True;钩子 pre_load / post_load / validates / validates_schema')
R['errs']['partial'] = tryl('partial=True 只给 name', {'name': 'zed'}, partial=True)
class S2(Schema):
    name = fields.Str(required=True); start = fields.Int(); end = fields.Int()
    @pre_load
    def strip(self, d, **kw): d = dict(d); d['name'] = d.get('name', '').strip().lower(); return d
    @validates('name')
    def no_admin(self, v, **kw):
        if v == 'admin': raise ValidationError('保留名')
    @validates_schema
    def order(self, d, **kw):
        if 'start' in d and 'end' in d and d['start'] > d['end']: raise ValidationError('start 必须小于等于 end', 'start')
    @post_load
    def make(self, d, **kw): return type('Range', (), d)()
r = S2().load({'name': '  Ann ', 'start': 1, 'end': 5}); print('  pre_load 去空格转小写 + post_load 构造对象 →', type(r).__name__, r.name); R['hooks'] = r.name
for label, data in (('validates 拒绝 admin', {'name': ' ADMIN '}), ('validates_schema 跨字段', {'name': 'a', 'start': 9, 'end': 1})):
    try: S2().load(data)
    except ValidationError as e: print(f'  {label:<24} →', json.dumps(e.messages, ensure_ascii=False)); R['hooks_err_' + label] = e.messages
print()
print('== 五:类型转换的宽松程度(Int 字段收到各种输入)')
class I(Schema): n = fields.Int()
R['int'] = {}
for v in (5, '5', '5.0', 5.0, 5.5, True, 'abc', None, ' 7 '):
    try: r = I().load({'n': v}); out = f'→ {r["n"]!r}'
    except ValidationError as e: out = f'错误 {e.messages["n"][0]}'
    print(f'  {v!r:<8} {out}'); R['int'][repr(v)] = out
print()
print('== 六:性能:dump 10000 个对象,Schema vs 手写字典推导(各取 5 组最小)')
class Item: 
    def __init__(self, i): self.id, self.name, self.score = i, f'n{i}', i * 1.5
class IS(Schema): id = fields.Int(); name = fields.Str(); score = fields.Float()
items = [Item(i) for i in range(10000)]; sch = IS(many=True)
t_m = min(timeit.repeat(lambda: sch.dump(items), number=1, repeat=5)) * 1000; t_d = min(timeit.repeat(lambda: [{'id': i.id, 'name': i.name, 'score': i.score} for i in items], number=1, repeat=5)) * 1000
class PS(Schema): id = fields.Int(); name = fields.Str(); score = fields.Float()
print(f'  marshmallow dump {t_m:.1f} ms;手写字典推导 {t_d:.1f} ms;约 {t_m / t_d:.0f} 倍'); R['perf'] = [t_m, t_d]
save('f115', R)

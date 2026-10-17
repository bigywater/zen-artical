import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f116'); R = {}
import json, decimal, datetime as dt, timeit
from typing import Annotated, Optional
from flask import Flask, request, jsonify
from pydantic import BaseModel, Field, ValidationError, field_validator, ConfigDict, EmailStr, TypeAdapter
class Item(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=20)]
    qty: int = Field(ge=0, le=1000)
    price: decimal.Decimal = Field(decimal_places=2)
    tags: list[str] = []
    note: Optional[str] = None
def tryv(label, data, model=Item):
    try: r = model.model_validate(data); out = f'通过 {r.model_dump()}'
    except ValidationError as e: out = '; '.join(f"{'.'.join(map(str, x['loc']))}: {x['type']}" for x in e.errors())
    print(f'  {label:<30} → {out[:150]}'); return out
print('== 一:model_validate:类型转换与错误')
R['v'] = {}
base = {'name': 'pen', 'qty': 3, 'price': '1.50'}
R['v']['合法'] = tryv('合法(price 是字符串 "1.50")', base)
R['v']['缺'] = tryv('缺字段', {'name': 'pen'})
R['v']['多错'] = tryv('多个字段出错', {'name': '', 'qty': -1, 'price': 'abc'})
R['v']['qty字符串'] = tryv('qty = "5"(字符串)', {**base, 'qty': '5'})
R['v']['qty小数'] = tryv('qty = 5.5', {**base, 'qty': 5.5})
R['v']['qty5.0'] = tryv('qty = 5.0', {**base, 'qty': 5.0})
R['v']['qtybool'] = tryv('qty = True', {**base, 'qty': True})
R['v']['多余'] = tryv('多余字段 extra', {**base, 'extra': 1})
R['v']['嵌套'] = tryv('tags 里有数字', {**base, 'tags': ['a', 1]})
try: Item.model_validate({**base, 'qty': -1})
except ValidationError as e: err = e.errors()[0]; print('  一条错误的完整内容:', {k: v for k, v in err.items() if k != 'url'}); R['err_item'] = {k: v for k, v in err.items() if k != 'url'}
print()
print('== 二:bool 与 严格模式')
class B(BaseModel): flag: bool
R['bool'] = {}
for v in ('true', 'false', '0', '1', 'yes', 'off', 'abc', 2, 'maybe'):
    try: r = B(flag=v).flag
    except ValidationError: r = '错误'
    print(f'  flag={v!r:<8} → {r}'); R['bool'][repr(v)] = r
class IS(BaseModel): n: int
class IStrict(BaseModel): model_config = ConfigDict(strict=True); n: int
for label, m in (('宽松(默认)', IS), ('strict=True', IStrict)):
    outs = []
    for v in ('5', 5.0, True):
        try: outs.append(m(n=v).n)
        except ValidationError: outs.append('错误')
    print(f'  {label:<14} n 收到 "5"、5.0、True → {outs}'); R.setdefault('strict', {})[label] = outs
print()
print('== 三:放进 Flask:请求体 → 模型,失败返回 422;errors() 里的 input(bytes)与 ctx(异常对象)可能不能直接 jsonify')
class User(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str
    age: int = Field(ge=0, le=150)
    @field_validator('name')
    @classmethod
    def no_admin(cls, v):
        if v.lower() == 'admin': raise ValueError('保留名')
        return v
app = Flask('p'); app.logger.disabled = True; app.config['PROPAGATE_EXCEPTIONS'] = False
@app.post('/u')
def u():
    try: m = User.model_validate_json(request.get_data())
    except ValidationError as e: return jsonify(errors=e.errors()), 422
    return jsonify(m.model_dump())
@app.post('/u2')
def u2():
    try: m = User.model_validate_json(request.get_data())
    except ValidationError as e: return jsonify(errors=e.errors(include_url=False, include_context=False, include_input=False)), 422
    return jsonify(m.model_dump())
@app.post('/u3')
def u3():
    try: m = User.model_validate_json(request.get_data())
    except ValidationError as e: return app.response_class(e.json(include_url=False), 422, mimetype='application/json')
    return jsonify(m.model_dump())
c = app.test_client(); R['flask'] = {}
for label, path, body in (('合法', '/u', '{"name":"ann","age":3}'), ('age 越界', '/u', '{"name":"ann","age":300}'), ('extra 被禁止', '/u', '{"name":"ann","age":3,"x":1}'), ('非法 JSON', '/u', '{'), ('自定义校验器 ValueError', '/u', '{"name":"admin","age":3}'), ('同上,errors(include_context=False, include_input=False)', '/u2', '{"name":"admin","age":3}'), ('非法 JSON,同样的 errors(...) 写法', '/u2', '{'), ('非法 JSON,用 e.json()', '/u3', '{'), ('同上,用 e.json()', '/u3', '{"name":"admin","age":3}')):
    r = c.post(path, data=body, content_type='application/json'); txt = r.get_data(as_text=True).strip().replace('\n', ' '); print(f'  {label:<34} → {r.status_code} {txt[:130]}'); R['flask'][label] = [r.status_code, txt[:200]]
print()
print('== 四:查询参数:request.args.to_dict() 会丢掉重复的参数')
class Q(BaseModel): ids: list[int] = []; page: int = 1
print('  ?ids=1&ids=2&page=3 用 to_dict():', end=' ')
try: print(Q.model_validate(request.args.to_dict() if False else __import__('werkzeug.datastructures', fromlist=['MultiDict']).MultiDict([('ids', '1'), ('ids', '2'), ('page', '3')]).to_dict()))
except ValidationError as e: print('错误:', [x['type'] for x in e.errors()]); R['todict'] = [x['type'] for x in e.errors()]
from werkzeug.datastructures import MultiDict
md = MultiDict([('ids', '1'), ('ids', '2'), ('page', '3')]); data = {k: md.getlist(k) if k == 'ids' else md.get(k) for k in md}; print('  自己用 getlist 处理 ids →', Q.model_validate(data)); R['getlist'] = str(Q.model_validate(data))
print()
print('== 五:序列化:model_dump(mode="json")、exclude、model_json_schema')
class Acct(BaseModel):
    id: int; email: str; password: str = Field(exclude=True); created: dt.datetime; bal: decimal.Decimal
a = Acct(id=1, email='a@x.test', password='pw', created=dt.datetime(2026, 1, 2, 3, 4, 5), bal=decimal.Decimal('1.10'))
print('  model_dump():', a.model_dump()); print('  model_dump(mode="json"):', a.model_dump(mode='json')); R['dump'] = [str(a.model_dump()), a.model_dump(mode='json')]
sc = Acct.model_json_schema(); print('  model_json_schema() 的 properties:', list(sc['properties']), '| required:', sc['required']); R['schema'] = [list(sc['properties']), sc['required']]
print()
print('== 六:性能:校验 10000 个字典(各取 5 组最小)')
rows = [{'name': f'n{i}', 'qty': i % 100, 'price': '1.50', 'tags': ['a'], 'note': None} for i in range(10000)]; ta = TypeAdapter(list[Item])
t1 = min(timeit.repeat(lambda: [Item.model_validate(r) for r in rows], number=1, repeat=5)) * 1000; t2 = min(timeit.repeat(lambda: ta.validate_python(rows), number=1, repeat=5)) * 1000
objs = ta.validate_python(rows); t3 = min(timeit.repeat(lambda: [o.model_dump() for o in objs], number=1, repeat=5)) * 1000
print(f'  逐个 model_validate {t1:.1f} ms;TypeAdapter 一次校验整个列表 {t2:.1f} ms;model_dump 10000 个 {t3:.1f} ms'); R['perf'] = [t1, t2, t3]
save('f116', R)

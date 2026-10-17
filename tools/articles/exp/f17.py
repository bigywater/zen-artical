import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f17'); R = {}
import itertools
from flask import Flask
def build(rules, methods=None):
    a = Flask('m'); a.logger.disabled = True
    for i, (rule, name) in enumerate(rules):
        a.add_url_rule(rule, endpoint=name, view_func=(lambda n: lambda **kw: f'{n}{dict(kw) if kw else ""}')(name), methods=(methods or {}).get(name, ['GET']))
    return a
def match(a, paths): c = a.test_client(); return {p: c.get(p).get_data(as_text=True).strip()[:40] if c.get(p).status_code == 200 else f'{c.get(p).status_code}' for p in paths}
def both(rules, paths, title):
    print(f'  {title}'); out = {}
    for label, rs in (('注册顺序 A', rules), ('注册顺序 B(倒过来)', rules[::-1])):
        m = match(build(rs), paths); out[label] = m; print(f'    {label:<20} ' + ' | '.join(f'{p} → {v}' for p, v in m.items()))
    same = out['注册顺序 A'] == out['注册顺序 B(倒过来)']; print('    两种顺序结果相同:', same); return out, same
print('== 一:静态路径优先于动态路径,与注册顺序无关')
R['s1'] = both([('/users/<name>', 'dyn'), ('/users/me', 'fixed')], ['/users/me', '/users/ann'], '/users/<name> 与 /users/me')
print()
print('== 二:转换器的优先级:int 比 string 更具体,path 最宽松')
R['s2'] = both([('/<x>', 'str'), ('/<int:x>', 'int')], ['/123', '/abc', '/-5'], '/<x>(string)与 /<int:x>')
R['s2b'] = both([('/files/<name>', 'name'), ('/files/<path:p>', 'path')], ['/files/a', '/files/a/b'], '/files/<name> 与 /files/<path:p>')
print()
print('== 三:多个动态段:前面的静态段优先')
R['s3'] = both([('/<a>/<b>', 'ab'), ('/<a>/x', 'ax'), ('/api/<b>', 'api_b')], ['/1/x', '/1/y', '/api/x', '/api/zz'], '/<a>/<b>、/<a>/x、/api/<b>')
print()
print('== 四:完全相同的规则注册两次:谁生效')
for order in (('first', 'second'), ('second', 'first')):
    a = build([('/dup', order[0]), ('/dup', order[1])]); print(f'    先注册 {order[0]}、后注册 {order[1]} → GET /dup:', a.test_client().get('/dup').get_data(as_text=True)); R.setdefault('dup', {})[order[0]] = a.test_client().get('/dup').get_data(as_text=True)
print()
print('== 五:同一路径、不同方法:挂在不同端点上,按方法分发;方法不匹配得到 405')
a = Flask('mm'); a.add_url_rule('/x', 'get_x', lambda: 'GET 端点', methods=['GET']); a.add_url_rule('/x', 'post_x', lambda: 'POST 端点', methods=['POST'])
c = a.test_client(); R['methods'] = {m: [c.open('/x', method=m).status_code, c.open('/x', method=m).get_data(as_text=True)[:20]] for m in ('GET', 'POST', 'PUT', 'DELETE')}
for m, v in R['methods'].items(): print(f'    {m:<6} /x → {v[0]} {v[1]!r}')
print()
print('== 六:iter_rules 的顺序,以及规则内部的片段权重')
a = build([('/users/<name>', 'dyn'), ('/users/me', 'fixed'), ('/<x>', 'x'), ('/<int:x>', 'i')])
print('    iter_rules 顺序(按注册顺序,不排序):', [r.rule for r in a.url_map.iter_rules() if r.endpoint != 'static']); R['iter'] = [r.rule for r in a.url_map.iter_rules() if r.endpoint != 'static']
print('    每条规则被拆成片段,每个片段有权重(取自私有属性 Rule._parts;权重越小优先级越高):')
R['parts'] = {}
for r in a.url_map.iter_rules():
    if r.endpoint == 'static': continue
    ps = [(('静态 ' + p.content) if p.static else '动态', p.weight.static_weights if p.static else p.weight.argument_weights) for p in r._parts if p.content or not p.static]
    R['parts'][r.rule] = [[x[0], str(x[1])] for x in ps]; print(f'      {r.rule:<16} ' + '  '.join(f'[{k} {w}]' for k, w in ps))
print()
print('== 七:匹配器类型与 merge_slashes:相邻的多个斜杠会被合并并重定向')
print('    url_map 的匹配器:', type(a.url_map._matcher).__name__, '| merge_slashes =', a.url_map.merge_slashes); R['matcher'] = type(a.url_map._matcher).__name__
r = a.test_client().get('/users//me'); print('    GET /users//me →', r.status_code, '| Location =', r.headers.get('Location')); R['merge'] = [r.status_code, r.headers.get('Location')]
save('f17', R)

import sys, os, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d20'); R = {}
d = proj('d20', apps=['django.contrib.contenttypes'], with_lab=False)
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\n" + code); return out.rstrip()
print('== 一:重复参数:get / getlist / dict 各返回什么')
o = run('''
from django.http import QueryDict
q = QueryDict('a=1&a=2&b=x&tag=py&tag=django&tag=orm&empty=')
print('QueryDict           =', q)
print("q['a']              =", repr(q['a']), '  ← 直接下标取到的是最后一个值')
print("q.get('a')          =", repr(q.get('a')))
print("q.getlist('a')      =", q.getlist('a'))
print("q.getlist('tag')    =", q.getlist('tag'))
print("q.get('missing')    =", q.get('missing'), " q.get('missing','dflt') =", q.get('missing', 'dflt'), " q.getlist('missing') =", q.getlist('missing'))
print("q.get('empty')      =", repr(q.get('empty')))
print('dict(q)             =', dict(q))
print('q.dict()            =', q.dict(), '  ← 每个 key 只留最后一个值')
print('list(q.items())     =', list(q.items()))
print('list(q.lists())     =', list(q.lists()))
print('len(q) =', len(q), '(key 的个数,不是参数个数)   q.keys() 顺序 =', list(q.keys()))
''')
print(o); R['dups'] = o
print()
print('== 二:QueryDict 默认不可变,copy() 才可变;urlencode() 的输出')
o = run('''
from django.http import QueryDict
q = QueryDict('a=1&a=2')
print('q._mutable =', q._mutable)
try: q['a'] = '3'
except AttributeError as e: print("q['a'] = '3' →", type(e).__name__ + ':', e)
m = q.copy(); m['a'] = '3'; m.appendlist('a', '4'); m.setlist('b', ['x', 'y'])
print('copy() 之后赋值/追加:', m, ' getlist("a") =', m.getlist('a'))
print('urlencode() =', m.urlencode())
m2 = QueryDict('q=中文&x=a b&y=%26'); print('解码后:', dict(m2.lists()), ' 再 urlencode():', m2.urlencode())
print('safe 参数保留 "/" :', QueryDict('next=/a/b/?c=1').urlencode(safe='/'))
''')
print(o); R['mutable'] = o
print()
print('== 三:请求里的 GET / POST 与重复参数;JSON 里没有这回事')
o = run('''
from django.test import RequestFactory
rf = RequestFactory()
r = rf.get('/x/?ids=1&ids=2&ids=3&name=a&name=b')
print('request.GET.get("ids")      =', r.GET.get('ids'), '   getlist =', r.GET.getlist('ids'))
print('int(request.GET["ids"])      =', int(r.GET['ids']), '(只取到最后一个)')
r = rf.post('/x/', {'ids': [1, 2, 3], 'name': 'a'})
print('POST 表单里 ids=[1,2,3]:  getlist =', r.POST.getlist('ids'), ' get =', r.POST.get('ids'))
''')
print(o); R['request'] = o
print()
print('== 四:参数数量上限 DATA_UPLOAD_MAX_NUMBER_FIELDS')
o = run('''
from django.conf import settings
from django.test import Client
from django.http import HttpResponse
print('DATA_UPLOAD_MAX_NUMBER_FIELDS 默认 =', settings.DATA_UPLOAD_MAX_NUMBER_FIELDS)
from django.test import RequestFactory
rf = RequestFactory()
for n in (1000, 1001):
    body = '&'.join(f'k{i}=v' for i in range(n))
    r = rf.post('/x/', body, content_type='application/x-www-form-urlencoded')
    try: print(f'POST 表单 {n} 个字段 → request.POST 里 {len(r.POST)} 个')
    except Exception as e: print(f'POST 表单 {n} 个字段 →', type(e).__name__ + ':', str(e)[:90])
for n in (1000, 1001):
    r = rf.get('/x/?' + '&'.join(f'k{i}=v' for i in range(n)))
    try: print(f'GET 查询串 {n} 个参数 → request.GET 里 {len(r.GET)} 个')
    except Exception as e: print(f'GET 查询串 {n} 个参数 →', type(e).__name__ + ':', str(e)[:90])
''')
print(o); R['limit'] = o
save('d20', R)

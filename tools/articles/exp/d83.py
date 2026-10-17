import sys, os, time, json, re, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d83'); R = {}
cps = '''
import os, time
def log(s):
    with open(os.environ['CP_LOG'], 'a') as f: f.write(s + '\\n')
def cp_a(request): log('cp_a'); return {'a': 'A'}
def cp_b(request): log('cp_b'); return {'b': 'B', 'a': 'B 覆盖了 A'}
def slow(request): log('slow'); time.sleep(0.005); return {'slow': 1}
'''
files = {'proj/cps.py': cps, 'templates/page.html': 'a={{ a }} b={{ b }}', 'templates/noctx.html': 'plain', 'templates/inc.html': '{% include "noctx.html" %}{% include "noctx.html" %}'}
def build(extra_cps, name='d83'):
    return proj(name, files=files, apps=['django.contrib.contenttypes'], with_lab=False, settings_extra="\nTEMPLATES[0]['OPTIONS']['context_processors'] += %r\n" % extra_cps)
d = build(['proj.cps.cp_a', 'proj.cps.cp_b']); LG = str(DJ / 'd83' / 'cp.log')
def run(code, dd=None, **kw): open(LG, 'w').close(); rc, out = pyscript(dd or d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.test import RequestFactory\nfrom django.template.loader import render_to_string\nfrom django.shortcuts import render\nrf = RequestFactory(); req = rf.get('/')\ndef L():\n    x = open(__import__('os').environ['CP_LOG']).read().splitlines(); open(__import__('os').environ['CP_LOG'], 'w').close(); return x\nL()\n" + code, CP_LOG=LG); return out.rstrip()
print('== 一:上下文处理器什么时候运行:只对 RequestContext(render(request, …))运行')
o = run("""
r = render(req, 'page.html', {}); print('render(request, "page.html") →', r.content.decode(), ' 处理器调用:', L())
s = render_to_string('page.html', {}); print('render_to_string(无 request) →', repr(s), ' 处理器调用:', L())
s = render_to_string('page.html', {}, request=req); print('render_to_string(request=req) →', s, ' 处理器调用:', L())
""")
print(o); R['when'] = o
print()
print('== 二:每次渲染调用一次(与模板里有没有用到无关);{% include %} 不会重复调用')
o = run("""
render(req, 'noctx.html', {}); print('模板里没用任何变量,处理器仍被调用:', L())
render(req, 'inc.html', {}); print('模板里 include 了 2 次,处理器调用次数:', len(L()), '(一次渲染只跑一遍)')
for _ in range(3): render(req, 'noctx.html', {})
print('连续渲染 3 次:', len(L()), '次调用(每次渲染各一次)')
""")
print(o); R['count'] = o
print()
print('== 三:处理器的顺序与覆盖:后面的覆盖前面的;传给 render 的 context 优先级最高')
o = run("""
print('cp_a 然后 cp_b:', render(req, 'page.html', {}).content.decode(), ' 调用顺序:', L())
print('render 里显式传 a="视图里的 a":', render(req, 'page.html', {'a': '视图里的 a'}).content.decode())
""")
print(o); R['override'] = o
print()
print('== 四:处理器的开销累加到每一次渲染:加一个慢处理器(5 ms),渲染一个空模板的耗时')
d2 = build(['proj.cps.cp_a', 'proj.cps.slow'], 'd83slow')
def bench(dd):
    rc, out = pyscript(dd, """
import logging, time, statistics; logging.disable(logging.CRITICAL)
from django.test import RequestFactory
from django.shortcuts import render
req = RequestFactory().get('/'); render(req, 'noctx.html', {})
xs = []
for _ in range(40):
    t0 = time.perf_counter(); render(req, 'noctx.html', {}); xs.append((time.perf_counter() - t0) * 1000)
print('%.3f' % statistics.median(xs))
""", CP_LOG=LG); return float(out.strip().splitlines()[-1])
b0 = bench(build([], 'd83base')); b1 = bench(d2)
print(f'  没有额外处理器:每次渲染中位 {b0:.3f} ms;加一个 5 ms 的处理器:{b1:.3f} ms'); R['bench'] = dict(base=b0, slow=b1)
print()
print('== 五:默认自带的处理器提供了什么变量')
o = run("""
from django.template import engines
e = engines['django']; print('默认配置(本项目模板设置)里的 context_processors:', e.engine.template_context_processors and [f.__module__.split('.')[-1] + '.' + f.__name__ for f in e.engine.template_context_processors])
""")
print(o); R['builtin'] = o
save('d83', R)

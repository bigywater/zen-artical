import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d86'); R = {}
tags = '''
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
register = template.Library()
CALLS = []
@register.simple_tag
def hello(name, greeting='Hi'): CALLS.append(('hello', name)); return f'{greeting}, {name}'
@register.simple_tag
def raw_html(x): return '<b>%s</b>' % x
@register.simple_tag
def safe_html(x): return format_html('<b>{}</b>', x)
@register.simple_tag
def marked(x): return mark_safe('<i>' + x + '</i>')
@register.simple_tag(takes_context=True)
def who(context): return context['request'].user.username if hasattr(context['request'], 'user') else 'anon'
@register.simple_tag(takes_context=True)
def set_flag(context): context['flag'] = 'set-by-tag'; return ''
@register.inclusion_tag('item.html')
def item(name): CALLS.append(('item', name)); return {'name': name}
@register.inclusion_tag('item.html', takes_context=True)
def item_ctx(context, name): return {'name': name, 'site': context.get('site')}
@register.simple_tag
def boom(): raise ValueError('tag exploded')
'''
files = {'lab/templatetags/__init__.py': '', 'lab/templatetags/mytags.py': tags, 'templates/item.html': '<li>{{ name }}|{{ site }}</li>'}
d = proj('d86', files=files, apps=['django.contrib.contenttypes', 'lab'])
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.template import engines\nfrom django.test import RequestFactory\nimport importlib\nm = importlib.import_module('lab.templatetags.mytags')\ndef r(src, **ctx): return engines['django'].from_string('{% load mytags %}' + src).render(ctx)\n" + code); return out.rstrip()
print('== 一:simple_tag:位置参数、关键字参数、as 变量;返回值')
o = run("""
print('{% hello "ann" %}                 →', r('{% hello "ann" %}'))
print('{% hello name greeting="Yo" %}     →', r('{% hello name greeting="Yo" %}', name='bob'))
print('{% hello "cat" as msg %}{{ msg }}{{ msg }} →', r('{% hello "cat" as msg %}[{{ msg }}][{{ msg }}]'))
m.CALLS.clear(); r('{% hello "x" as msg %}{{ msg }}{{ msg }}'); print('   ↑ as 之后用两次,tag 调用次数:', len(m.CALLS))
m.CALLS.clear(); r('{% hello "x" %}{% hello "x" %}'); print('不用 as 写两次,tag 调用次数:', len(m.CALLS))
""")
print(o); R['simple'] = o
print()
print('== 二:simple_tag 的输出会被自动转义(除非返回 safe 字符串)')
o = run("""
print('返回普通字符串 <b> →', r('{% raw_html "<i>" %}'))
print('format_html 返回 →', r('{% safe_html "<i>" %}'))
print('mark_safe 返回(参数未转义!)→', r('{% marked v %}', v='<script>x</script>'))
""")
print(o); R['escape'] = o
print()
print('== 三:takes_context:读取上下文;在 tag 里写上下文变量的作用域')
o = run("""
rf = RequestFactory(); req = rf.get('/')
print('who(无 user 属性的 request) →', r('{% who %}', request=req))
print('set_flag 之后同一模板里能读到吗:', repr(r('{% set_flag %}[{{ flag }}]')), ' ← 写进 context 的变量在当前作用域内有效')
print('在 {% for %} 里 set_flag:', repr(r('{% for i in items %}{% set_flag %}{% endfor %}[{{ flag }}]', items=[1])), ' ← 循环里的写入在循环结束后不可见(context 被 push/pop)')
""")
print(o); R['ctx'] = o
print()
print('== 四:inclusion_tag:渲染另一个模板;takes_context 才能拿到外层变量;每次调用一次模板加载')
o = run("""
print('{% item "a" %} →', r('{% item "a" %}', site='S'))
print('外层变量 site 默认不会传进去:', '(见上,|后面为空)')
print('{% item_ctx "b" %} takes_context →', r('{% item_ctx "b" %}', site='S'))
m.CALLS.clear(); r('{% for i in items %}{% item i %}{% endfor %}', items=range(4)); print('循环里 4 次 inclusion_tag,tag 函数调用次数:', len(m.CALLS))
""")
print(o); R['incl'] = o
print()
print('== 五:开销:simple_tag / inclusion_tag / 过滤器 / 直接写变量,渲染 200 次的耗时(合成对比)')
o = run("""
import time, statistics
def t(src, n=200, **ctx):
    tpl = engines['django'].from_string('{% load mytags %}' + src); tpl.render(ctx); xs = []
    for _ in range(n):
        t0 = time.perf_counter(); tpl.render(ctx); xs.append((time.perf_counter() - t0) * 1e6)
    return statistics.median(xs)
print('20 处直接写 {{ v }}:              ' + str(round(t('{{ v }}' * 20, v='x'))) + ' µs')
print('20 处 simple_tag {% hello v %}:   ' + str(round(t('{% hello v %}' * 20, v='x'))) + ' µs')
print('20 处 inclusion_tag {% item v %}: ' + str(round(t('{% item v %}' * 20, v='x'))) + ' µs')
""")
print(o); R['perf'] = o
print()
print('== 六:tag 里的异常:原样抛出')
o = run("""
try: r('{% boom %}')
except Exception as e: print(type(e).__name__ + ':', e)
""")
print(o); R['err'] = o
save('d86', R)

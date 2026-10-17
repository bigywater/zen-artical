import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d85'); R = {}
tags = '''
import os
from django import template
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe
register = template.Library()
CALLS = {'n': 0}
@register.filter
def shout(value): return str(value).upper() + '!'
@register.filter
def add_str(value, arg): return f'{value}{arg}'
@register.filter(is_safe=True)
def keep_safe(value): return str(value) + '<end>'
@register.filter(needs_autoescape=True)
def bold(value, autoescape=True):
    esc = conditional_escape if autoescape else (lambda x: x)
    return mark_safe('<b>%s</b>' % esc(value))
@register.filter
def boom(value): raise ValueError('filter exploded')
@register.filter
def counted(value): CALLS['n'] += 1; return value
@register.filter
def stringy(value): return len(value)
'''
files = {'lab/templatetags/__init__.py': '', 'lab/templatetags/myf.py': tags}
d = proj('d85', files=files, apps=['django.contrib.contenttypes', 'lab'])
def run(code, dbg=None): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.template import engines\ndef r(src, **ctx): return engines['django'].from_string('{% load myf %}' + src).render(ctx)\n" + code); return out.rstrip()
print('== 一:基本用法:无参数、带参数、链式;参数只能有一个')
o = run("""
print('{{ v|shout }}          →', r('{{ v|shout }}', v='hi'))
print('{{ v|add_str:"-x" }}   →', r('{{ v|add_str:"-x" }}', v='hi'))
print('链式 {{ v|shout|add_str:"?" }} →', r('{{ v|shout|add_str:"?" }}', v='hi'))
print('变量作为参数 {{ v|add_str:suffix }} →', r('{{ v|add_str:suffix }}', v='hi', suffix='_s'))
from django.template import TemplateSyntaxError
try: r('{{ v|add_str:"a":"b" }}', v='hi')
except TemplateSyntaxError as e: print('两个参数 →', type(e).__name__ + ':', str(e)[:80])
""")
print(o); R['basic'] = o
print()
print('== 二:自动转义与过滤器:默认过滤器的返回值会被再转义;is_safe / needs_autoescape 的差别')
o = run("""
print('返回字符串的普通过滤器:', r('{{ v|shout }}', v='<i>'))
print('is_safe=True,输入是 safe:', r('{{ v|keep_safe }}', v=__import__('django.utils.safestring', fromlist=['x']).mark_safe('<i>')))
print('is_safe=True,输入不是 safe:', r('{{ v|keep_safe }}', v='<i>'))
print('needs_autoescape,自动转义开:', r('{{ v|bold }}', v='<i>'))
print('needs_autoescape,{% autoescape off %} 里:', r('{% autoescape off %}{{ v|bold }}{% endautoescape %}', v='<i>'))
""")
print(o); R['escape'] = o
print()
print('== 三:过滤器里抛异常:模板渲染失败,异常原样抛出(不会被静默吞掉);变量不存在则是 string_if_invalid')
o = run("""
try: r('{{ v|boom }}', v=1)
except Exception as e: print('boom 过滤器 →', type(e).__name__ + ':', e)
print('变量不存在:{{ nope|shout }} →', repr(r('{{ nope|shout }}')), ' ← 过滤器收到的是空字符串 "",于是得到 "!"')
print('没有对应过滤器:', end=' ')
try: r('{{ v|nofilter }}', v=1)
except Exception as e: print(type(e).__name__ + ':', str(e)[:80])
try: print(r('{{ v|stringy }}', v=None))
except Exception as e: print('对 None 用 len 的过滤器 →', type(e).__name__ + ':', e)
""")
print(o); R['errors'] = o
print()
print('== 四:调用次数:同一个过滤器表达式出现两次就调用两次;不会缓存;在 {% for %} 里每次迭代一次')
o = run("""
import importlib; m = importlib.import_module('lab.templatetags.myf'); m.CALLS['n'] = 0
r('{{ v|counted }}{{ v|counted }}', v=1); print('模板里写两次:', m.CALLS['n'])
m.CALLS['n'] = 0; r('{% for i in items %}{{ i|counted }}{% endfor %}', items=range(5)); print('5 次循环:', m.CALLS['n'])
m.CALLS['n'] = 0; r('{% with x=v|counted %}{{ x }}{{ x }}{% endwith %}', v=1); print('{% with %} 先存下来再用两次:', m.CALLS['n'])
""")
print(o); R['calls'] = o
print()
print('== 五:过滤器只能放在模板变量后;它们和「已注册库」的关系:必须 {% load %}')
o = run("""
from django.template import TemplateSyntaxError
try: engines['django'].from_string('{{ v|shout }}').render({'v': 1})
except TemplateSyntaxError as e: print('没有 {% load myf %}:', type(e).__name__ + ':', str(e)[:90])
""")
print(o); R['load'] = o
save('d85', R)

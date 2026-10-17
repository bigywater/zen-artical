import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dj import *
tee('d84'); R = {}
d = proj('d84', apps=['django.contrib.contenttypes'], with_lab=False)
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.template import engines, Context\nfrom django.utils.safestring import mark_safe\nfrom django.utils.html import escape, format_html\ndef r(src, **ctx): return engines['django'].from_string(src).render(ctx)\n" + code); return out.rstrip()
print('== 一:自动转义:五个字符;{{ x }} 默认转义,|safe 关闭')
o = run("""
x = '<b>&"\\'</b>'
print('{{ x }}          →', r('{{ x }}', x=x))
print('{{ x|safe }}     →', r('{{ x|safe }}', x=x))
print('mark_safe 的对象 →', r('{{ x }}', x=mark_safe(x)))
print('{% autoescape off %}{{ x }}{% endautoescape %} →', r('{% autoescape off %}{{ x }}{% endautoescape %}', x=x))
print('对同一个字符串既 safe 又 upper(escape 时机):', r('{{ x|safe|upper }}', x='<b>a&amp;b</b>'))
""")
print(o); R['basic'] = o
print()
print('== 二:HTML 转义 ≠ 各上下文都安全:属性里的 javascript: URL、<script> 里的变量')
o = run("""
evil = 'javascript:alert(1)'
print('href="{{ url }}" →', r('<a href="{{ url }}">x</a>', url=evil), '  ← 不会被转义或拦截(需要自己校验协议)')
name = '";alert(1);//'
print('<script>var n = "{{ name }}";</script> →', r('<script>var n = "{{ name }}";</script>', name=name), '  ← HTML 转义把 " 变成 &quot;,在 JS 字符串里并不是安全的写法')
print('用 escapejs 过滤器:', r('<script>var n = "{{ name|escapejs }}";</script>', name=name))
print('用 json_script(推荐):', r('{{ data|json_script:"d" }}', data={'name': name, 'x': '</script><b>'}))
""")
print(o); R['context'] = o
print()
print('== 三:非引号包裹的属性、单引号属性:Django 转义了单引号 → &#x27;')
o = run("""
v = 'x onmouseover=alert(1)'
print('<input value={{ v }}> →', r('<input value={{ v }}>', v=v), '  ← 属性没加引号,空格仍能截断')
print('<input value=\\'{{ v2 }}\\'> →', r("<input value='{{ v2 }}'>", v2="' onclick='x"))
""")
print(o); R['attr'] = o
print()
print('== 四:在 Python 里拼 HTML:format_html 会转义参数;字符串 + 拼接不会')
o = run("""
u = '<img src=x onerror=alert(1)>'
print('format_html("<p>{}</p>", u) →', format_html('<p>{}</p>', u))
print('mark_safe("<p>" + u + "</p>") →', mark_safe('<p>' + u + '</p>'), '  ← 用户输入被原样标成安全')
print('escape(u) →', escape(u))
""")
print(o); R['py'] = o
print()
print('== 五:哪些位置的值不会被自动转义:模板里的字面量、safe 过滤器的返回值、标记为 safe 的对象')
o = run("""
print('模板里的字面量 {{ "<i>lit</i>" }} →', r('{{ "<i>lit</i>" }}'))
print('join 过滤器对列表元素转义:', r('{{ items|join:", " }}', items=['<a>', 'b']))
print('linebreaksbr 对内容转义、只把换行变成 <br>:', r('{{ t|linebreaksbr }}', t='<x>\\nline2'))
print('urlize 转链接并转义:', r('{{ t|urlize }}', t='see http://a.com/?q=<x>'))
""")
print(o); R['others'] = o
save('d84', R)

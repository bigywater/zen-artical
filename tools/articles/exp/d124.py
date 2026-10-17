import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sec import *
tee('d124'); R = {}
d = proj('d124', apps=['django.contrib.contenttypes'], with_lab=False, middleware=[])
def run(code): rc, out = pyscript(d, "import logging; logging.disable(logging.CRITICAL)\nfrom django.template import Template, Context\nfrom django.utils.safestring import mark_safe\nfrom django.utils.html import format_html, escape\nP = '<script>alert(1)</script>'\ndef r(tpl, **ctx): return Template(tpl).render(Context(ctx))\ndef show(label, out, bad='<script>'): print(f'  {label:<44} {out!r:<60} 含原样的 <script>: {bad in out}')\n" + code); return out.rstrip()
print('== 一:自动转义:同一个恶意字符串 P = "<script>alert(1)</script>" 在不同写法下的渲染结果')
o = run("""
show('{{ p }}', r('{{ p }}', p=P))
show('{{ p|safe }}', r('{{ p|safe }}', p=P))
show('{% autoescape off %}{{ p }}{% endautoescape %}', r('{% autoescape off %}{{ p }}{% endautoescape %}', p=P))
show('{{ p }}(变量被 mark_safe 过)', r('{{ p }}', p=mark_safe(P)))
show('format_html("<b>{}</b>", P)', str(format_html('<b>{}</b>', P)))
show('mark_safe("<b>" + P + "</b>")(拼接)', str(mark_safe('<b>' + P + '</b>')))
""")
print(o); R['auto'] = o
print()
print('== 二:属性与 URL 上下文:自动转义能挡住引号逃逸,但挡不住 javascript: URL')
o = run("""
q = '" onmouseover="alert(1)'
out = r('<div title="{{ q }}">x</div>', q=q); print('  title="{{ q }}"         →', out)
out = r('<div title={{ q }}>x</div>', q='x onmouseover=alert(1)'); print('  title={{ q }}(没加引号)→', out, '← 空格没被转义,多出了一个属性')
out = r('<a href="{{ u }}">x</a>', u='javascript:alert(1)'); print('  href="{{ u }}",u = javascript:alert(1) →', out, '  (原样保留)')
from django.utils.http import url_has_allowed_host_and_scheme
for u in ('javascript:alert(1)', 'https://example.com/x', '/local/path', '//evil.example/x'):
    print(f'  url_has_allowed_host_and_scheme({u!r:<28}, allowed_hosts={{"example.com"}}) →', url_has_allowed_host_and_scheme(u, allowed_hosts={'example.com'}))
""")
print(o); R['ctx'] = o
print()
print('== 三:把数据放进 <script>:escapejs / json_script')
o = run("""
data = {'name': '</script><script>alert(1)</script>', 'n': 1}
out = r('<script>var d = {{ d|escapejs }};</script>', d=data['name']); print('  escapejs        →', out)
out = r('{{ d|json_script:"cfg" }}', d=data); print('  json_script     →', out)
print('  json_script 输出里含原样的 </script>:', out.count('</script>') > 1)
out = r('<script>var name = "{{ n }}";</script>', n='";alert(1);//'); print('  只用自动转义放进 JS 字符串 →', out, ' ← 引号被转成 &quot;,但这不是 JS 的转义方式,不要这样写')
""")
print(o); R['js'] = o
print()
print('== 四:过滤器与 |safe 的组合(在模板里渲染同一个 P)')
o = run("""
for tpl in ('{{ t|linebreaks }}', '{{ t|urlize }}', '{{ t|linebreaksbr }}', '{{ t|truncatechars:40 }}', '{{ t|striptags }}', '{{ t|safe|linebreaks }}', '{{ t|safe|truncatechars:40 }}'):
    out = r(tpl, t=P); print(f'  {tpl:<30} → {out!r:<52} 含原样的 <script>: {"<script>" in out}')
""")
print(o); R['misuse'] = o
save('d124', R)

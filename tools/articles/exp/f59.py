import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
tee('f59'); R = {}
from flask import Flask, render_template_string
from markupsafe import Markup, escape, soft_str
app = Flask('mk'); app.logger.disabled = True
def T(tpl, **kw):
    with app.test_request_context('/'): return render_template_string(tpl, **kw)
print('== 一:Markup 是 str 的子类,表示「已经是安全的 HTML」;escape 把字符串转成 Markup')
m = Markup('<b>x</b>'); print('  Markup("<b>x</b>"):', repr(m), '| 是 str:', isinstance(m, str), '| 有 __html__:', hasattr(m, '__html__')); R['basic'] = [repr(m), isinstance(m, str), hasattr(m, '__html__')]
e = escape('<b>&"\''); print('  escape("<b>&\\"\'"):', repr(e), '| 类型:', type(e).__name__); R['escape'] = [repr(e), type(e).__name__]
print('  对 Markup 再 escape 不会双重转义:', repr(escape(Markup('<b>'))), '| escape(Markup("&amp;")):', repr(escape(Markup('&amp;')))); R['no_double'] = [repr(escape(Markup('<b>'))), repr(escape(Markup('&amp;')))]
print('  escape(None):', repr(escape(None)), '| escape(5):', repr(escape(5)), '| escape(对象有 __html__):', repr(escape(type("H", (), {"__html__": lambda s: "<i>已是 HTML</i>"})()))); R['types'] = [repr(escape(None)), repr(escape(5))]
print()
print('== 二:Markup 的运算:与普通字符串拼接时,普通字符串会被转义;反过来 str + Markup 也一样')
u = '<script>alert(1)</script>'
print('  Markup("<b>") + u      →', repr(Markup('<b>') + u)); print('  u + Markup("<b>")      →', repr(u + Markup('<b>'))); print('  Markup("<b>%s</b>") % u →', repr(Markup('<b>%s</b>') % u)); print('  Markup("<b>{}</b>").format(u) →', repr(Markup('<b>{}</b>').format(u))); print('  Markup(f"<b>{u}</b>")(错误写法,先格式化再标记安全)→', repr(Markup(f'<b>{u}</b>'))); print('  "<b>%s</b>" % u 再 Markup(...) →', repr(Markup('<b>%s</b>' % u)))
R['ops'] = [repr(Markup('<b>') + u), repr(u + Markup('<b>')), repr(Markup('<b>%s</b>') % u), repr(Markup('<b>{}</b>').format(u)), repr(Markup(f'<b>{u}</b>'))]
print('  Markup.join:', repr(Markup('<br>').join(['<a>', 'b&c'])), '| Markup 拼接 Markup:', repr(Markup('<i>') + Markup('<b>'))); R['join'] = repr(Markup('<br>').join(['<a>', 'b&c']))
print('  切片、upper、replace 的结果仍然是 Markup:', type(Markup('<b>x</b>')[:3]).__name__, type(Markup('<b>x</b>').upper()).__name__, type(Markup('<b>x</b>').replace('x', '<y>')).__name__, '| replace 里的新文本被转义:', repr(Markup('<b>x</b>').replace('x', '<y>'))); R['methods'] = repr(Markup('<b>x</b>').replace('x', '<y>'))
print()
print('== 三:模板里的 |safe、|e、|forceescape、|striptags、|string')
tpl = lambda f: T('{{ x' + f + ' }}', x='<b>A &amp; B</b>')
for f in ('', '|safe', '|e', '|escape', '|forceescape', '|striptags', '|string', '|upper', '|safe|upper', '|upper|safe'): out = tpl(f); R.setdefault('filters', {})[f or '(无)'] = out; print(f'  x{f:<14} → {out}')
print()
print('== 四:对象的 __html__ 方法:模板输出对象时会调用它,返回值被当作安全 HTML')
class Widget:
    def __init__(self, label): self.label = label
    def __html__(self): return Markup('<button>{}</button>').format(self.label)
    def __str__(self): return f'Widget({self.label})'
print('  {{ w }} →', T('{{ w }}', w=Widget('<保存>')), '| {{ w|string }} →', T('{{ w|string }}', w=Widget('<保存>')), '| {{ [w]|join(",") }} →', T('{{ [w]|join(",") }}', w=Widget('<保存>'))); R['html'] = [T('{{ w }}', w=Widget('<保存>')), T('{{ w|string }}', w=Widget('<保存>')), T('{{ [w]|join(",") }}', w=Widget('<保存>'))]
print()
print('== 五:Python 里把 str 变成 Markup 的几种方式的安全性:一个小测试——对同一个恶意输入的结果')
bad = '"><img src=x onerror=alert(1)>'
cases = {'Markup(f"<a title=\\"{u}\\">")': lambda: Markup(f'<a title="{bad}">'), 'Markup("<a title=\\"{}\\">").format(u)': lambda: Markup('<a title="{}">').format(bad), 'Markup("<a title=\\"%s\\">") % u': lambda: Markup('<a title="%s">') % bad, 'Markup("<a title=\\"") + u + Markup("\\">")': lambda: Markup('<a title="') + bad + Markup('">'), '"<a title=\\"" + escape(u) + "\\">"': lambda: '<a title="' + escape(bad) + '">'}
R['five'] = {}
for k, f in cases.items(): out = str(f()); safe = '<img' not in out; R['five'][k] = safe; print(f'  {k:<46} → {"安全" if safe else "危险"} {out}')
print()
print('== 六:soft_str 与 Markup.striptags/unescape')
print('  Markup("<p>a &amp; <b>b</b></p>").striptags() →', repr(Markup('<p>a &amp; <b>b</b></p>').striptags()), '| Markup("&lt;b&gt;").unescape() →', repr(Markup('&lt;b&gt;').unescape())); R['strip'] = [repr(Markup('<p>a &amp; <b>b</b></p>').striptags()), repr(Markup('&lt;b&gt;').unescape())]
save('f59', R)

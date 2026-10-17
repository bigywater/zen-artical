import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f58'); R = {}
from flask import Flask, render_template, render_template_string, request
from markupsafe import Markup
d = mkapp('f58', {'templates/page.html': '<p>{{ x }}</p>', 'templates/page.htm': '<p>{{ x }}</p>', 'templates/page.xml': '<a>{{ x }}</a>', 'templates/page.xhtml': '<p>{{ x }}</p>', 'templates/page.txt': 'text: {{ x }}', 'templates/page.js': 'var a = "{{ x }}";', 'templates/page.json': '{"a": "{{ x }}"}', 'templates/page.svg': '<text>{{ x }}</text>', 'templates/page.html.j2': '<p>{{ x }}</p>', 'templates/noext': '<p>{{ x }}</p>', 'templates/page.jinja': '<p>{{ x }}</p>'})
sys.path.insert(0, str(d)); os.chdir(d)
app = Flask('esc', root_path=str(d)); app.logger.disabled = True
X = '<b id="a" onclick=\'x()\'>&</b>'
print('== 一:哪些模板文件名会自动转义(Flask 的 select_jinja_autoescape:按扩展名)')
R['ext'] = {}
with app.test_request_context('/'):
    for n in ('page.html', 'page.htm', 'page.xml', 'page.xhtml', 'page.svg', 'page.txt', 'page.js', 'page.json', 'page.html.j2', 'page.jinja', 'noext'):
        out = render_template(n, x=X); esc = '&lt;' in out; R['ext'][n] = esc; print(f'  {n:<14} → {"转义" if esc else "不转义":<4} {out[:50]}')
    out = render_template_string('{{ x }}', x=X); print('  render_template_string →', '转义' if '&lt;' in out else '不转义', out); R['string'] = '&lt;' in out
print(f'  Flask 的规则:扩展名是 .html .htm .xml .xhtml .svg 之一就开启(render_template_string 总是开启)')
print()
print('== 二:转义了哪些字符')
with app.test_request_context('/'): out = render_template_string('{{ x }}', x='<>&\'"/\\`'); print('  输入 <>&\'"/\\` →', out); R['chars'] = out
print()
print('== 三:放在 HTML 文本里安全,放在其它上下文里不一定安全——五种上下文下的实际输出')
payloads = {'text': ('<p>{{ x }}</p>', '<script>alert(1)</script>'), '带引号的属性': ('<input value="{{ x }}">', '" onfocus="alert(1)'), '不带引号的属性': ('<input value={{ x }}>', 'a onfocus=alert(1)'), 'href(javascript:)': ('<a href="{{ x }}">link</a>', 'javascript:alert(1)'), '<script> 里的字符串': ('<script>var a = "{{ x }}";</script>', '";alert(1);//'), '<script> 里的 tojson': ('<script>var a = {{ x|tojson }};</script>', '";alert(1);//'), '<style> 里': ('<style>p {color: {{ x }}}</style>', 'red;} body{display:none'), '单引号属性且值含单引号': ("<input value='{{ x }}'>", "' onfocus='alert(1)")}
R['ctx'] = {}
with app.test_request_context('/'):
    for label, (tpl, pay) in payloads.items():
        out = render_template_string(tpl, x=pay); R['ctx'][label] = out; print(f'  {label:<20} 输入 {pay!r:<34} → {out}')
print('  观察:引号被转义的属性(带引号)是安全的;不带引号的属性、href 里的 javascript: 协议、<script> 里的字符串都没有被「HTML 转义」拯救。')
print()
print('== 四:模板注入(SSTI):把用户输入拼进模板「源码」再渲染,用户能执行表达式——对比正确写法')
@app.get('/hello-bad')
def hello_bad(): return render_template_string('<h1>你好 ' + request.args.get('name', '') + '</h1>')
@app.get('/hello-good')
def hello_good(): return render_template_string('<h1>你好 {{ name }}</h1>', name=request.args.get('name', ''))
app.config['SECRET_KEY'] = 'lab-secret'
c = app.test_client()
for label, path in (('错误写法', '/hello-bad'), ('正确写法', '/hello-good')):
    for pay in ('Ann', '{{ 7*7 }}', '{{ config.SECRET_KEY }}'):
        r = c.get(path, query_string={'name': pay}); out = r.get_data(as_text=True).strip(); R.setdefault('ssti', {})[f'{label}:{pay}'] = out; print(f'  {label} name={pay:<26} → {out}')
print()
print('== 五:|safe 与 {% autoescape false %}:关闭转义的两种方式')
with app.test_request_context('/'):
    print('  {{ x|safe }}:', render_template_string('{{ x|safe }}', x='<b>bold</b>')); print('  {% autoescape false %}…{% endautoescape %}:', render_template_string('{% autoescape false %}{{ x }}{% endautoescape %}', x='<b>bold</b>')); print('  {% autoescape true %}(在 .txt 里开启):', end=' '); R['safe'] = [render_template_string('{{ x|safe }}', x='<b>bold</b>'), render_template_string('{% autoescape false %}{{ x }}{% endautoescape %}', x='<b>bold</b>')]
    print(render_template_string('{% autoescape true %}{{ x }}{% endautoescape %}', x='<b>bold</b>'))
print()
print('== 六:tojson 过滤器:在 <script> 里安全地输出 JSON(Flask 的 tojson 额外转义 < > & \')')
with app.test_request_context('/'):
    out = render_template_string('{{ x|tojson }}', x={'a': '</script><script>alert(1)</script>', 'q': "it's & <b>"}); print('  ', out); R['tojson'] = out
    tt = render_template_string('{{ (x|tojson).__class__.__name__ }}', x=1); print('  tojson 返回值的类型:', tt, '(Markup = 已标记为安全,不会再被转义)'); R['tojson_type'] = tt
save('f58', R)

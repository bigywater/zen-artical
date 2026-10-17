import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sl import *
tee('s33'); reset_s()
d = sdir('s33')
def P(title, code):
    print(title)
    rc, out, t = py(d, env={'PYTHONWARNINGS': 'ignore'}, code='from scrapy import FormRequest\nfrom scrapy.http import HtmlResponse\nfrom urllib.parse import parse_qsl, unquote_plus\ndef R(html, url="http://site.test/dir/page.html"): return HtmlResponse(url, body=html.encode(), encoding="utf-8")\ndef show(tag, req):\n    body = req.body.decode()\n    print(f"  {tag}")\n    print(f"      {req.method} {req.url}")\n    if body: print(f"      body: {parse_qsl(body, keep_blank_values=True)}")\n    ct = req.headers.get("Content-Type"); print(f"      Content-Type: {ct.decode() if ct else None}")\n' + code)
    print(out)
FORM = '''<html><body>
<form id="login" name="loginform" action="/do/login?next=1" method="post">
  <input type="hidden" name="csrf" value="tok123">
  <input type="text" name="user" value="">
  <input type="password" name="pass" value="">
  <input type="checkbox" name="remember" value="yes" checked>
  <input type="checkbox" name="newsletter" value="on">
  <input type="radio" name="plan" value="free"> <input type="radio" name="plan" value="pro" checked>
  <select name="lang"><option value="en">en</option><option value="zh" selected>zh</option></select>
  <select name="multi" multiple><option value="a" selected>a</option><option value="b" selected>b</option><option value="c">c</option></select>
  <textarea name="bio">hello
world</textarea>
  <input type="text" name="locked" value="x" disabled>
  <input type="submit" name="act" value="Login">
  <input type="submit" name="act" value="Register">
  <button type="submit" name="btn" value="b1">Go</button>
</form>
<form id="search" action="search" method="get"><input name="q" value="python"><input type="submit" value="Search"></form>
</body></html>'''
print('== 一:FormRequest.from_response 的状态')
rc, out, t = py(d, 'import warnings\nfrom scrapy import FormRequest\nfrom scrapy.http import HtmlResponse\nr = HtmlResponse("http://x/", body=b"<form><input name=a value=1></form>")\nwith warnings.catch_warnings(record=True) as w:\n    warnings.simplefilter("always")\n    FormRequest.from_response(r)\n    print("  警告:", w[0].category.__name__ + ": " + str(w[0].message))\nwith warnings.catch_warnings(record=True) as w:\n    warnings.simplefilter("always")\n    FormRequest("http://x/", formdata={"a": "1"})\n    print("  FormRequest(url, formdata=…) 直接构造的警告数:", len(w))')
print(out)
P('== 二:from_response 默认从表单里收集什么:隐藏字段、文本框的默认值、选中的 checkbox / radio / select、textarea;disabled 字段和没选中的 checkbox 不要;提交按钮默认点第一个 (name=act, value=Login)', f"""
r = R({FORM!r})
req = FormRequest.from_response(r, formid='login', formdata={{'user': 'alice', 'pass': 'pw'}})
show('formid="login",formdata 填 user、pass', req)
""")
P('== 三:选哪个表单:formid / formname / formnumber / formxpath / formcss;默认取第一个表单', f"""
r = R({FORM!r})
for tag, kw in (('(不指定)默认第一个', {{}}), ('formnumber=1', dict(formnumber=1)), ('formname="loginform"', dict(formname='loginform')), ('formid="search"', dict(formid='search')), ('formxpath="//form[@action=\\'search\\']"', dict(formxpath="//form[@action='search']")), ('formcss="form#search"', dict(formcss='form#search'))):
    req = FormRequest.from_response(r, **kw)
    print(f'  {{tag:<42}}→ {{req.method}} {{req.url}}')
try: FormRequest.from_response(r, formnumber=5)
except Exception as e: print('  formnumber=5:抛', type(e).__name__, e)
try: FormRequest.from_response(R('<html>no form</html>'))
except Exception as e: print('  页面里没有表单:抛', type(e).__name__, e)
""")
P('== 四:提交按钮:clickdata 选哪个按钮,dont_click=True 不点任何按钮', f"""
r = R({FORM!r})
for tag, kw in (('默认(第一个提交按钮)', {{}}), ('clickdata={{"value": "Register"}}', dict(clickdata={{'value': 'Register'}})), ('clickdata={{"name": "btn"}}', dict(clickdata={{'name': 'btn'}})), ('clickdata={{"nr": 0}}(form.inputs 的第 0 个是隐藏字段 csrf)', dict(clickdata={{'nr': 0}})), ('clickdata={{"nr": 12}}(第 13 个控件)', dict(clickdata={{'nr': 12}})), ('clickdata={{"value": "Nope"}}(没有匹配)', dict(clickdata={{'value': 'Nope'}})), ('dont_click=True', dict(dont_click=True))):
    try:
        req = FormRequest.from_response(r, formid='login', **kw)
        pairs = parse_qsl(req.body.decode(), keep_blank_values=True)
        print(f'  {{tag:<52}}→ 按钮相关字段 {{[p for p in pairs if p[0] in ("act", "btn")]}}')
    except Exception as e: print(f'  {{tag:<52}}→ 抛 {{type(e).__name__}}: {{e}}')
""")
P('== 五:formdata 覆盖或追加字段;值为 None 的字段被删除;列表值产生多个同名参数', f"""
r = R({FORM!r})
req = FormRequest.from_response(r, formid='login', formdata={{'remember': None, 'plan': 'enterprise', 'extra': ['x', 'y'], 'user': '中文'}}, dont_click=True)
show('formdata={{remember: None, plan: enterprise, extra: [x, y], user: 中文}}', req)
""")
P('== 六:action 与 method:相对 action 按页面 URL(或 <base>)补全;GET 表单把字段放进 URL 查询串;method 可以用参数覆盖', f"""
r = R({FORM!r}, 'http://site.test/dir/page.html')
show('POST 表单 action=/do/login?next=1', FormRequest.from_response(r, formid='login', dont_click=True))
show('GET 表单 action=search(相对路径)', FormRequest.from_response(r, formid='search'))
show('GET 表单,参数 method="POST" 覆盖', FormRequest.from_response(r, formid='search', method='POST'))
rb = R('<html><head><base href="http://other.test/base/"></head><body><form action="x"><input name="a" value="1"></form></body></html>', 'http://site.test/p.html')
show('<base href> 下的相对 action', FormRequest.from_response(rb))
show('表单没有 action', FormRequest.from_response(R('<form><input name="a" value="1"></form>', 'http://site.test/here?old=1')))
show('FormRequest(url, formdata={{…}}) 直接构造(值都是字符串)', FormRequest('http://site.test/post', formdata={{'k': 'v', 'n': '1', 'list': ['a', 'b']}}))
try: FormRequest('http://site.test/post', formdata={{'n': 1}})
except Exception as e: print('  formdata 里放整数 1:抛', type(e).__name__, str(e)[:60])
show('FormRequest(url, formdata=…, method="GET")', FormRequest('http://site.test/get?x=1', formdata={{'k': 'v'}}, method='GET'))
""")
P('== 七:不支持的东西:文件上传(multipart)——表单 enctype 被忽略;multipart 需要自己拼', f"""
r = R('<form action="/up" method="post" enctype="multipart/form-data"><input name="title" value="t"><input type="file" name="f"></form>')
req = FormRequest.from_response(r)
show('enctype="multipart/form-data" 的表单', req)
print('  type=file 的字段是否出现在请求体里:', 'f=' in req.body.decode(), '(没有出现)' if 'f=' not in req.body.decode() else '')
""")

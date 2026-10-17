import sys, os, re, subprocess, importlib.metadata as md; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
tee('p45')
d = pdir('p45')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--target', str(d / 'site'), 'beautifulsoup4', 'html5lib', 'selectolax'], capture_output=True, env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()})
sys.path.insert(0, str(d / 'site'))
import lxml.html, lxml.etree, html5lib
from bs4 import BeautifulSoup
from selectolax.lexbor import LexborHTMLParser as HTMLParser
V = {n: md.version(n) for n in ('lxml', 'beautifulsoup4', 'html5lib', 'selectolax')}

CASES = [
 ('未闭合的 <p>', '<p>one<p>two'), ('错位嵌套的格式标签', '<b><i>x</b>y</i>'), ('表格没有 tbody', '<table><tr><td>a</td></tr></table>'), ('表格里的游离文字', '<table>text<tr><td>a</td></tr></table>'),
 ('嵌套的 <a>', '<a href=1>x<a href=2>y</a></a>'), ('<div> 里的 <p> 被 </div> 截断', '<div><p>x</div>y</p>'), ('重复的属性', '<a href=x.html href=y.html>t</a>'), ('</br> 结束标签', 'a</br>b'),
 ('属性值缺少结尾引号', '<a href="x>text</a><a href="y">z</a>'), ('没有分号的实体', '&copy 2026 &amp &notit; &lt'), ('<script> 里有 </div>', '<script>var s = "</div>";</script><p>after</p>'),
 ('<li> 没有 <ul>', '<li>a<li>b'), ('<select> 里的未闭合 <option>', '<select><option>a<option>b</select>'), ('<p> 里放 <table>', '<p>t<table><tr><td>x</td></tr></table>'),
 ('自闭合的非空元素 <div/>', '<div/>x<span/>y'), ('嵌套的 <form>', '<form id=a><form id=b><input></form></form>'), ('<textarea> 里的标签', '<textarea><b>bold</b></textarea>'),
 ('大小写混用与奇怪属性', '<DIV CLASS=A Id="b" data-X=1><P>x</P></DIV>'), ('<td> 在 <table> 之外', '<td>a</td><td>b</td>'), ('<title> 里的标签', '<title><b>t</b></title><p>x</p>'), ('注释 <!-- a -- b -->', 'x<!-- a -- b -->y'), ('<!-->', 'x<!-->y'),
]
def doc(snip): return f'<!doctype html><html><head><meta charset="utf-8"></head><body>{snip}</body></html>'
def _sort_attrs(m):
    attrs = re.findall(r'\s+([^\s=>/]+)(?:=("[^"]*"|\S+))?', m.group(2)); attrs.sort()
    return '<' + m.group(1) + ''.join(f' {k}={v}' if v else f' {k}' for k, v in attrs) + '>'
def norm(s):
    s = re.sub(r'\s+', ' ', s).strip(); s = re.sub(r'\s*/>', '>', s); s = s.replace('&nbsp;', '\xa0')
    s = re.sub(r'<(/?)([A-Za-z0-9]+)', lambda m: f'<{m.group(1)}{m.group(2).lower()}', s)
    return re.sub(r'<([a-z0-9]+)((?:\s+[^\s=>/]+(?:="[^"]*"|=\S+)?)*)\s*>', _sort_attrs, s)
import html as _html
def inner_lxml(el): return _html.escape(el.text or '', quote=False) + ''.join(lxml.html.tostring(c, encoding='unicode') for c in el)
def p_lxml(h):
    root = lxml.html.document_fromstring(h); return inner_lxml(root.body)
def p_html5lib(h):
    tree = html5lib.parse(h, treebuilder='etree', namespaceHTMLElements=False)
    out = html5lib.serializer.HTMLSerializer(omit_optional_tags=False, quote_attr_values='always', minimize_boolean_attributes=False, escape_lt_in_attrs=True, resolve_entities=False)
    full = out.render(html5lib.getTreeWalker('etree')(tree)); m = re.search(r'<body[^>]*>(.*)</body>', full, re.S); return m.group(1) if m else full
def bs(h, f): return BeautifulSoup(h, f).body.decode_contents() if BeautifulSoup(h, f).body is not None else '(没有 body)'
PARS = [(f'lxml.html {V["lxml"]}', p_lxml), (f'html5lib {V["html5lib"]}', p_html5lib), (f'bs4 + html.parser', lambda h: bs(h, 'html.parser')), (f'bs4 + lxml', lambda h: bs(h, 'lxml')), (f'bs4 + html5lib', lambda h: bs(h, 'html5lib')),
        (f'selectolax {V["selectolax"]}', lambda h: HTMLParser(h).body.inner_html)]

with Srv(lambda h: h.reply(200, DOCS[h.path].encode(), headers={'Content-Type': 'text/html; charset=utf-8'})) as sv:
    DOCS = {f'/{i}': doc(sn) for i, (_, sn) in enumerate(CASES)}
    with Chrome(free_port(9970), d) as ch:
        pg = ch.new_page(); truth = []
        for i in range(len(CASES)):
            pg.goto(sv.url(f'/{i}')); truth.append(pg.eval('document.body.innerHTML'))
        ver = ch.version; pg.close()
print(f'== 一:{len(CASES)} 个残缺 HTML 片段(放在 <body> 里),标准答案是真实的 {ver}(headless)解析出来的 body.innerHTML;下面逐个解析器看是否与它一致(比较前统一了空白、标签名大小写、<br/> 与 <br>、属性顺序)')
res = {n: [] for n, _ in PARS}; outs = {}
for i, (lab, sn) in enumerate(CASES):
    for n, f in PARS:
        try: o = f(doc(sn))
        except Exception as e: o = f'抛出 {type(e).__name__}'
        outs[(i, n)] = o; res[n].append(norm(o) == norm(truth[i]))
print(f'  {"解析器":<26}{"与 Chrome 一致的片段数":>20}')
for n, _ in PARS: print(f'  {n:<26}{sum(res[n]):>12} / {len(CASES)}')
print('== 二:每个片段 Chrome 解析成什么、以及哪些解析器给出不同的结果')
for i, (lab, sn) in enumerate(CASES):
    bad = [n for n, _ in PARS if not res[n][i]]
    print(f'  {lab}:输入 {sn!r}')
    print(f'      Chrome → {truth[i]!r}')
    for n in bad: print(f'      {n} → {outs[(i, n)]!r}')
    if not bad: print('      其它解析器全部一致')
purge()

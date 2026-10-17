import sys, os, re, json, subprocess, html as H, importlib.metadata as md; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p49')
d = pdir('p49')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--target', str(d / 'site'), 'json5'], capture_output=True, env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()})
sys.path.insert(0, str(d / 'site'))
import json5, lxml.html
DATA = {'name': 'Widget', 'offers': {'price': 12.5, 'currency': 'CNY'}, 'tags': ['a', 'b'], 'desc': 'says }; and </div> and "quotes"', 'big': 9007199254740993}
J = json.dumps(DATA, ensure_ascii=False)
def page(body): return f'<!doctype html><html><head><meta charset="utf-8"><title>t</title></head><body><h1>x</h1>{body}</body></html>'
PAGES = {
 'JSON-LD(一个)': page(f'<script type="application/ld+json">{J}</script>'),
 '__NEXT_DATA__': page(f'<script id="__NEXT_DATA__" type="application/json">{json.dumps({"props": {"pageProps": DATA}}, ensure_ascii=False)}</script>'),
 'window.__STATE__ = {…};后面还有 JS': page(f'<script>window.__STATE__ = {J};\nwindow.other = {{"x": 1}}; console.log("done");</script>'),
 'JS 对象字面量(单引号、无引号键、末尾逗号、undefined)': page("<script>window.__STATE__ = {name: 'Widget', price: 12.5, tags: ['a', 'b',], missing: undefined,};</script>"),
 'JSON 里含 <\\/script>(合法转义)': page('<script type="application/ld+json">' + json.dumps({'html': '</script><b>x</b>', 'n': 1}, ensure_ascii=False).replace('</', '<\\/') + '</script>'),
 '数据在属性里(&quot; 实体)': page(f'<div data-product="{H.escape(J)}"></div>'),
 '两个 JSON-LD(其中一个是 @graph)': page('<script type="application/ld+json">{"@type":"Product","name":"A"}</script><script type="application/ld+json">{"@graph":[{"@type":"Org","name":"O"},{"@type":"WebSite","name":"W"}]}</script>'),
 'JSON-LD 里有注释和末尾逗号(不是合法 JSON)': page('<script type="application/ld+json">{ /* product */ "name": "A", "price": 5, }</script>'),
 'JSON 字符串里含 </script>(没有转义)': page('<script type="application/ld+json">{"html": "</script><b>x</b>", "n": 1}</script>'),
}
def m_regex(html):
    ms = re.findall(r'<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.*?)</script>', html, re.S)
    return [json.loads(x) for x in ms]
def m_lxml(html):
    doc = lxml.html.fromstring(html); out = []
    for t in doc.xpath('//script[@type="application/ld+json" or @type="application/json"]/text()'): out.append(json.loads(t))
    for a in doc.xpath('//@data-product'): out.append(json.loads(a))
    return out
def m_lxml_json5(html):
    doc = lxml.html.fromstring(html); out = []
    for t in doc.xpath('//script[@type="application/ld+json" or @type="application/json"]/text()'): out.append(json5.loads(t))
    return out
def scan_balanced(text, start):
    """从 text[start] 的 { 起,按花括号配对(跳过字符串)找到结尾,返回子串"""
    depth = 0; i = start; q = None
    while i < len(text):
        c = text[i]
        if q:
            if c == '\\': i += 1
            elif c == q: q = None
        elif c in '"\'': q = c
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return text[start:i + 1]
        i += 1
    raise ValueError('括号不配对')
def assign_text(html):
    doc = lxml.html.fromstring(html); return doc.xpath('//script/text()')[0]
def m_assign_regex(html):
    m = re.search(r'window\.__STATE__\s*=\s*(\{.*?\});', assign_text(html), re.S); return [json.loads(m.group(1))]
def m_assign_raw(html):
    t = assign_text(html); j = t.index('{', t.index('window.__STATE__')); obj, end = json.JSONDecoder().raw_decode(t[j:]); return [obj]
def m_assign_scan_json5(html):
    t = assign_text(html); j = t.index('{', t.index('window.__STATE__')); return [json5.loads(scan_balanced(t, j))]
def m_assign_scan_json5_undef(html):
    t = assign_text(html); j = t.index('{', t.index('window.__STATE__')); return [json5.loads(re.sub(r'\bundefined\b', 'null', scan_balanced(t, j)))]
def ok(f, html):
    try:
        r = f(html)
        if not r: return '空'
        return '✓' + (f'({len(r)})' if len(r) > 1 else '')
    except Exception as e: return '✗' + type(e).__name__
A_PAGES = ['JSON-LD(一个)', '__NEXT_DATA__', 'JSON 里含 <\\/script>(合法转义)', '数据在属性里(&quot; 实体)', '两个 JSON-LD(其中一个是 @graph)', 'JSON-LD 里有注释和末尾逗号(不是合法 JSON)', 'JSON 字符串里含 </script>(没有转义)']
B_PAGES = ['window.__STATE__ = {…};后面还有 JS', 'JS 对象字面量(单引号、无引号键、末尾逗号、undefined)']
print('== 一:A 组——数据在 type 为 json 的 <script> 里(或属性里):三种方法能不能取出并解析(✓ = 成功,括号里是取到的块数;✗+异常名 = 失败;空 = 没取到任何东西)')
AM = [('M1 正则取 <script> 再 json.loads', m_regex), ('M2 lxml 取 script 文本/属性 再 json.loads', m_lxml), ('M3 lxml 取 script + json5', m_lxml_json5)]
print(f'  {"页面类型":<48}' + ''.join(f'{n.split()[0]:>16}' for n, _ in AM)); print('  ' + ' / '.join(n for n, _ in AM))
for lab in A_PAGES: print(f'  {lab:<44}' + ''.join(f'{ok(f, PAGES[lab]):>16}' for _, f in AM))
print('== 二:B 组——数据在 JS 赋值语句 window.__STATE__ = … 里:四种方法')
BM = [('N1 正则 {.*?}; 再 json.loads', m_assign_regex), ('N2 从 { 起 raw_decode', m_assign_raw), ('N3 按花括号配对取出再 json5', m_assign_scan_json5), ('N4 同 N3,先把 undefined 换成 null', m_assign_scan_json5_undef)]
print(f'  {"页面类型":<48}' + ''.join(f'{n.split()[0]:>12}' for n, _ in BM)); print('  ' + ' / '.join(n for n, _ in BM))
for lab in B_PAGES: print(f'  {lab[:44]:<44}' + ''.join(f'{ok(f, PAGES[lab]):>12}' for _, f in BM))

print('== 三:几个值得细看的结果')
h = PAGES['window.__STATE__ = {…};后面还有 JS']
try: m_assign_regex(h)
except Exception as e: print(f'  非贪婪正则 {{.*?}}; 遇到字符串里的 "}};" :json.loads 报 {type(e).__name__}: {str(e)[:50]}(在 desc 字段里的 "}};" 处就被截断了)')
print(f'  raw_decode 从第一个 {{ 开始只读一个完整的 JSON 值,忽略后面的 JS:取到 {list(m_assign_raw(h)[0].keys())}')
h = PAGES['JS 对象字面量(单引号、无引号键、末尾逗号、undefined)']
try: m_assign_raw(h)
except Exception as e: print(f'  JS 对象字面量交给 json.loads/raw_decode:{type(e).__name__}: {str(e)[:50]}')
try: m_assign_scan_json5(h)
except Exception as e: print(f'  json5 直接解析含 undefined 的字面量:{type(e).__name__}: {str(e)[:50]}(json5 不认识 undefined)')
r = m_assign_scan_json5_undef(h)[0]; print(f'  先把 undefined 换成 null 再用 json5:{r}')
h = PAGES['JSON 字符串里含 </script>(没有转义)']
print(f'  字符串里含没转义的 </script>:HTML 解析器在第一个 </script> 就结束了脚本。lxml 取到的 script 文本是 {lxml.html.fromstring(h).xpath("//script/text()")[0]!r}')
h = PAGES['JSON 里含 <\\/script>(合法转义)']; print(f'  转义成 <\\/script> 的合法 JSON:正则取到 {m_regex(h)},lxml 取到 {m_lxml(h)}')
h = PAGES['数据在属性里(&quot; 实体)']; print(f'  属性里的 JSON:lxml 自动解码实体;正则直接取到的原始文本是 {re.search(r"data-product=\"(.{0,40})", h).group(1)!r}')
print(f'  整数精度:JSON 里的 {DATA["big"]} 在 Python 里是 {json.loads(J)["big"]}(精确);页面里的 JS 如果当 Number 处理,会变成 {float(DATA["big"]):.0f}')
print('== 四:第二个 JSON-LD 是 @graph 的情形:遍历时要展开')
doc = lxml.html.fromstring(PAGES['两个 JSON-LD(其中一个是 @graph)']); blocks = [json.loads(t) for t in doc.xpath('//script[@type="application/ld+json"]/text()')]
nodes = [n for b in blocks for n in (b['@graph'] if '@graph' in b else [b])]
print(f'  共 {len(blocks)} 个块,展开 @graph 之后有 {len(nodes)} 个实体:{[(n["@type"], n["name"]) for n in nodes]}')
purge()

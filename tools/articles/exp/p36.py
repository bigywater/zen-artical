import sys, os, json, subprocess, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import lxml.html
tee('p36')
d = pdir('p36')
B = 'http://a.test/dir/sub/page.html?x=1#top'
CASES = [
 ('同目录文件', B, 'x.html'), ('./ 开头', B, './x.html'), ('上一级 ../', B, '../x.html'), ('上上级 ../../', B, '../../x.html'),
 ('越过根目录 ../../../../', B, '../../../../x.html'), ('绝对路径 /', B, '/x.html'), ('协议相对 //', B, '//b.test/x.html'),
 ('只有查询串 ?', B, '?y=2'), ('只有 fragment #', B, '#sec'), ('空字符串', B, ''), ('另一个站点的绝对 URL', B, 'http://c.test/z'),
 ('子目录带结尾斜杠', B, 'child/'), ('base 目录没有结尾斜杠', 'http://a.test/dir/sub', 'x.html'), ('base 目录有结尾斜杠', 'http://a.test/dir/sub/', 'x.html'),
 ('base 只有主机', 'http://a.test', 'x.html'), ('base 路径带 . 段', 'http://a.test/a/./b/../c/', 'x'), ('带点段的相对链接', 'http://a.test/a/b/', './../c/./d'),
 ('javascript: 链接', B, 'javascript:void(0)'), ('mailto: 链接', B, 'mailto:a@b.test'), ('data: 链接', B, 'data:text/plain,hi'), ('tel: 链接', B, 'tel:+123'),
 ('前后有空格', B, '  x.html  '), ('内部有换行', B, 'x\n.html'), ('反斜杠', B, '..\\x.html'), ('反斜杠开头的绝对路径', B, '\\x.html'),
 ('无斜杠的 scheme(http:foo)', B, 'http:foo'), ('不同 scheme 的 scheme:foo', 'http://a.test/dir/', 'https:foo'), ('三个斜杠 http:///x', B, 'http:///x'),
 ('大写 scheme', B, 'HTTP://C.test/Z'), ('端口', B, 'http://a.test:80/x'), ('中文路径', B, '/路径/页面.html'), ('中文域名绝对链接', B, 'http://中文.test/x'),
 ('查询串里有空格', B, '/s?q=a b'), ('链接里多余的 ../ 在中段', B, '/a/../../b'), ('只有 ..', 'http://a.test/x/y/z', '..'), ('只有 .', 'http://a.test/x/y/z', '.'),
]
json.dump([[b, r] for _, b, r in CASES], open(d / 'cases.json', 'w'))
NODE = "const c=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));console.log(JSON.stringify(c.map(([b,r])=>{try{return new URL(r,b).href}catch(e){return 'ERR:'+e.constructor.name}})))"
env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
nodes = json.loads(subprocess.run(['node', '-e', NODE, str(d / 'cases.json')], capture_output=True, text=True, env=env).stdout)
def pj(b, r):
    try: return up.urljoin(b, r)
    except Exception as e: return 'ERR:' + type(e).__name__
print(f'== 一:{len(CASES)} 个相对链接用例:Python urllib.parse.urljoin 与 Node 的 WHATWG URL(浏览器采用的标准)的结果对比(base 默认是 {B})')
same = 0; diffs = []
for (lab, b, r), nd in zip(CASES, nodes):
    pv = pj(b, r)
    if pv == nd: same += 1
    else: diffs.append((lab, b, r, pv, nd))
print(f'  结果相同的 {same} 个,不同的 {len(diffs)} 个')
print('== 二:不同的那几个(Python urljoin → Node WHATWG)')
for lab, b, r, pv, nd in diffs:
    print(f'  {lab}:相对链接 {r!r}' + (f'(base {b})' if b != B else ''))
    print(f'        Python:{pv}')
    print(f'        Node  :{nd}')

print('== 三:不同 scheme 的链接被 urljoin 原样保留,爬虫要自己过滤')
for r in ('javascript:void(0)', 'mailto:a@b.test', 'data:text/plain,hi', 'tel:+123', 'ftp://f.test/x', 'file:///etc/passwd'):
    j = up.urljoin(B, r); print(f'  urljoin(base, {r!r}) = {j!r};scheme = {up.urlsplit(j).scheme!r}')

print('== 四:页面里的 <base href> 与重定向后的最终 URL')
HTML_PAGE = lambda base: ('<html><head>' + (f'<base href="{base}">' if base else '') + '</head><body><a href="x.html">a</a><a href="/root.html">b</a><a href="../up.html">c</a></body></html>')
def hrefs(html, url, resolve=True):
    doc = lxml.html.fromstring(html); doc.make_links_absolute(url, resolve_base_href=resolve); return [a.get('href') for a in doc.iter('a')]
print(f'  页面 URL = http://a.test/dir/page.html')
print(f'  没有 <base>:{hrefs(HTML_PAGE(None), "http://a.test/dir/page.html")}')
print(f'  <base href="http://cdn.test/assets/">:{hrefs(HTML_PAGE("http://cdn.test/assets/"), "http://a.test/dir/page.html")}')
print(f'  同样的页面,make_links_absolute(url, resolve_base_href=False)(文档字符串说"忽略 <base>"):{hrefs(HTML_PAGE("http://cdn.test/assets/"), "http://a.test/dir/page.html", resolve=False)}')
import inspect
print('  → 实测 <base> 仍然生效。lxml 6.1.1 源码里的原因:')
for l in inspect.getsource(lxml.html.HtmlMixin.make_links_absolute).splitlines():
    if 'self.rewrite_links(link_repl)' in l or 'if resolve_base_href:' in l: print('      make_links_absolute:' + l.strip())
for l in inspect.getsource(lxml.html.HtmlMixin.rewrite_links).splitlines():
    if l.strip().startswith('def rewrite_links') or 'resolve_base_href=True' in l or 'elif resolve_base_href' in l or 'self.resolve_base_href()' in l: print('      rewrite_links:' + l.strip())
print(f'  <base href="/other/"> (相对的 base):{hrefs(HTML_PAGE("/other/"), "http://a.test/dir/page.html")}')
two = '<html><head><base href="http://one.test/"><base href="http://two.test/"></head><body><a href="x">a</a></body></html>'
print(f'  两个 <base>:{hrefs(two, "http://a.test/p")}')
with Srv(lambda h: (h.reply(302, b'', headers={'Location': '/new/dir/page.html'}) if h.path == '/old' else h.reply(200, b'<html><body><a href="next.html">n</a></body></html>'))) as sv:
    import requests
    r = requests.get(sv.url('/old'))
    doc = lxml.html.fromstring(r.content)
    a = up.urljoin(sv.url('/old'), 'next.html'); b2 = up.urljoin(r.url, 'next.html')
    print(f'  请求 /old 被重定向到 /new/dir/page.html;相对链接 next.html:用请求时的 URL 当 base → {a.replace(sv.url(""), "<站点>")};用 r.url(最终 URL)当 base → {b2.replace(sv.url(""), "<站点>")}')
purge()

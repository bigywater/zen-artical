import sys, os, re, subprocess, urllib.parse as up, random, collections, importlib.metadata as md; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p35')
d = pdir('p35')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--target', str(d / 'site'), 'w3lib'], capture_output=True, env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()})
sys.path.insert(0, str(d / 'site'))
from w3lib.url import canonicalize_url
import yarl

UNRESERVED = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~')
def _pct(s):
    def f(m):
        c = chr(int(m.group(1), 16)); return c if c in UNRESERVED else '%' + m.group(1).upper()
    return re.sub(r'%([0-9A-Fa-f]{2})', f, s)
def remove_dots(path):
    out = []
    for seg in path.split('/'):
        if seg == '..':
            if len(out) > 1: out.pop()
        elif seg != '.': out.append(seg)
    if path.endswith(('/.', '/..')): out.append('')
    r = '/'.join(out); return r if r.startswith('/') else '/' + r
def norm_safe(url):
    """只做语法上不会改变含义的规范化(RFC 3986 的思路):scheme/主机小写、去默认端口、去点段、百分号编码统一、去 fragment、空路径变 /、主机转 punycode、去主机末尾的点"""
    p = up.urlsplit(url.strip())
    host = (p.hostname or '').rstrip('.').encode('idna').decode('ascii').lower() if p.hostname else ''
    port = p.port
    if port and ((p.scheme.lower() == 'http' and port == 80) or (p.scheme.lower() == 'https' and port == 443)): port = None
    netloc = (f'{p.username}:{p.password}@' if p.password else (f'{p.username}@' if p.username else '')) + host + (f':{port}' if port else '')
    path = remove_dots(_pct(p.path) or '/')
    return up.urlunsplit((p.scheme.lower(), netloc, path, _pct(p.query), ''))
TRACK = re.compile(r'^(utm_|fbclid$|gclid$|sessionid$|sid$)', re.I)
def norm_loose(url):
    """在 norm_safe 之上再做"语义"规范化:合并重复斜杠、丢空查询、去追踪参数、参数排序(这些对具体网站不一定成立)"""
    u = up.urlsplit(norm_safe(url))
    q = sorted((k, v) for k, v in up.parse_qsl(u.query, keep_blank_values=True) if not TRACK.match(k))
    path = re.sub(r'/{2,}', '/', u.path)
    return up.urlunsplit((u.scheme, u.netloc, path, up.urlencode(q), ''))

PAIRS = [
 ('scheme 与主机大小写', 'HTTP://Example.COM/a', 'http://example.com/a'),
 ('路径大小写(路径通常区分)', 'http://a.test/Abc', 'http://a.test/abc'),
 ('默认端口 :80', 'http://a.test:80/x', 'http://a.test/x'),
 ('默认端口 :443', 'https://a.test:443/x', 'https://a.test/x'),
 ('非默认端口 :8080', 'http://a.test:8080/x', 'http://a.test/x'),
 ('http 与 https', 'http://a.test/x', 'https://a.test/x'),
 ('fragment', 'http://a.test/x#top', 'http://a.test/x'),
 ('空路径与 /', 'http://a.test', 'http://a.test/'),
 ('结尾斜杠', 'http://a.test/x/', 'http://a.test/x'),
 ('点段 /./ 与 /../', 'http://a.test/a/./b/../c', 'http://a.test/a/c'),
 ('重复斜杠', 'http://a.test/a//b', 'http://a.test/a/b'),
 ('百分号编码大小写 %2f / %2F', 'http://a.test/a%2fb', 'http://a.test/a%2Fb'),
 ('不必要的编码 %7E 与 ~', 'http://a.test/%7Euser', 'http://a.test/~user'),
 ('参数顺序', 'http://a.test/s?b=2&a=1', 'http://a.test/s?a=1&b=2'),
 ('空的 ? ', 'http://a.test/s?', 'http://a.test/s'),
 ('utm 追踪参数', 'http://a.test/s?id=1&utm_source=x', 'http://a.test/s?id=1'),
 ('主机末尾的点', 'http://a.test./x', 'http://a.test/x'),
 ('中文域名 与 punycode', 'http://中文.test/x', 'http://xn--fiq228c.test/x'),
 ('查询串里空格 + 与 %20', 'http://a.test/s?q=a+b', 'http://a.test/s?q=a%20b'),
 ('用户信息', 'http://u:p@a.test/x', 'http://a.test/x'),
]
def wl(u):
    try: return canonicalize_url(u)
    except Exception as e: return 'ERR:' + type(e).__name__
NORM = [('原样字符串', lambda u: u), ('urlsplit→geturl', lambda u: up.urlsplit(u).geturl()), ('yarl.URL', lambda u: str(yarl.URL(u))), (f'w3lib {md.version("w3lib")}', wl), ('自写:只做语法规范化', norm_safe), ('自写:再加语义规范化', norm_loose)]
print('== 一:20 组"可能是同一个页面"的 URL,各种规范化之后是否变成同一个字符串(✓ = 变成相同了)')
print(f'  {"用例":<26}' + ''.join(f'{n:>22}' for n, _ in NORM))
tot = collections.Counter()
for lab, a, b in PAIRS:
    row = []
    for n, f in NORM:
        try: same = f(a) == f(b)
        except Exception: same = False
        row.append('✓' if same else '·'); tot[n] += same
    print(f'  {lab:<22}' + ''.join(f'{r:>22}' for r in row))
print(f'  {"合并成功的组数":<20}' + ''.join(f'{tot[n]:>22}' for n, _ in NORM))

print('== 二:几个值得单独看的结果(规范化之后的字符串)')
for u in ('HTTP://Example.COM:80/a/./b/../c?b=2&a=1#frag', 'http://a.test/a//b/%7Euser?utm_source=x&id=1', 'http://中文.test/x'):
    print(f'  输入 {u}')
    for n, f in NORM[2:]:
        try: print(f'      {n:<18}→ {f(u)}')
        except Exception as e: print(f'      {n:<18}→ 抛 {type(e).__name__}')

print('== 三:对去重数量的影响:1000 个不同页面,每个页面以 8 种写法各出现若干次(链接来自不同页面,写法不同),共 8000 个 URL;规范化之后还剩多少个"不同的 URL"')
rng = random.Random(5)
def variants(i):
    base = f'/item/{i}'; q = f'id={i}&cat={i % 7}'
    return [f'http://shop.test{base}?{q}', f'http://SHOP.test:80{base}?{q}', f'http://shop.test{base}?cat={i % 7}&id={i}', f'http://shop.test{base}?{q}#reviews',
            f'http://shop.test{base}?{q}&utm_source=mail', f'http://shop.test/./item/../item/{i}?{q}', f'http://shop.test{base}?{q}&sessionid={rng.randint(1000, 9999)}', f'http://shop.test//item/{i}?{q}']
urls = [v for i in range(1000) for v in variants(i)]
for n, f in NORM:
    try: k = len({f(u) for u in urls})
    except Exception as e: k = f'抛 {type(e).__name__}'
    print(f'  {n:<22}:{len(urls)} 个 URL → {k} 个不同的')
purge()

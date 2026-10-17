import sys, os, subprocess, urllib.robotparser as rp, urllib.error; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p25')
d = pdir('p25')
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--target', str(d / 'site'), 'protego'], capture_output=True, text=True, env={k: v for k, v in os.environ.items() if 'proxy' not in k.lower()})
sys.path.insert(0, str(d / 'site')); import protego, importlib.metadata as md
PV = md.version('protego')
H = 'http://example.test'

def std(text, url, ua):
    p = rp.RobotFileParser(); p.parse(text.strip().splitlines()); return p.can_fetch(ua, url)
def pro(text, url, ua):
    return protego.Protego.parse(text).can_fetch(url, ua)

CASES = [
 ('最长匹配:Allow 更长压过 Disallow', 'User-agent: *\nDisallow: /private/\nAllow: /private/public.html', '/private/public.html', 'MyBot'),
 ('最长匹配:Disallow 写在 Allow 之后也一样', 'User-agent: *\nAllow: /private/public.html\nDisallow: /private/', '/private/public.html', 'MyBot'),
 ('长度相同的 Allow 与 Disallow', 'User-agent: *\nDisallow: /a\nAllow: /a', '/a', 'MyBot'),
 ('长度相同,Allow 写在前面', 'User-agent: *\nAllow: /a\nDisallow: /a', '/a', 'MyBot'),
 ('前缀匹配', 'User-agent: *\nDisallow: /private', '/privateer/x', 'MyBot'),
 ('路径区分大小写', 'User-agent: *\nDisallow: /Private', '/private/x', 'MyBot'),
 ('通配符 * 在中间', 'User-agent: *\nDisallow: /a/*/c', '/a/b/c/d', 'MyBot'),
 ('结尾 $ 精确匹配(.pdf 结尾)', 'User-agent: *\nDisallow: /*.pdf$', '/docs/a.pdf', 'MyBot'),
 ('结尾 $:路径后面还有查询串', 'User-agent: *\nDisallow: /*.pdf$', '/docs/a.pdf?download=1', 'MyBot'),
 ('空的 Disallow = 全部允许', 'User-agent: *\nDisallow:', '/anything', 'MyBot'),
 ('Disallow: / 禁止整站', 'User-agent: *\nDisallow: /', '/', 'MyBot'),
 ('Disallow: / 之外 Allow: /ok', 'User-agent: *\nDisallow: /\nAllow: /ok', '/ok/page', 'MyBot'),
 ('查询串匹配 /search?q=', 'User-agent: *\nDisallow: /search?q=', '/search?q=python', 'MyBot'),
 ('百分号编码:规则写 ~,请求写 %7E', 'User-agent: *\nDisallow: /~user', '/%7Euser/x', 'MyBot'),
 ('百分号编码:规则写 %7E,请求写 ~', 'User-agent: *\nDisallow: /%7Euser', '/~user/x', 'MyBot'),
 ('UA 精确组 vs * 组', 'User-agent: *\nDisallow: /\n\nUser-agent: MyBot\nAllow: /', '/x', 'MyBot'),
 ('UA 名字带版本号 MyBot/1.0', 'User-agent: MyBot\nDisallow: /x', '/x', 'MyBot/1.0'),
 ('组名是我的 UA 名字的子串("bot" 对 "MyBot")', 'User-agent: bot\nDisallow: /x', '/x', 'MyBot'),
 ('组名比我的 UA 名字长("MyBotPro" 对 "MyBot")', 'User-agent: MyBotPro\nDisallow: /x', '/x', 'MyBot'),
 ('UA 名字大小写', 'User-agent: MYBOT\nDisallow: /x', '/x', 'mybot'),
 ('同一个 UA 出现在两个组里(是否合并)', 'User-agent: MyBot\nDisallow: /a\n\nUser-agent: MyBot\nDisallow: /b', '/b', 'MyBot'),
 ('多个 UA 共用一组', 'User-agent: AlphaBot\nUser-agent: MyBot\nDisallow: /x', '/x', 'MyBot'),
 ('规则之间的空行与注释', 'User-agent: *\n# 注释\n\nDisallow: /x\n', '/x', 'MyBot'),
 ('字段名大小写与空格', 'USER-AGENT : *\ndisallow : /x', '/x', 'MyBot'),
 ('没有 User-agent 行的规则', 'Disallow: /x', '/x', 'MyBot'),
 ('robots.txt 本身', 'User-agent: *\nDisallow: /', '/robots.txt', 'MyBot'),
]
print(f'== 一:同一份 robots.txt、同一个 URL,Python 3.14.8 标准库 urllib.robotparser 与 protego {PV} 的判断(True = 允许抓取)')
print(f'  {"用例":<40}{"标准库":>8}{"protego":>9}  是否一致')
diff = []
for name, text, path, ua in CASES:
    a = std(text, H + path, ua); b = pro(text, H + path, ua)
    flag = '' if a == b else '  ← 不一致'
    if a != b: diff.append(name)
    print(f'  {name:<40}{str(a):>8}{str(b):>9}{flag}')
print(f'  共 {len(CASES)} 个用例,两者判断不同的有 {len(diff)} 个:{diff}')

print('== 二:Crawl-delay、Request-rate、Sitemap 的读取')
T = 'User-agent: *\nCrawl-delay: 3\nRequest-rate: 2/10\nDisallow: /x\n\nUser-agent: MyBot\nCrawl-delay: 7\n\nSitemap: http://example.test/sitemap1.xml\nSitemap: http://example.test/sitemap2.xml'
p = rp.RobotFileParser(); p.parse(T.splitlines()); q = protego.Protego.parse(T)
print(f'  标准库:crawl_delay("MyBot") = {p.crawl_delay("MyBot")},crawl_delay("Other") = {p.crawl_delay("Other")},request_rate("Other") = {p.request_rate("Other")},site_maps() = {p.site_maps()}')
print(f'  protego:crawl_delay("MyBot") = {q.crawl_delay("MyBot")},crawl_delay("Other") = {q.crawl_delay("Other")},request_rate("Other") = {q.request_rate("Other")},sitemaps = {list(q.sitemaps)}')
print(f'  Crawl-delay: 1.5 这种小数:标准库 = {(lambda z: (z.parse(["User-agent: *", "Crawl-delay: 1.5"]), z.crawl_delay("x"))[1])(rp.RobotFileParser())},protego = {protego.Protego.parse("User-agent: *\\nCrawl-delay: 1.5").crawl_delay("x")}')

print('== 三:robots.txt 本身的 HTTP 状态不同,标准库 read() 之后 can_fetch 的结果(服务器是本机,robots.txt 内容为 Disallow: /x)')
ROB = b'User-agent: *\nDisallow: /x\n'
def server(h):
    p = h.path.split('?')[0]
    if p == '/robots.txt':
        c = int(h.headers.get('X-Code', '200'))
    code = {'200': 200, '404': 404, '410': 410, '401': 401, '403': 403, '429': 429, '500': 500, '503': 503, '301': 301}.get(h.path.split('?c=')[-1], 200)
    if code == 200: h.reply(200, ROB, headers={'Content-Type': 'text/plain'})
    elif code == 301: h.reply(301, b'', headers={'Location': '/real.txt'})
    else: h.reply(code, b'')
with Srv(lambda h: (server(h) if 'real' not in h.path else h.reply(200, ROB))) as sv:
    for code in ('200', '404', '410', '401', '403', '429', '500', '503', '301'):
        p = rp.RobotFileParser(sv.url('/robots.txt?c=' + code)); p.read()
        r1, r2 = p.can_fetch('MyBot', H + '/x'), p.can_fetch('MyBot', H + '/y')
        print(f'  robots.txt 返回 {code}:/x 允许={r1},/y 允许={r2};disallow_all={p.disallow_all},allow_all={p.allow_all}')
    p = rp.RobotFileParser(); print(f'  从没读过 robots.txt(没调用 read/parse):can_fetch = {p.can_fetch("MyBot", H + "/y")}')
purge()

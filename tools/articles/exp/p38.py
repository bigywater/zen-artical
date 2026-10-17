import sys, os, hashlib, urllib.parse as up, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
tee('p38')

def server(h):
    p = up.urlsplit(h.path); hd = {k.lower(): v for k, v in h.hdrs}
    lang = hd.get('accept-language', 'en'); ck = hd.get('cookie', '')
    body = h.body.decode()
    if p.path.startswith('/product/'): out = f'product {p.path} lang={lang}'
    elif p.path == '/search': out = f'search method={h.command} q={up.parse_qs(body or p.query).get("q", [""])[0]}'
    elif p.path.startswith('/account/'): out = f'account {p.path} tier={"pro" if "tier=pro" in ck else "free"}'
    else: out = f'static {p.path}'
    h.reply(200, out.encode())

# 请求列表(模拟爬虫的待抓队列)
R = []
for i in range(40):
    for lang in ('en', 'zh'): R.append(dict(m='GET', path=f'/product/{i}', headers={'Accept-Language': lang}))
for j in range(20):
    for _ in range(3): R.append(dict(m='POST', path='/search', data=f'q=word{j}', headers={}))
for i in range(10):
    for tier in ('free', 'pro'): R.append(dict(m='GET', path=f'/account/{i}', headers={'Cookie': f'tier={tier}'}))
for _ in range(10): R.append(dict(m='GET', path='/about', headers={}))
for j in range(10): R.append(dict(m='GET', path='/search', params={'q': f'word{j}'}, headers={}))     # 同一个 /search,GET 方式

def canon(path, params): return path + ('?' + up.urlencode(sorted(params.items())) if params else '')
def fp(design, r):
    url = canon(r['path'], r.get('params'))
    if design == '只哈希 URL': return url
    if design == '方法 + URL': return (r['m'], url)
    if design == '方法 + URL + 请求体': return (r['m'], url, hashlib.sha1(r.get('data', '').encode()).hexdigest())
    if design == '方法 + URL + 请求体 + 关键请求头': return (r['m'], url, hashlib.sha1(r.get('data', '').encode()).hexdigest(), r['headers'].get('Accept-Language'), r['headers'].get('Cookie'))

with Srv(server) as sv:
    def fetch(r):
        return requests.request(r['m'], sv.url(canon(r['path'], r.get('params'))), data=r.get('data'), headers=r['headers']).text
    truth = [fetch(r) for r in R]
    T = len(set(truth))
    print('== 一:标准答案:把队列里的请求全部发一遍,数一数服务器返回了多少种不同的内容')
    print(f'  请求队列共 {len(R)} 个:40 个商品页 × 2 种语言 = 80;POST /search 20 种请求体 × 重复 3 次 = 60;/account/ 10 个 URL × 2 种 Cookie = 20;/about 重复 10 次;GET /search?q= 10 个 = 10')
    print(f'  全部发一遍之后,服务器返回了 {T} 种不同的内容(真正重复的请求有 {len(R) - T} 个)')
    print('== 二:四种指纹方案,按指纹去重(同一个指纹只发第一个请求)之后:发出多少个请求、拿到多少种不同的内容、漏掉多少种、多发了多少个重复的')
    print(f'  {"指纹方案":<36}{"发出的请求":>10}{"拿到的不同内容":>14}{"漏掉的":>8}{"多发的重复请求":>14}')
    res = {}
    for design in ('只哈希 URL', '方法 + URL', '方法 + URL + 请求体', '方法 + URL + 请求体 + 关键请求头'):
        seen = set(); kept = []
        for r, t in zip(R, truth):
            k = fp(design, r)
            if k in seen: continue
            seen.add(k); kept.append(t)
        got = len(set(kept)); res[design] = (len(kept), got)
        print(f'  {design:<30}{len(kept):>10}{got:>14}{T - got:>8}{len(kept) - got:>14}')
    print('== 三:漏掉的是哪几类(只哈希 URL 时)')
    seen = set(); lost = collections.Counter()
    for r, t in zip(R, truth):
        k = fp('只哈希 URL', r)
        if k in seen: lost[r['path'].split('/')[1] + (' POST' if r['m'] == 'POST' else '')] += (t not in {tt for rr, tt in zip(R, truth) if fp('只哈希 URL', rr) == k and False})
        seen.add(k)
    skipped_unique = collections.Counter()
    first_content = {}
    for r, t in zip(R, truth):
        k = fp('只哈希 URL', r)
        if k not in first_content: first_content[k] = {t}
        elif t not in first_content[k]:
            first_content[k].add(t); skipped_unique[r['path'].split('/')[1] + (' POST' if r['m'] == 'POST' else '') + (' 带 Accept-Language' if 'Accept-Language' in r['headers'] else '') + (' 带 Cookie' if 'Cookie' in r['headers'] else '')] += 1
    for k, v in sorted(skipped_unique.items()): print(f'  {k}:被当成重复丢掉、实际内容不同的请求 {v} 个')
    print('== 四:指纹里的请求体用什么哈希、要不要规范化:同一个 POST 的请求体换了参数顺序')
    a = 'q=word1&page=2'; b = 'page=2&q=word1'
    print(f'  请求体 {a!r} 与 {b!r}:服务器对两者返回的内容相同吗?{requests.post(sv.url("/search"), data=a).text == requests.post(sv.url("/search"), data=b).text}(对本服务器相同);按原始字节哈希的指纹相同吗?{hashlib.sha1(a.encode()).hexdigest() == hashlib.sha1(b.encode()).hexdigest()};按解析后排序再哈希的指纹相同吗?{hashlib.sha1(up.urlencode(sorted(up.parse_qsl(a))).encode()).hexdigest() == hashlib.sha1(up.urlencode(sorted(up.parse_qsl(b))).encode()).hexdigest()}')
purge()

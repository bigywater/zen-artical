import sys, os, json, re, urllib.parse as up; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
import requests, lxml.html
tee('p53')
d = pdir('p53')
ITEMS = [dict(id=i, name=f'Item {i}', price_cents=1000 + i * 37, internal_sku=f'SKU-{i:05d}') for i in range(1, 26)]
APP_JS = """
const list = document.getElementById('list');
async function load(page) {
  const r = await fetch('/api/products?page=' + page + '&limit=10', {headers: {'X-Requested-With': 'XMLHttpRequest'}});
  const j = await r.json();
  for (const it of j.items) { const li = document.createElement('li'); li.textContent = it.name + ' - ' + (it.price_cents / 100).toFixed(2); list.appendChild(li); }
  return j.next;
}
(async () => {
  await fetch('/api/config').then(r => r.json());
  let p = 1;
  while (p) { p = await load(p); }
  navigator.sendBeacon('/api/track', JSON.stringify({event: 'loaded'}));
  document.title = 'done';
})();
"""
def srv(h):
    u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query)); hd = {k.lower(): v for k, v in h.hdrs}
    if u.path == '/': return h.reply(200, b'<!doctype html><html><head><title>shop</title></head><body><h1>Shop</h1><ul id="list"></ul><script src="/app.js"></script></body></html>', headers={'Content-Type': 'text/html', 'Set-Cookie': 'sid=abc123; Path=/'})
    if u.path == '/app.js': return h.reply(200, APP_JS.encode(), headers={'Content-Type': 'application/javascript'})
    if u.path == '/api/config': return h.reply(200, b'{"theme":"light"}', headers={'Content-Type': 'application/json'})
    if u.path == '/api/track': return h.reply(204, b'')
    if u.path == '/api/products':
        if 'sid=abc123' not in hd.get('cookie', ''): return h.reply(401, b'{"error":"no session"}', headers={'Content-Type': 'application/json'})
        if hd.get('x-requested-with') != 'XMLHttpRequest': return h.reply(403, b'{"error":"xhr only"}', headers={'Content-Type': 'application/json'})
        page = int(q.get('page', 1)); limit = int(q.get('limit', 10)); chunk = ITEMS[(page - 1) * limit:page * limit]
        return h.reply(200, json.dumps(dict(items=chunk, next=page + 1 if page * limit < len(ITEMS) else None)).encode(), headers={'Content-Type': 'application/json'})
    h.reply(404, b'')

with Srv(srv) as sv:
    B = sv.url('')
    print('== 一:只用 requests 取页面(不执行 JavaScript):HTML 里有商品吗?')
    r = requests.get(B + '/'); doc = lxml.html.fromstring(r.content)
    print(f'  状态 {r.status_code},HTML 大小 {len(r.content)} 字节;<li> 个数 {len(doc.xpath("//li"))};<script src> = {doc.xpath("//script/@src")};ul#list 里的内容 {doc.xpath("//ul[@id=\'list\']/*")} ——数据不在 HTML 里,要等 JS 去取')
    print('== 二:用 Chrome(CDP 的 Network 事件)记录页面加载过程中发出的所有请求')
    with Chrome(free_port(9970), d) as ch:
        pg = ch.new_page(); pg.send('Network.enable'); t0 = time.perf_counter()
        pg.goto(B + '/', wait='Page.loadEventFired')
        for _ in range(100):
            if pg.eval('document.title') == 'done': break
            time.sleep(0.05)
        browser_ms = ms(t0)
        reqs = {}; bodies = {}
        # 事件已经缓存在 pg.events 里
        for e in pg.events:
            m, p = e['method'], e['params']
            if m == 'Network.requestWillBeSent': reqs[p['requestId']] = dict(method=p['request']['method'], url=p['request']['url'].replace(B, ''), headers=p['request']['headers'], type=p.get('type'), initiator=p['initiator']['type'])
            elif m == 'Network.responseReceived' and p['requestId'] in reqs: reqs[p['requestId']].update(status=p['response']['status'], mime=p['response']['mimeType'], size=p['response'].get('encodedDataLength'))
        for rid, rq in reqs.items():
            if 'products' in rq['url']:
                try: bodies[rq['url']] = json.loads(pg.send('Network.getResponseBody', requestId=rid)['body'])
                except Exception as ex: bodies[rq['url']] = f'(取不到:{type(ex).__name__})'
        dom_items = pg.eval('Array.from(document.querySelectorAll("#list li")).map(l => l.textContent)')
        print(f'  从打开页面到 JS 渲染完成:{browser_ms:.0f} ms;DOM 里渲染出 {len(dom_items)} 条,第一条 {dom_items[0]!r}')
        print(f'  {"方法":<6}{"路径":<34}{"状态":>5}{"类型":>10}{"发起者":>10}  请求头里值得注意的')
        for rq in reqs.values():
            ih = {k: v for k, v in rq['headers'].items() if k.lower() in ('x-requested-with', 'cookie', 'accept', 'content-type')}
            print(f'  {rq["method"]:<6}{rq["url"]:<34}{rq.get("status", "?"):>5}{rq.get("type", ""):>10}{rq["initiator"]:>10}  {ih if rq["url"].startswith("/api") else ""}')
        pg.close()
    print('== 三:直接用 requests 重放 /api/products?page=1&limit=10,逐个去掉请求头,看哪些是必须的')
    def call(headers=None, cookies=None):
        r = requests.get(B + '/api/products?page=1&limit=10', headers=headers or {}, cookies=cookies or {}); return r.status_code
    full_h = {'X-Requested-With': 'XMLHttpRequest'}; full_c = {'sid': 'abc123'}
    print(f'  什么都不带:{call()};只带 Cookie:{call(cookies=full_c)};只带 X-Requested-With:{call(full_h)};两者都带:{call(full_h, full_c)}')
    print('  → 缺 Cookie 返回 401,缺 X-Requested-With 返回 403;这两个都是浏览器自动带上的,直接请求时要自己补(Cookie 的值来自第一次访问 / 时服务器设置的 Set-Cookie)')
    s = requests.Session(); s.get(B + '/'); s.headers['X-Requested-With'] = 'XMLHttpRequest'
    print('== 四:用 Session(先访问首页拿 cookie)加必需的头,直接翻页取全部数据,与浏览器 DOM 里的结果对比')
    all_items = []; page = 1; t0 = time.perf_counter(); calls = 0
    while page:
        j = s.get(B + f'/api/products?page={page}&limit=10').json(); calls += 1; all_items += j['items']; page = j['next']
    api_ms = ms(t0)
    print(f'  {calls} 次请求取到 {len(all_items)} 条,{api_ms:.0f} ms(浏览器从打开页面到渲染完成要 {browser_ms:.0f} ms,这里 Chrome 已经启动好,时间包括加载页面、运行 JS 和同样的 3 次接口请求;两者都在本机回环上,绝对值只供比较)')
    dom_names = [x.split(' - ')[0] for x in dom_items]; api_names = [x['name'] for x in all_items]
    print(f'  条数一致:{len(dom_items) == len(all_items)};名称一致:{dom_names == api_names};API 返回的字段:{list(all_items[0].keys())}')
    print(f'  DOM 里只显示了 名称 和 价格(元);API 里还有页面没显示的字段:internal_sku={all_items[0]["internal_sku"]!r},价格是分 price_cents={all_items[0]["price_cents"]}')
purge()

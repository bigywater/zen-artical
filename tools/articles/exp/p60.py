import sys, os, json, base64, gzip as _gz, urllib.parse as up, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
tee('p60')
d = pdir('p60')
BIG = json.dumps([{'id': i, 'name': f'item-{i}', 'desc': 'x' * 40} for i in range(3000)]).encode()   # 约 200 KB 的 JSON,压缩后很小
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
def srv(h):
    u = up.urlsplit(h.path); q = dict(up.parse_qsl(u.query)); p = u.path
    if p == '/': return h.reply(200, b'<!doctype html><html><body><img src="/a.png"><script src="/app.js"></script></body></html>', headers={'Content-Type': 'text/html'})
    if p == '/app.js': return h.reply(200, b"fetch('/api/data').then(r => r.json()).then(j => { window.n = j.length; });", headers={'Content-Type': 'application/javascript'})
    if p == '/api/data':
        z = _gz.compress(BIG); return h.reply(200, z, headers={'Content-Type': 'application/json', 'Content-Encoding': 'gzip'})
    if p == '/a.png': return h.reply(200, PNG, headers={'Content-Type': 'image/png'})
    if p == '/redir': return h.reply(302, b'', headers={'Location': '/api/data'})
    if p == '/slow':          # 先发头和一半内容,停 0.6 秒,再发剩下的(分块)
        h.send_response(200); h.send_header('Content-Type', 'text/plain'); h.send_header('Transfer-Encoding', 'chunked'); h.end_headers()
        for part in (b'A' * 1000, b'B' * 1000):
            h.wfile.write(b'%x\r\n' % len(part) + part + b'\r\n'); h.wfile.flush(); time.sleep(0.6)
        h.wfile.write(b'0\r\n\r\n'); h.close_connection = True; return
    if p == '/blob':   # 指定大小的不可压缩内容
        n = int(q['mb']) * 1024 * 1024; return h.reply(200, os.urandom(n), headers={'Content-Type': 'application/octet-stream'})
    if p == '/ad': return h.reply(200, PNG, headers={'Content-Type': 'image/png'})
    h.reply(404, b'')

def evs(pg, name): return [e['params'] for e in pg.events if e['method'] == name]
def body(pg, rid):
    try: r = pg.send('Network.getResponseBody', requestId=rid); return ('ok', len(r['body']), r['base64Encoded'])
    except RuntimeError as e: return ('err', str(e)[:90], None)

with Srv(srv) as sv, Chrome(free_port(9970), d) as ch:
    B = sv.url('')
    print('== 一:Network 事件里一个请求的生命周期,以及 getResponseBody 取到什么(页面:一个 img + 一个 script,script 里 fetch 一个 gzip 压缩的 JSON)')
    pg = ch.new_page(); pg.send('Network.enable'); pg.goto(B + '/'); pg.drain(0.8)
    reqs = {e['requestId']: e for e in evs(pg, 'Network.requestWillBeSent')}; resp = {e['requestId']: e for e in evs(pg, 'Network.responseReceived')}; fin = {e['requestId']: e for e in evs(pg, 'Network.loadingFinished')}
    print(f'  事件个数:requestWillBeSent {len(reqs)}、responseReceived {len(resp)}、loadingFinished {len(fin)}、dataReceived {len(evs(pg, "Network.dataReceived"))}')
    for rid, r in resp.items():
        u = r['response']['url'].replace(B, ''); b = body(pg, rid)
        print(f'  {u:10s} type={r["type"]:9s} 状态 {r["response"]["status"]} mimeType={r["response"]["mimeType"]:24s} Content-Length(响应头)={r["response"]["headers"].get("Content-Length")} encodedDataLength={fin[rid]["encodedDataLength"]}  getResponseBody:{b[0]} 长度={b[1]} base64Encoded={b[2]}')
    print('== 二:压缩的响应:getResponseBody 给的是解压前还是解压后')
    rid = next(k for k, r in resp.items() if r['response']['url'].endswith('/api/data'))
    jb = json.loads(pg.send('Network.getResponseBody', requestId=rid)['body'])
    print(f'  /api/data 网络上传输的字节数(loadingFinished 的 encodedDataLength)是 {fin[rid]["encodedDataLength"]},getResponseBody 给出的是解压之后的文本 {len(pg.send("Network.getResponseBody", requestId=rid)["body"])} 字符、解析成 {len(jb)} 个对象;服务器实际发送的 gzip 字节数 {len(_gz.compress(BIG))};页面 JS 里 window.n = {pg.eval("window.n")}')
    print('== 三:什么时候可以取响应体(/slow:头先到,正文分两块、中间停 0.6 秒)')
    pg2 = ch.new_page(); pg2.send('Network.enable'); pg2.goto(B + '/'); pg2.drain(0.5); pg2.events.clear(); pg2.eval("fetch('/slow').then(r => r.text()).then(t => { window.slow = t.length; })")
    rid = None
    while rid is None:
        e = pg2.wait_event('Network.responseReceived', clear=True, timeout=5)
        if e['params']['response']['url'].endswith('/slow'): rid = e['params']['requestId']
    t0 = time.time(); print(f'  responseReceived 到达时(正文 2000 字节还没发完)取:{body(pg2, rid)}')
    while rid not in [x['requestId'] for x in evs(pg2, 'Network.loadingFinished')] and time.time() - t0 < 5: pg2.drain(0.05)
    print(f'  loadingFinished 到达后取:{body(pg2, rid)}(距 responseReceived {time.time() - t0:.2f} 秒;页面 JS 里收到的正文长度 {pg2.eval("window.slow")})')
    print('== 四:重定向的事件;页面跳走之后还能不能取')
    pg.goto(B + '/redir'); pg.drain(0.4)
    r3 = evs(pg, 'Network.requestWillBeSent'); redir = [x for x in r3 if x.get('redirectResponse')]
    print(f'  访问 /redir:requestWillBeSent 里带 redirectResponse 的有 {len(redir)} 个,状态 {redir[0]["redirectResponse"]["status"] if redir else None},Location={redir[0]["redirectResponse"]["headers"].get("Location") if redir else None}')
    print(f'  跳转之后:此前 /api/data 那个 requestId 再取 getResponseBody:{body(pg, rid_api) if (rid_api := next(k for k, r in resp.items() if r["response"]["url"].endswith("/api/data"))) else None}')
    print('== 五:Network.setBlockedURLs 阻止加载图片(不下载就不占流量)')
    for lab, blocked in (('不阻止', []), ('阻止 *.png', ['*.png'])):
        sv.reset(); pg4 = ch.new_page(); pg4.send('Network.enable'); pg4.send('Network.setBlockedURLs', urls=blocked); pg4.goto(B + '/'); pg4.drain(0.6)
        fails = [e for e in evs(pg4, 'Network.loadingFailed')]
        print(f'  {lab}:服务器收到 /a.png {sum(1 for l in sv.log if l["path"] == "/a.png")} 次,其它请求 {sum(1 for l in sv.log if l["path"] != "/a.png")} 次;浏览器侧 loadingFailed {len(fails)} 个({[(f.get("errorText"), f.get("blockedReason")) for f in fails]});页面 JS 里 window.n = {pg4.eval("window.n")}'); pg4.close()
    print('== 六:一个页面里连续收到很多大响应,事后还能取到几个(每个 1 MiB,不可压缩,共 150 个,fetch 后马上不取、全部结束之后再统一取)')
    for lab, buf in (('Network.enable 默认', None), ('maxTotalBufferSize=10 MiB', 10 * 1024 * 1024), ('maxTotalBufferSize=1 GiB', 1024 ** 3)):
        pg5 = ch.new_page(); pg5.goto(B + '/')
        if buf is None: pg5.send('Network.enable')
        else: pg5.send('Network.enable', maxTotalBufferSize=buf, maxResourceBufferSize=buf)
        pg5.events.clear(); pg5.eval("window.k = 0; (async () => { for (let i = 0; i < 150; i++) { const r = await fetch('/blob?mb=1&i=' + i); await r.arrayBuffer(); window.k++; } })()")
        t0 = time.time()
        while time.time() - t0 < 40 and pg5.eval('window.k') < 150: pg5.drain(0.2)
        pg5.drain(0.3)
        rs = [e for e in evs(pg5, 'Network.responseReceived') if '/blob' in e['response']['url']]
        okc = sum(1 for e in rs if body(pg5, e['requestId'])[0] == 'ok')
        first = [i for i, e in enumerate(rs) if body(pg5, e['requestId'])[0] == 'ok']
        print(f'  {lab}:页面收完 {pg5.eval("window.k")} 个,事后取得到响应体的有 {okc} 个' + (f',取得到的是第 {first[0]}–{first[-1]} 个(从 0 开始)' if first else ''))
        pg5.close()
purge()

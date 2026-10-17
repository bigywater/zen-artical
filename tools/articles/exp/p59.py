import sys, os, json, asyncio, threading, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
from pcdp import Chrome
import aiohttp, aiohttp.web as web, websocket
tee('p59')
d = pdir('p59')

class WSServer:
    """后台线程里的 aiohttp WebSocket 服务器:每 50 ms 产生一个递增序号的行情(不管有没有客户端),订阅后推送;可配置空闲断开、定时断开、Origin 校验、断线后按 since 回放"""
    def __init__(self, port):
        self.port = port; self.seq = 0; self.buf = collections.deque(maxlen=2000); self.cfg = dict(idle=None, drop_after=None, origin=None, replay=True); self.log = []; self.loop = None
        self.th = threading.Thread(target=self._run, daemon=True); self.ready = threading.Event(); self.th.start(); self.ready.wait(5)
    async def tick(self):
        while True:
            await asyncio.sleep(0.05); self.seq += 1; self.buf.append(dict(seq=self.seq, price=round(100 + (self.seq % 17) * 0.1, 2)))
    async def ws(self, req):
        org = req.headers.get('Origin')
        self.log.append(('handshake', dict(origin=org, ua=req.headers.get('User-Agent', ''), ext=req.headers.get('Sec-WebSocket-Extensions'))))
        if self.cfg['origin'] is not None and org != self.cfg['origin']: return web.Response(status=403, text='bad origin')
        w = web.WebSocketResponse(); await w.prepare(req)
        t0 = time.monotonic(); last_in = time.monotonic(); sub = None; st = dict(sent=0)
        async def pump():
            cursor = None
            while not w.closed:
                if sub is not None:
                    if cursor is None: cursor = (sub['since'] + 1) if (sub.get('since') is not None and self.cfg['replay']) else self.seq + 1
                    while cursor <= self.seq:
                        for m in list(self.buf):
                            if m['seq'] == cursor: await w.send_json(m); st['sent'] += 1; cursor += 1; break
                        else: cursor = self.buf[0]['seq']        # 缓冲里已经没有这个序号了:从最早的开始
                await asyncio.sleep(0.02)
        task = asyncio.ensure_future(pump()); code = None
        while True:
            try: msg = await w.receive(timeout=0.05)
            except asyncio.TimeoutError:
                if self.cfg['drop_after'] and time.monotonic() - t0 > self.cfg['drop_after']: code = 1001
                elif self.cfg['idle'] and time.monotonic() - last_in > self.cfg['idle']: code = 4000
                if code: task.cancel(); await w.close(code=code); break
                continue
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR): break
            last_in = time.monotonic()
            if msg.type == aiohttp.WSMsgType.TEXT:
                j = json.loads(msg.data)
                if j.get('op') == 'subscribe': sub = dict(since=j.get('since'))
                elif j.get('op') == 'ping': await w.send_json({'op': 'pong'})
        task.cancel()
        self.log.append(('closed', dict(by='server' if code else 'client', code=code or w.close_code, sent=st['sent'])))
        return w
    def _run(self):
        self.loop = asyncio.new_event_loop(); asyncio.set_event_loop(self.loop)
        app = web.Application(); app.router.add_get('/ws', self.ws)
        runner = web.AppRunner(app); self.loop.run_until_complete(runner.setup()); site = web.TCPSite(runner, '127.0.0.1', self.port); self.loop.run_until_complete(site.start())
        self.loop.create_task(self.tick()); self.ready.set(); self.loop.run_forever()
    def stop(self): self.loop.call_soon_threadsafe(self.loop.stop)

PORT = free_port(9970); PORT2 = free_port(PORT + 1)
S = WSServer(PORT)
PAGE = ("<!doctype html><html><body><script>const ws = new WebSocket('ws://127.0.0.1:%d/ws'); window.got = 0; window.last = null;"
        "ws.onopen = () => ws.send(JSON.stringify({op:'subscribe'})); ws.onmessage = e => { window.got++; window.last = e.data; }; window.ws = ws;</script></body></html>" % PORT)
with Srv(lambda h: h.reply(200, PAGE.encode(), headers={'Content-Type': 'text/html'})) as sv, Chrome(free_port(PORT2), d) as ch:
    print('== 一:浏览器里的页面打开 WebSocket 后,CDP 的 Network 事件里能看到什么')
    S.log.clear(); pg = ch.new_page(); pg.send('Network.enable'); pg.goto(sv.url('/')); pg.drain(1.0)
    ev = [e for e in pg.events if e['method'].startswith('Network.webSocket')]
    kinds = collections.Counter(e['method'].replace('Network.webSocket', '') for e in ev)
    sent = [e['params']['response']['payloadData'] for e in ev if e['method'] == 'Network.webSocketFrameSent']
    recv = [json.loads(e['params']['response']['payloadData']) for e in ev if e['method'] == 'Network.webSocketFrameReceived']
    hs = next((e['params']['response'] for e in ev if e['method'] == 'Network.webSocketHandshakeResponseReceived'), {})
    created = next((e['params']['url'] for e in ev if e['method'] == 'Network.webSocketCreated'), None)
    print(f'  事件种类与个数:{dict(kinds)}')
    print(f'  WebSocket 地址:{created};握手响应状态 {hs.get("status")};页面发出的帧:{sent};收到的帧共 {len(recv)} 个,前 3 个 {recv[:3]};页面 JS 里数到 {pg.eval("window.got")} 条')
    bh = [x for k, x in S.log if k == 'handshake'][0]
    print(f'  浏览器的握手头(服务器记录):Origin={bh["origin"]};User-Agent={bh["ua"][:70]!r};Sec-WebSocket-Extensions={bh["ext"]}')
    print(f'  1 秒内收到 {len(recv)} 帧,约每 {1000 / max(1, len(recv)):.0f} ms 一帧;序号是否连续:{[m["seq"] for m in recv] == list(range(recv[0]["seq"], recv[0]["seq"] + len(recv)))}'); pg.close()
    print('== 二:不用浏览器,直接用 websocket-client 连:握手头、订阅、收 2 秒')
    S.log.clear(); w = websocket.create_connection(f'ws://127.0.0.1:{PORT}/ws', timeout=5); w.send(json.dumps({'op': 'subscribe'}))
    t0 = time.time(); got = []
    while time.time() - t0 < 2.0: got.append(json.loads(w.recv()))
    w.close(); time.sleep(0.2)
    hs = [x for k, x in S.log if k == 'handshake'][0]
    print(f'  服务器记录的握手:Origin={hs["origin"]},User-Agent={hs["ua"]!r},Sec-WebSocket-Extensions={hs["ext"]};2 秒内收到 {len(got)} 条({len(got) / 2:.0f} 条/秒),序号 {got[0]["seq"]}…{got[-1]["seq"]},连续:{[m["seq"] for m in got] == list(range(got[0]["seq"], got[-1]["seq"] + 1))}')
    print('== 三:服务器每 1.5 秒断开一次(模拟重启):不处理重连 / 重连后重新订阅 / 重连并带上 since 让服务器回放')
    S.cfg['drop_after'] = 1.5
    def run(mode, total=5.0):
        got = []; t0 = time.time(); w = None; reconnects = 0; last_seq = None
        while time.time() - t0 < total:
            try:
                if w is None:
                    w = websocket.create_connection(f'ws://127.0.0.1:{PORT}/ws', timeout=1); reconnects += 1
                    w.send(json.dumps({'op': 'subscribe', 'since': last_seq} if mode == 'resume' and last_seq else {'op': 'subscribe'}))
                m = json.loads(w.recv()); got.append(m['seq']); last_seq = m['seq']
            except Exception:
                w = None
                if mode == 'none': break
                time.sleep(0.3)        # 重连前等 0.3 秒
        if w:
            try: w.close()
            except Exception: pass
        gaps = sum(b - a - 1 for a, b in zip(got, got[1:]) if b > a + 1)
        return len(got), reconnects, gaps, (got[-1] - got[0] + 1) if got else 0
    for mode, lab in (('none', '断了就不再连'), ('resub', '断了等 0.3 秒重连并重新订阅(不带 since)'), ('resume', '重连并带上 since=最后收到的序号')):
        n, rc, gaps, span = run(mode); print(f'  {lab}:收到 {n} 条,连接 {rc} 次,序号缺口(丢失的条数){gaps},覆盖的序号范围 {span}')
    S.cfg['drop_after'] = None
    print('== 四:心跳:服务器 1.0 秒内收不到客户端的任何消息就主动关闭连接(关闭码 4000)')
    S.cfg['idle'] = 1.0
    for lab, hb in (('不发心跳', None), ('每 0.4 秒发一个应用层 ping', 0.4)):
        S.log.clear(); w = websocket.create_connection(f'ws://127.0.0.1:{PORT}/ws', timeout=0.2); w.send(json.dumps({'op': 'subscribe'})); t0 = time.time(); n = 0; last_ping = time.time(); how = '3 秒内未被关闭'
        while time.time() - t0 < 3.0:
            try:
                op, fr = w.recv_data_frame(True)
                if op == 8: how = f'收到关闭帧,关闭码 {int.from_bytes(fr.data[:2], "big")}'; break
                if op == 1: n += 1
            except websocket.WebSocketTimeoutException: pass
            except Exception as e: how = f'异常 {type(e).__name__}'; break
            if hb and time.time() - last_ping > hb: w.send(json.dumps({'op': 'ping'})); last_ping = time.time()
        el = time.time() - t0
        try: w.close()
        except Exception: pass
        time.sleep(0.3); cl = [x for k, x in S.log if k == 'closed']
        print(f'  {lab}:连接维持了 {el:.1f} 秒,收到 {n} 帧;客户端:{how};服务器记录:由{"服务器" if cl[0]["by"] == "server" else "客户端"}关闭,码 {cl[0]["code"]}')
    S.cfg['idle'] = None
    print('== 五:握手校验:服务器要求 Origin 必须是 http://shop.test')
    S.cfg['origin'] = 'http://shop.test'
    for lab, kw in (('默认(库自动补上 Origin: http://127.0.0.1:%d,即服务器自己的地址)' % PORT, {}), ('suppress_origin=True,真的不带 Origin 头', {'suppress_origin': True}), ('带错误的 Origin', {'origin': 'http://evil.test'}), ('带正确的 Origin', {'origin': 'http://shop.test'})):
        S.log.clear()
        try: w = websocket.create_connection(f'ws://127.0.0.1:{PORT}/ws', timeout=3, **kw); res = '握手成功'; w.close()
        except Exception as e: res = f'{type(e).__name__}: {str(e)[:42]}'
        print(f'  websocket-client {lab}:{res};服务器看到的 Origin={[x["origin"] for k, x in S.log if k == "handshake"]}')
    for lab, allow in (('服务器只允许页面自己的 Origin', 'self'), ('服务器只允许 http://shop.test', 'http://shop.test')):
        pg = ch.new_page(); pg.send('Network.enable'); S.cfg['origin'] = f'http://127.0.0.1:{sv.port}' if allow == 'self' else allow
        pg.goto(sv.url('/')); pg.drain(0.8); kinds = collections.Counter(e['method'].replace('Network.webSocket', '') for e in pg.events if e['method'].startswith('Network.webSocket'))
        print(f'  浏览器页面(Origin http://127.0.0.1:{sv.port})+ {lab}:页面 JS 里收到 {pg.eval("window.got")} 条;Network 事件 {dict(kinds)}'); pg.close()
S.stop(); purge()

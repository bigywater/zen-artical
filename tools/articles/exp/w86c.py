import sys, os, re, statistics, ssl, asyncio, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived
from aioquic.quic.configuration import QuicConfiguration
tee('w86c'); reset()
HOST = 'example.com'; IP = '104.20.23.154'
class C(QuicConnectionProtocol):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.h3 = H3Connection(self._quic); self.ev = asyncio.Queue()
    def quic_event_received(self, e):
        for x in self.h3.handle_event(e): self.ev.put_nowait(x)
async def get(ticket=None, zero_rtt=False, save=None):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, session_ticket=ticket, server_name=HOST)
    t0 = time.time()
    async with connect(IP, 443, configuration=cfg, create_protocol=C, wait_connected=not zero_rtt, session_ticket_handler=(lambda t: save.append(t)) if save is not None else None) as c:
        sid = c._quic.get_next_available_stream_id()
        c.h3.send_headers(sid, [(b':method', b'GET'), (b':scheme', b'https'), (b':authority', HOST.encode()), (b':path', b'/')], end_stream=True); c.transmit()
        th = None; st = None
        while True:
            e = await asyncio.wait_for(c.ev.get(), 10)
            if isinstance(e, HeadersReceived) and th is None: th = time.time(); st = dict(e.headers).get(b':status')
            if isinstance(e, DataReceived) and e.stream_ended: break
        t3 = time.time(); tls = c._quic.tls
        if save is not None:
            for _ in range(30):
                if save: break
                await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        return dict(head=(th - t0) * 1000, total=(t3 - t0) * 1000, resumed=tls.session_resumed, early=tls.early_data_accepted, st=st)
print('== 三:会话恢复与 0-RTT(对 example.com 的 HTTP/3;修正了 w86 最初版本里 session ticket 回调没有生效的错误):第一次完整握手并保存 session ticket;之后各 4 次——A 完整握手、B 带 ticket 恢复并等握手完成、C 带 ticket 的 0-RTT')
saved = []
r0 = asyncio.run(get(save=saved)); time.sleep(0.5)
print(f'  第一次(完整握手):响应头 {r0["head"]:.0f} ms,状态 {r0["st"]};收到 {len(saved)} 个 session ticket;ticket 的 max_early_data_size = {saved[-1].max_early_data_size if saved else None}')
if saved:
    res = {'A 完整握手': [], 'B 带 ticket,等握手完成': [], 'C 带 ticket,0-RTT': []}
    for i in range(4):
        for k, kw in (('A 完整握手', {}), ('B 带 ticket,等握手完成', dict(ticket=saved[-1])), ('C 带 ticket,0-RTT', dict(ticket=saved[-1], zero_rtt=True))):
            try: res[k].append(asyncio.run(get(**kw)))
            except Exception as e: print('  失败', k, repr(e)[:70])
    for k, v in res.items():
        if v: print(f'    {k:<24} 响应头 逐次 {[round(x["head"]) for x in v]} 中位 {statistics.median(x["head"] for x in v):.0f} ms;session_resumed = {v[0]["resumed"]},early_data_accepted = {v[0]["early"]},状态 {sorted({x["st"] for x in v})}')

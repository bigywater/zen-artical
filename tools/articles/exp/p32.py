import sys, os, struct, socket, collections, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
tee('p32')

print('== 一:urllib3 的 Retry 默认只重试哪些方法(allowed_methods),以及对 POST 的态度')
print(f'  Retry.DEFAULT_ALLOWED_METHODS = {sorted(Retry.DEFAULT_ALLOWED_METHODS)}')
r = Retry(total=3, status_forcelist=[503])
for m in ('GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS', 'TRACE', 'POST', 'PATCH'):
    print(f'  Retry(total=3, status_forcelist=[503]) 对 {m:<7}→ 状态码 503 时是否重试:{r.is_retry(m, 503)}')
r2 = Retry(total=3, status_forcelist=[503], allowed_methods=None)
print(f'  allowed_methods=None(对所有方法都重试):POST → {r2.is_retry("POST", 503)}')

# 一个"下单"服务器:收到 POST /order 就创建一个订单(服务器端副作用);可配置在创建订单后丢掉响应(模拟网络在回应途中断开)
class Shop:
    def __init__(self): self.orders = []; self.lock = threading.Lock(); self.mode = 'ok'; self.n = 0
    def handler(self, h):
        if h.command == 'POST' and h.path.startswith('/order'):
            with self.lock:
                self.n += 1
                key = next((v for k, v in h.hdrs if k.lower() == 'idempotency-key'), None)
                dup = key is not None and any(o[1] == key for o in self.orders)
                if not dup: self.orders.append((len(self.orders) + 1, key))
                oid = next(o[0] for o in self.orders if o[1] == key) if key is not None else len(self.orders)
                n = self.n
            if self.mode == 'drop_first' and n == 1:                # 订单已创建,但回应没发出去:连接被重置
                h.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); h.close_connection = True; h.connection.close(); return
            if self.mode == 'status503_first' and n == 1: return h.reply(503, b'busy')   # 先回 503(这时订单已创建)
            return h.reply(200, str(oid).encode())
        h.reply(200, b'ok')

def try_post(retry, headers=None, mode='drop_first', method='POST'):
    shop = Shop(); shop.mode = mode
    with Srv(shop.handler) as sv:
        s = requests.Session(); s.mount('http://', HTTPAdapter(max_retries=retry))
        try:
            r = s.request(method, sv.url('/order'), data=b'item=1', headers=headers or {}); res = f'{r.status_code}(订单号 {r.text})'
        except Exception as e: res = type(e).__name__
        return res, len(shop.orders), shop.n

print('== 二:下单服务器在"创建订单之后、回应之前"丢了连接(订单已创建,客户端没收到回应):POST 被重试会怎样')
cfgs = [('默认 Retry(total=3)(POST 不在 allowed_methods 里)', Retry(total=3)),
        ('Retry(total=3, allowed_methods=None)(对所有方法重试)', Retry(total=3, allowed_methods=None)),
        ('allowed_methods=None + 请求带 Idempotency-Key', Retry(total=3, allowed_methods=None))]
for i, (lab, rt) in enumerate(cfgs):
    res, orders, n = try_post(rt, {'Idempotency-Key': 'abc-123'} if i == 2 else None)
    print(f'  {lab}:客户端结果 {res};服务器收到 {n} 次 POST,实际创建了 {orders} 个订单')

print('== 三:服务器先创建订单、再回 503(客户端看到的是失败):被 status_forcelist 重试的 POST')
for lab, rt, hd in (('Retry(total=3, status_forcelist=[503])(POST 默认不重试)', Retry(total=3, status_forcelist=[503]), None),
                    ('allowed_methods=None, status_forcelist=[503]', Retry(total=3, status_forcelist=[503], allowed_methods=None), None),
                    ('同上 + Idempotency-Key', Retry(total=3, status_forcelist=[503], allowed_methods=None), {'Idempotency-Key': 'k-9'})):
    res, orders, n = try_post(rt, hd, mode='status503_first')
    print(f'  {lab}:客户端结果 {res};服务器收到 {n} 次 POST,创建了 {orders} 个订单')

print('== 四:同样的"丢回应"场景,幂等方法(PUT 到固定资源)被重试没有副作用,GET 也是')
class Store:
    def __init__(self): self.v = None; self.n = 0; self.lock = threading.Lock()
    def handler(self, h):
        with self.lock: self.n += 1; n = self.n
        if h.command == 'PUT': self.v = h.body
        if n == 1:
            h.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0)); h.close_connection = True; h.connection.close(); return
        h.reply(200, b'ok')
for m in ('PUT', 'GET'):
    st = Store()
    with Srv(st.handler) as sv:
        s = requests.Session(); s.mount('http://', HTTPAdapter(max_retries=Retry(total=3)))
        r = s.request(m, sv.url('/res/1'), data=b'v=1' if m == 'PUT' else None)
        print(f'  {m} 被重置一次后默认 Retry 自动重试:结果 {r.status_code},服务器收到 {st.n} 次,资源值 {st.v!r}')
print('== 五:Retry 的分项次数:read(读取阶段出错)的上限。GET 被重置一次(读取阶段出错)')
for lab, rt in (('Retry(total=3)', Retry(total=3)), ('Retry(total=3, read=0)(读取阶段不重试)', Retry(total=3, read=0)), ('Retry(total=3, read=1)', Retry(total=3, read=1)), ('Retry(total=0)', Retry(total=0))):
    st = Store()
    with Srv(st.handler) as sv:
        s = requests.Session(); s.mount('http://', HTTPAdapter(max_retries=rt))
        try: r = s.get(sv.url('/res/1')); res = str(r.status_code)
        except Exception as e: res = type(e).__name__
        print(f'  {lab}:结果 {res},服务器收到 {st.n} 次')
purge()

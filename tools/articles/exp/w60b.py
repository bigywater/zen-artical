import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tfo_common import *
tee('w60b'); reset()

def conns(P, port):
    out = []
    for p in syns(P, port):
        sa = [q for q in P if q['sp'] == port and q['dp'] == p['sp'] and q['fl'] & 0x12 == 0x12]
        out.append((p, sa[0] if sa else None))
    return out
def ck(p):
    d = p['optd'].get(34, b''); return d.hex()[:8] if len(d) >= 8 else '-'
def desc(i, p, sa):
    s = f'  第 {i} 个:SYN 载荷 {p["plen"]} 字节,TFO 选项长度 {topt(p) or "无"},cookie 前 4 字节 {ck(p)}'
    if sa is None: return s + ';没有 SYN+ACK'
    acc = '数据被接受' if p['plen'] and sa['ack'] - p['seq'] == p['plen'] + 1 else ('数据没被接受(ack = seq + 1)' if p['plen'] else '')
    return s + f';SYN+ACK 的 TFO 选项 {ck(sa) if 34 in sa["optd"] else "无"}' + (f',{acc}' if acc else '')

for n in (11, 12, 13): tfolab('alias', 'add', n)
try:
    print('== 一:干净的对照:服务端不开 TFO,目的地用 lo0 上新加的别名 127.77.0.11(客户端从没用过),连续 8 次 connectx(各带 6 字节):SYN 里有没有 TFO 选项、数据怎么到的、客户端会不会中途不再尝试')
    port = lab_port(); th, got = server('127.77.0.11', port, False, 8)
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        for i in range(8): client('127.77.0.11', port, b'hello%d' % i).close(); time.sleep(0.2)
        th.join(); time.sleep(0.3)
    P = dd(tcp_pkts(c.pcap)); print(f'  服务端收到的数据 {got}')
    for i, (p, sa) in enumerate(conns(P, port), 1): print(desc(i, p, sa) + f';SYN 选项 {[OPN.get(k_, k_) for k_, l in p["opts"]]}')

    print('== 二:服务端密钥轮换:目的地 127.77.0.12,服务端开 TFO。先把服务端密钥设成 K1,连接 1 取 cookie,连接 2~3 带数据;然后换成 K2,再连 4 次。看旧 cookie 被拒绝后的样子,客户端会不会拿到新 cookie')
    print('  设置 K1:' + (tfolab('key', '00112233445566778899aabbccddeeff') or '成功'))
    port = lab_port(); th, got = server('127.77.0.12', port, True, 7)
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        for i in range(3): client('127.77.0.12', port, b'hello%d' % i).close(); time.sleep(0.2)
        print('  换成 K2:' + (tfolab('key', 'ffeeddccbbaa99887766554433221100') or '成功'))
        for i in range(3, 7): client('127.77.0.12', port, b'hello%d' % i).close(); time.sleep(0.2)
        th.join(); time.sleep(0.3)
    P = dd(tcp_pkts(c.pcap)); print(f'  服务端收到的数据 {got},全部正确:{got == [b"hello%d" % i for i in range(7)]}')
    for i, (p, sa) in enumerate(conns(P, port), 1): print(desc(i, p, sa) + ('   ← 换密钥之后' if i > 3 else ''))
finally:
    for n in (11, 12, 13): tfolab('alias', 'del', n)
    tfolab('mode', 3)

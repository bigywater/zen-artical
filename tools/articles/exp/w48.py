import sys, os, re, struct, collections, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import dpkt
tee('w48'); reset()
def sc(k_): return sysout('sysctl', k_).strip()
def parse_pkts(path, port):
    data = []; acks = []
    with open(path, 'rb') as f:
        for ts, buf in dpkt.pcap.Reader(f):
            ip = bytes(buf[4:])
            if ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tl_ = struct.unpack('>H', ip[2:4])[0]; t = ip[ihl:]
            sp, dp, seq, ack, off, fl, win = struct.unpack('>HHIIBBH', t[:16]); hl = (off >> 4) * 4; plen = tl_ - ihl - hl; o = t[20:hl]
            if sp == port and plen > 0: data.append(dict(ts=ts, seq=seq, plen=plen))
            elif dp == port and fl & 0x10 and plen == 0:
                sack = []; i = 0
                while i < len(o):
                    k = o[i]
                    if k == 0: break
                    if k == 1: i += 1; continue
                    l = o[i + 1]
                    if k == 5:
                        for j in range(i + 2, i + l, 8): sack.append(struct.unpack('>II', o[j:j + 8]))
                    i += l
                acks.append(dict(ts=ts, ack=ack, sack=sack))
    return data, acks

print('== 一:SACK 相关的内核开关,以及握手时它有没有被协商(SYN / SYN-ACK 的选项里有 SACK-permitted)')
for k_ in ('net.inet.tcp.sack', 'net.inet.tcp.sack_maxholes', 'net.inet.tcp.sack_globalmaxholes', 'net.inet.tcp.sack_globalholes'):
    r = sc(k_); print('  ' + (r if 'unknown' not in r else f'({k_} 在本机不存在)'))
print('  SYN 里的 SACK-permitted(kind 4,2 字节)是双方协商的:两边都带才能在 ACK 里使用 SACK 选项(kind 5)——w37 / w38 已经看到本机和 example.com 都带了')

print('== 二:丢包下 ACK 里的 SACK 块:lo0 上 netlab 3% 丢包 + 单向 20 ms 延迟,服务端发 4 MiB;抓接收方发出的所有纯 ACK,解码 SACK 选项(每个块是 [左边缘, 右边缘) 两个 32 位序号)')
p = lab_port(); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', p)); ls.listen(); info = {}
def srv():
    cn, _ = ls.accept(); cn.sendall(b'z' * (4 << 20)); time.sleep(0.8); info['ti'] = tcp_info(cn); cn.close()
threading.Thread(target=srv, daemon=True).start()
with lossy(loss=3, delay=20, bw=0):
    with Cap(f'tcp port {p}', iface='lo0', write=True) as c:
        t0 = time.time(); k = socket.create_connection(('127.0.0.1', p)); n = 0
        while n < (4 << 20):
            d = k.recv(1 << 20)
            if not d: break
            n += len(d)
        dt = time.time() - t0; time.sleep(1.2); k.close()
data, acks = parse_pkts(c.pcap, p)
isn = min(d['seq'] for d in data) - 1
withs = [a for a in acks if a['sack']]; cnt = collections.Counter(len(a['sack']) for a in withs)
print(f'  传输 4 MiB 用了 {dt:.2f} 秒;发送方 tcp_info:发出 {info["ti"]["txpackets"]} 个包,重传 {info["ti"]["txretransmitpackets"]} 个({info["ti"]["txretransmitbytes"]} 字节,占发送字节的 {info["ti"]["txretransmitbytes"] / info["ti"]["txbytes"] * 100:.2f}%);设定的丢包率是 3%')
print(f'  接收方发出的纯 ACK(抓到的记录,含 dummynet 重复){len(acks)} 条,其中带 SACK 选项的 {len(withs)} 条;SACK 块个数的分布:' + ';'.join(f'{k_} 块 × {v}' for k_, v in sorted(cnt.items())))
ex = [a for a in withs if len(a['sack']) >= 2][:1] or withs[:1]
for a in ex:
    print(f'  一个例子:累积确认号(相对)= {a["ack"] - isn},SACK 块(相对序号):' + ';'.join(f'[{l - isn}, {r - isn})  长 {r - l} 字节' for l, r in a['sack']))
above = sum(1 for a in withs if all(l >= a['ack'] and (r - l) > 0 for l, r in a['sack'] if (l - a['ack']) & 0xffffffff < 2 ** 31))
print(f'  所有带 SACK 的 ACK 里,SACK 块位于累积确认号之上(中间有洞)的 {above} / {len(withs)} 条;块的最大个数 {max(cnt) if cnt else 0}(TCP 选项空间只有 40 字节,带时间戳时头部 12 字节,每块 8 字节,所以最多 3 块)')

print('== 三:SACK 让重传精确到洞:对每个带 SACK 的 ACK,累积确认号指向的是第一个洞的开头;看发送方随后重传的段是不是正好从这个序号开始')
byseq = collections.defaultdict(list)
for d_ in data: byseq[d_['seq']].append(d_['ts'])
retx = {}
for seq, L in byseq.items():
    L.sort(); cl = [L[0]]
    for t in L[1:]:
        if t - cl[-1] > 0.03: cl.append(t)
    if len(cl) >= 2: retx[seq] = cl
holes = sorted({a['ack'] for a in withs})
hit = sum(1 for h in holes if h in retx)
print(f'  带 SACK 的 ACK 指向的“第一个洞”(去重后)有 {len(holes)} 个,其中发送方确实重传了从这个序号开始的段的有 {hit} 个;发送方被重传过的段一共 {len(retx)} 个')
sizes = collections.Counter(next(d_['plen'] for d_ in data if d_['seq'] == s) for s in retx)
print(f'  被重传的段大小:{dict(sizes)}——每个重传的都是丢掉的那个整段,没有把洞之后已经收到的数据重发一遍')
tot_sent = sum(d_['plen'] for d_ in data if True)
print(f'  对比“累积确认、没有 SACK”的做法(只能从洞开始往后重传,或者等超时一个一个试):本次发送方实际重传 {info["ti"]["txretransmitbytes"]} 字节 = {info["ti"]["txretransmitpackets"]} 个完整的段;洞之后已经被接收方收到的字节有很多(SACK 块里报告了),发送方因此知道不必重传它们')

print('== 四:DSACK(RFC 2883):接收方用 SACK 的第一个块报告“我收到了重复的数据”,块的左边缘低于累积确认号;用来发现不必要的重传。统计这次抓包里有没有')
d_n = 0; exd = None
for a in withs:
    l, r = a['sack'][0]
    if (l - a['ack']) & 0xffffffff >= 2 ** 31 or r - l > 0 and ((a['ack'] - l) & 0xffffffff) < 2 ** 31 and l != a['ack']:
        if ((a['ack'] - l) & 0xffffffff) < 2 ** 31 and ((a['ack'] - l) & 0xffffffff) > 0: d_n += 1; exd = exd or a
print(f'  第一个 SACK 块的左边缘低于累积确认号的 ACK(DSACK 报告){d_n} 条' + (f';一个例子:累积确认号 {exd["ack"] - isn},第一个块 [{exd["sack"][0][0] - isn}, {exd["sack"][0][1] - isn})' if exd else ';这次没有出现'))

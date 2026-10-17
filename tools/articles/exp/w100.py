import sys, os, re, struct, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
tee('w100'); reset()
NTP_EPOCH = 2208988800
def ntp_ts(t): return struct.pack('>II', int(t + NTP_EPOCH), int((t + NTP_EPOCH) % 1 * 2 ** 32))
def ts_to_float(b): s, f = struct.unpack('>II', b); return s - NTP_EPOCH + f / 2 ** 32
def query(host, port=123, tmo=3, ip=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(tmo); ip = ip or socket.gethostbyname(host)
    pkt = bytearray(48); pkt[0] = (0 << 6) | (4 << 3) | 3; t1 = time.time(); pkt[40:48] = ntp_ts(t1)
    s.sendto(bytes(pkt), (ip, port)); d, _ = s.recvfrom(1024); t4 = time.time(); s.close()
    return ip, d, t1, t4
def parse(d, t1, t4):
    li_vn_mode, stratum, poll, prec = struct.unpack('>BBBb', d[:4]); rdelay, rdisp = struct.unpack('>II', d[4:12]); refid = d[12:16]
    org = ts_to_float(d[24:32]); rx = ts_to_float(d[32:40]); tx = ts_to_float(d[40:48]); ref = ts_to_float(d[16:24])
    offset = ((rx - t1) + (tx - t4)) / 2; delay = (t4 - t1) - (tx - rx)
    return dict(li=li_vn_mode >> 6, vn=(li_vn_mode >> 3) & 7, mode=li_vn_mode & 7, stratum=stratum, poll=poll, prec=prec, rdelay=rdelay / 65536, rdisp=rdisp / 65536, refid=refid, org=org, rx=rx, tx=tx, ref=ref, offset=offset, delay=delay)
def refid_str(p):
    if p['stratum'] <= 1: return p['refid'].rstrip(b'\0').decode('ascii', 'replace')
    return '.'.join(str(x) for x in p['refid'])

print('== 一:NTP 的请求与应答都是 48 字节的 UDP 报文(端口 123)。手工拼一个客户端请求(版本 4,模式 3),发给 ntp.aliyun.com,逐字段解析应答')
ip, d, t1, t4 = query('ntp.aliyun.com'); p = parse(d, t1, t4)
print(f'  请求 48 字节,首字节 0x23 = LI 0 | 版本 4 | 模式 3(客户端);只有 transmit 时间戳(最后 8 字节)有值;应答 {len(d)} 字节,来自 {ip}')
print(f'  应答头:LI={p["li"]}(0=正常),版本 {p["vn"]},模式 {p["mode"]}(4=服务器),stratum {p["stratum"]},poll {p["poll"]}(2^{p["poll"]} 秒),precision {p["prec"]}(2^{p["prec"]} 秒 ≈ {2 ** p["prec"] * 1e9:.0f} ns)')
print(f'  根延迟 root delay {p["rdelay"] * 1000:.2f} ms,根离散度 root dispersion {p["rdisp"] * 1000:.2f} ms,参考标识 {refid_str(p)}(stratum ≥ 2 时是上游服务器的 IPv4 地址,stratum 1 时是 4 字符的时钟源名如 GPS)')
print(f'  四个时间戳(都是 64 位:32 位整数秒 + 32 位小数,起点 1900-01-01):')
print(f'    T1 originate(我发出请求的时刻,被服务器原样抄回)= {p["org"]:.6f},与我记录的 T1 {t1:.6f} 差 {abs(p["org"] - t1) * 1e6:.2f} µs(32 位小数的精度 ≈ 0.23 ns,但是 Python float 只有微秒量级)')
print(f'    T2 receive(服务器收到)= {p["rx"]:.6f};T3 transmit(服务器发出)= {p["tx"]:.6f};T4(我收到)= {t4:.6f}')
print(f'    服务器的处理时间 T3 − T2 = {(p["tx"] - p["rx"]) * 1e6:.1f} µs;往返时间 T4 − T1 = {(t4 - t1) * 1000:.2f} ms')
print(f'  偏移 offset = ((T2 − T1) + (T3 − T4)) ÷ 2 = {p["offset"] * 1000:.2f} ms;延迟 delay = (T4 − T1) − (T3 − T2) = {p["delay"] * 1000:.2f} ms')

print('== 二:几个真实服务器,各问 8 次(间隔 1 秒),看偏移与延迟的分布。偏移 = 本机时钟比服务器快(+)或慢(−)多少')
rows = []
for host in ('ntp.aliyun.com', 'ntp.tencent.com', 'time.cloudflare.com', 'pool.ntp.org'):
    offs = []; dels = []; st = None; ids = None
    for i in range(8):
        try: ip, d, t1, t4 = query(host); p = parse(d, t1, t4); offs.append(p['offset'] * 1000); dels.append(p['delay'] * 1000); st = p['stratum']; ids = refid_str(p)
        except Exception: pass
        time.sleep(1)
    if offs: rows.append((host, st, ids, offs, dels)); 
    else: print(f'  {host}:无应答')
print('    服务器                  stratum  参考标识           偏移中位(ms)  偏移范围(ms)           延迟中位(ms)  延迟范围(ms)')
for host, st, ids, offs, dels in rows: print(f'    {host:<22} {st:^7}  {ids:<16} {statistics.median(offs):>10.2f}   [{min(offs):>7.2f}, {max(offs):>7.2f}]   {statistics.median(dels):>10.2f}   [{min(dels):.2f}, {max(dels):.2f}]')
allmed = [statistics.median(r[3]) for r in rows]
print(f'  各服务器给出的偏移中位数 {[round(x, 1) for x in allmed]} ms:它们互相一致(差 {max(allmed) - min(allmed):.1f} ms)说明本机时钟相对标准时间的偏移就是这个量级;单次测量的抖动(范围)远大于偏移的真值误差,所以 NTP 客户端要多次采样、取延迟最小的那一次')

print('== 三:用本机自写的 NTP 服务器验证公式:服务器把自己的时钟故意拨快 +250 ms。往返对称(netlab 每方向 50 ms)时,算出的 offset 应该就是 +250 ms 的相反数(本机相对服务器慢 250 ms → offset = +250);delay 应约等于 100 ms')
SKEW = 0.250; reply_delay = [0.0]
def srv(port, stop):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', port)); s.settimeout(0.3)
    while not stop[0]:
        try: d, a = s.recvfrom(1024)
        except socket.timeout: continue
        rx = time.time() + SKEW; out = bytearray(48); out[0] = (0 << 6) | (4 << 3) | 4; out[1] = 2; out[2] = 6; out[3] = 0xEC; out[12:16] = bytes([127, 0, 0, 1])
        out[24:32] = d[40:48]; out[32:40] = ntp_ts(rx)
        out[40:48] = ntp_ts(time.time() + SKEW); out[16:24] = ntp_ts(rx - 5)
        if reply_delay[0]: time.sleep(reply_delay[0])  # T3 已经盖章,之后才耽搁:相当于返程路径变慢
        s.sendto(bytes(out), a)
    s.close()
port = lab_port(); stop = [False]; threading.Thread(target=srv, args=(port, stop), daemon=True).start(); time.sleep(0.3)
res = {}
with lossy(loss=0, delay=50, bw=0):
    offs = []; dels = []
    for i in range(10):
        ip, d, t1, t4 = query('127.0.0.1', port=port); p = parse(d, t1, t4); offs.append(p['offset'] * 1000); dels.append(p['delay'] * 1000); time.sleep(0.1)
print(f'  对称往返(每方向 50 ms):offset 中位 {statistics.median(offs):.2f} ms(服务器拨快了 {SKEW * 1000:.0f} ms;本机相对服务器慢 → offset 为 +{SKEW * 1000:.0f});delay 中位 {statistics.median(dels):.2f} ms(≈ 2 × 50 ms)')
print(f'  误差:offset 与真值 {SKEW * 1000:.0f} ms 之差 {abs(statistics.median(offs) - SKEW * 1000):.2f} ms')

print('== 四:路径不对称是 NTP 的天花板:让服务器在回复前多等 80 ms,等于只有返程变慢 80 ms(去程 50 ms、返程 130 ms)。公式假设两个方向一样,所以 offset 会被带偏')
reply_delay[0] = 0.080
with lossy(loss=0, delay=50, bw=0):
    offs = []; dels = []
    for i in range(10):
        ip, d, t1, t4 = query('127.0.0.1', port=port); p = parse(d, t1, t4); offs.append(p['offset'] * 1000); dels.append(p['delay'] * 1000); time.sleep(0.1)
print(f'  返程多 80 ms 后:offset 中位 {statistics.median(offs):.2f} ms(真值仍是 +250 ms);delay 中位 {statistics.median(dels):.2f} ms')
print(f'  offset 的误差 = {statistics.median(offs) - SKEW * 1000:+.2f} ms,恰好是不对称量 80 ms 的一半的相反数({-80 / 2:.0f} ms):NTP 把整个往返时间平分给两个方向,所以它测不出也修正不了不对称——这是网络对时精度的根本限制')
reply_delay[0] = 0; stop[0] = True

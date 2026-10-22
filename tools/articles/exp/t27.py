import sys, os, json, socket; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
tee('t27'); reset()
NODE = r'''
import sys, time, json, socket, random, os
idx, n, ports, offset_ms, duration, seed = int(sys.argv[1]), int(sys.argv[2]), json.loads(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
rng = random.Random(seed); sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(('127.0.0.1', ports[idx])); sock.settimeout(0.002)
def pt(): return int((time.time() * 1000) + offset_ms)          # 本节点的“物理时钟”(毫秒):真实时间加上人为注入的偏差
L = 0; vc = [0] * n; hl, hc = 0, 0; seq = 0
def hlc_tick(msg_l=None, msg_c=None):
    global hl, hc
    p = pt(); old = hl
    if msg_l is None:
        hl = max(old, p); hc = hc + 1 if hl == old else 0
    else:
        hl = max(old, msg_l, p)
        if hl == old and hl == msg_l: hc = max(hc, msg_c) + 1
        elif hl == old: hc += 1
        elif hl == msg_l: hc = msg_c + 1
        else: hc = 0
def emit(kind, mid=None, peer=None):
    global seq; seq += 1
    print(json.dumps({'node': idx, 'seq': seq, 'kind': kind, 'pt': pt(), 'L': L, 'vc': list(vc), 'hlc': [hl, hc], 'mid': mid, 'peer': peer}), flush=True)
t_end = time.time() + duration; mc = 0
while time.time() < t_end:
    try:
        data, _ = sock.recvfrom(4096); m = json.loads(data)
        L = max(L, m['L']) + 1; vc = [max(a, b) for a, b in zip(vc, m['vc'])]; vc[idx] += 1; hlc_tick(m['hlc'][0], m['hlc'][1]); emit('recv', m['mid'], m['from'])
    except socket.timeout: pass
    if rng.random() < 0.08:
        if rng.random() < 0.7:                                    # 发消息给随机的另一个节点
            peer = rng.choice([j for j in range(n) if j != idx]); mc += 1; mid = f'{idx}-{mc}'
            L += 1; vc[idx] += 1; hlc_tick(); sock.sendto(json.dumps({'mid': mid, 'from': idx, 'L': L, 'vc': vc, 'hlc': [hl, hc]}).encode(), ('127.0.0.1', ports[peer])); emit('send', mid, peer)
        else: L += 1; vc[idx] += 1; hlc_tick(); emit('local')
'''
(TT / 't27_node.py').write_text(NODE)
N = 3; OFF = [0, 50, -80]; ports = [free_port() for _ in range(N)]
def run_cluster(offsets, duration=4.0):
    ps = [subprocess.Popen([sys.executable, str(TT / 't27_node.py'), str(i), str(N), json.dumps(ports), str(offsets[i]), str(duration), str(100 + i)], stdout=subprocess.PIPE, text=True) for i in range(N)]
    ev = []
    for p in ps:
        out, _ = p.communicate(timeout=60); ev += [json.loads(l) for l in out.splitlines() if l.strip()]
    return ev
def analyze(ev):
    ev = sorted(ev, key=lambda e: (e['L'], e['node'], e['seq']))               # Lamport 顺序与因果一致,拿来当处理顺序
    idx = {(e['node'], e['seq']): i for i, e in enumerate(ev)}; sends = {e['mid']: i for i, e in enumerate(ev) if e['kind'] == 'send'}
    anc = [0] * len(ev); last = {}
    for i, e in enumerate(ev):
        a = 0
        if e['node'] in last: a |= anc[last[e['node']]] | (1 << last[e['node']])
        if e['kind'] == 'recv' and e['mid'] in sends: j = sends[e['mid']]; a |= anc[j] | (1 << j)
        anc[i] = a; last[e['node']] = i
    return ev, anc, sends
def hb(anc, i, j): return bool(anc[j] >> i & 1)                                 # i 先于 j
def vc_leq(a, b): return all(x <= y for x, y in zip(a, b))
print(f'{N} 个节点各是一个独立进程(UDP 互发消息),各自带着人为注入的物理时钟偏差(毫秒):{OFF};每个事件同时记录物理时间、Lamport 时钟、向量时钟、混合逻辑时钟(HLC);“谁先于谁”的真值由消息收发图(程序顺序 + 发送 → 接收)的可达性得到')

print('== 一:物理时钟加上偏差:一条消息的接收事件的物理时间戳,小于它的发送事件的时间戳——即因果上后发生的事件,时间戳却更小')
rows = []
for name, offs in (('三个节点时钟完全一致(偏差 0)', [0, 0, 0]), (f'偏差 {OFF} ms', OFF)):
    ev = run_cluster(offs); sends = {e['mid']: e for e in ev if e['kind'] == 'send'}; rec = [e for e in ev if e['kind'] == 'recv' and e['mid'] in sends]
    bad = [sends[e['mid']]['pt'] - e['pt'] for e in rec if e['pt'] < sends[e['mid']]['pt']]
    rows.append((name, len(rec), len(bad), f'{max(bad) if bad else 0} ms'))
table(rows, ['时钟偏差', '收到的消息数', '接收时间戳 < 发送时间戳的消息数', '最大倒退量'])
print('  偏差为 0 时(本机同一个时钟)没有一条消息倒退;偏差 [0, +50, -80] 时,从“快”的节点发给“慢”的节点的消息,在接收方看来是“来自未来”——这里注入的偏差只是模拟机器之间的时钟不同步')

print('== 二:Lamport 时钟与因果:a 先于 b 就一定 L(a) < L(b);反过来不成立。抽 20000 对事件,看真正并发的事件对被 Lamport 排出了先后的比例(向量时钟、物理时钟作对照)')
ev = run_cluster(OFF); ev, anc, sends = analyze(ev); n = len(ev); rng = random.Random(27)
viol_l = sum(1 for e in ev if e['kind'] == 'recv' and e['mid'] in sends and not ev[sends[e['mid']]]['L'] < e['L'])
conc = rel = 0; l_ordered_conc = pt_wrong_rel = pt_wrong_conc = vc_correct = 0; tot = 0
for _ in range(20000):
    i, j = rng.randrange(n), rng.randrange(n)
    if i == j: continue
    tot += 1; a_b, b_a = hb(anc, i, j), hb(anc, j, i)
    va, vb = ev[i]['vc'], ev[j]['vc']; vc_ab = vc_leq(va, vb) and va != vb; vc_ba = vc_leq(vb, va) and va != vb
    vc_correct += (vc_ab == a_b and vc_ba == b_a)
    if a_b or b_a:
        rel += 1; first, second = (ev[i], ev[j]) if a_b else (ev[j], ev[i]); pt_wrong_rel += (first['pt'] >= second['pt'])
    else:
        conc += 1; l_ordered_conc += (ev[i]['L'] != ev[j]['L'])
print(f'  共 {n} 个事件;Lamport 条件 “发送的 L < 接收的 L” 被违反的消息数:{viol_l}')
print(f'  抽样 {tot} 对:有因果关系的 {rel} 对,真正并发的 {conc} 对')
print(f'  并发的 {conc} 对里,Lamport 给出了先后(L 不相等)的有 {l_ordered_conc} 对({l_ordered_conc / conc * 100:.1f}%):单看 Lamport 值分不清“有因果”还是“碰巧数字大小不同”')
print(f'  有因果关系的 {rel} 对里,按物理时间戳反而是“后发生的更小或相等”的有 {pt_wrong_rel} 对({pt_wrong_rel / rel * 100:.1f}%)')
print(f'  向量时钟对全部 {tot} 对的判定(a 先于 b / b 先于 a / 并发)和真值一致的有 {vc_correct} 对({vc_correct / tot * 100:.1f}%)')

print('== 三:向量时钟的代价:每条消息要带 N 个计数器;N 个节点的消息头大小(JSON 序列化,计数器取 5 位数)')
rows = []
for nn in (3, 10, 50, 200):
    vcs = json.dumps([12345] * nn); lam = json.dumps(12345); hl = json.dumps([1792250000000, 12])
    rows.append((nn, f'{len(lam)} 字节', f'{len(hl)} 字节', f'{len(vcs)} 字节'))
table(rows, ['节点数 N', 'Lamport(1 个整数)', 'HLC(l, c)', '向量时钟(N 个整数)'])
print('  Lamport 和 HLC 的大小不随节点数增长,向量时钟线性增长;换来的是向量时钟能精确判定并发')

print('== 四:混合逻辑时钟(HLC):(l, c) 里 l 追着物理时间走但不倒退,c 在物理时间不前进时补充序号;看因果是否被保住,以及 l 离物理时间多远')
ev2 = ev; viol_h = sum(1 for e in ev2 if e['kind'] == 'recv' and e['mid'] in sends and not tuple(ev2[sends[e['mid']]]['hlc']) < tuple(e['hlc']))
chains = bad_h = bad_pt = 0
rng = random.Random(5)
for _ in range(20000):
    i, j = rng.randrange(n), rng.randrange(n)
    if i != j and hb(anc, i, j): chains += 1; bad_h += (not tuple(ev[i]['hlc']) < tuple(ev[j]['hlc'])); bad_pt += (ev[i]['pt'] >= ev[j]['pt'])
drift = [e['hlc'][0] - e['pt'] for e in ev2]; cs = [e['hlc'][1] for e in ev2]
print(f'  “发送的 HLC < 接收的 HLC” 被违反的消息数 {viol_h};抽样的有因果关系的 {chains} 对里,HLC 顺序和因果相反的 {bad_h} 对(同一批 {chains} 对里,物理时间戳顺序和因果相反或相等的有 {bad_pt} 对)')
print(f'  l 与事件发生时本节点物理时钟的差(l - pt):最小 {min(drift)} ms,最大 {max(drift)} ms(注入的偏差之差最大是 {max(OFF) - min(OFF)} ms);c 的最大值 {max(cs)},c > 0 的事件占 {sum(1 for c in cs if c > 0) / len(cs) * 100:.1f}%')
print('  HLC 把“因果”交给逻辑部分、把“离真实时间不远”交给物理部分:时间戳还能当成大致的墙上时间用,偏差也有上界(取决于节点间时钟偏差)')

print('== 五:最后写入者胜(LWW)用哪种时间戳(这一节不是进程实测,是用 HLC / Lamport 的更新规则和注入的时钟偏差,对 1000 对随机间隔的因果写入做计算;Lamport 的结果由规则本身保证):节点 B(时钟 +50 ms)写入 v1,节点 C(时钟 -80 ms)在收到 v1 之后(因果上在后)写入 v2;两次写入相隔 g ms(0 到 300 随机),看 v2 会不会被 v1 压掉')
def hlc_after_recv(pt_c, m):                                  # C 收到带着 B 的 HLC 的消息之后,用 C 的物理时钟做写入时间戳
    l0, c0 = 0, 0; l = max(l0, m[0], pt_c)
    c = (max(c0, m[1]) + 1) if (l == l0 and l == m[0]) else ((c0 + 1) if l == l0 else ((m[1] + 1) if l == m[0] else 0)); return (l, c)
rng = random.Random(9); lost_wall = lost_hlc = lost_lam = 0; T = 1000
for _ in range(T):
    t = 1_000_000.0; g = rng.random() * 300                    # t 是“真实时间”;B 在 t 写,C 在 t + g 写
    ts_b_wall = t + 50; ts_c_wall = t + g - 80
    lost_wall += (ts_c_wall < ts_b_wall)                        # 物理时间戳 LWW:v2 的时间戳更小 → v1 获胜
    hb_ = (int(t + 50), 0); hc_ = hlc_after_recv(int(t + g - 80), hb_); lost_hlc += (hc_ < hb_)
    lam_b, lam_c = 1, 2; lost_lam += (lam_c < lam_b)            # Lamport:C 收到 B 的消息后 L = max(L, 1) + 1
table([('物理时钟时间戳', T, lost_wall, f'{lost_wall / T * 100:.1f}%'), ('HLC 时间戳', T, lost_hlc, f'{lost_hlc / T * 100:.1f}%'), ('Lamport 时间戳', T, lost_lam, f'{lost_lam / T * 100:.1f}%')], ['LWW 用的时间戳', '写入对数', '因果上在后的 v2 被压掉的次数', '比例'])
print(f'  用物理时钟做 LWW,两个节点时钟差 130 ms:相隔不到 130 ms 的因果写入,后面的会输给前面的(这里相隔 0 到 300 ms 均匀分布,理论上约 130/300 = 43%);HLC 和 Lamport 保证因果在后的时间戳更大')
reset(); (TT / 't27_node.py').unlink(missing_ok=True)

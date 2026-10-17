import json
from lib import *
R = J('r128'); cb = R['combos']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
dn = 'DENIED Redis is running in protected mode…'
def s(x): return dn if x.startswith('(error) DENIED') else x.replace('(error) ', '')
steps = [
    step(f"出厂默认:不带配置文件 redis-server --port。CONFIG GET bind = {R['a_cfg'][0][1]},protected-mode = {R['a_cfg'][1][1]},监听 *:端口。经 127.0.0.1 PING → PONG;经本机的局域网地址 {R['lan']} PING → DENIED …connections are only accepted from the loopback interface。", n=fl([['bind * -::*', '监听所有网卡'], ['127.0.0.1 → PONG', ''], [f'{R["lan"]} → DENIED', '']], done=[1], mark=[2]), kv=KV([['默认', '监听全部,但 protected-mode 拦非回环']], ['默认'])),
    step(f"B:bind * · protected-mode yes · 无密码:回环 {s(cb['B']['lo'])},局域网 {s(cb['B']['lan'])}。protected-mode 的触发条件是「default 用户没密码」,来源是非回环地址。", t=tl([f"回环: {s(cb['B']['lo'])}", f"局域网: {s(cb['B']['lan'])}"], cur=[0], mark=[1]), kv=KV([['B', '局域网被拒']], ['B'])),
    step(f"C:加了 requirepass:回环 {s(cb['C']['lo'])};局域网无 AUTH {s(cb['C']['lan'])};局域网 AUTH 之后 {s(cb['C']['lan_auth'])}。有了密码 protected-mode 不再拦截,由密码负责。", t=tl([f"回环: {s(cb['C']['lo'])}", f"局域网(无 AUTH): {s(cb['C']['lan'])}", f"局域网(AUTH 后): {s(cb['C']['lan_auth'])}"], cur=[2], mark=[1]), kv=KV([['C', '密码接管']], ['C'])),
    step(f"D:protected-mode no · 无密码:回环 {s(cb['D']['lo'])},局域网 {s(cb['D']['lan'])}——完全裸奔。出厂默认那台实例在运行时 CONFIG SET protected-mode no 之后,局域网 PING 也变成 {R['a_after_no']}。", t=tl([f"回环: {s(cb['D']['lo'])}", f"局域网: {s(cb['D']['lan'])}"], cur=[0], mark=[1]), kv=KV([['D', '没有任何保护']], ['D'])),
    step(f"E:显式 bind 127.0.0.1 {R['lan']} · protected-mode yes · 无密码:回环 {s(cb['E']['lo'])},局域网 {s(cb['E']['lan'])}。显式 bind 到了局域网地址,protected-mode 仍然拦截(和「配了 bind 就不再保护」的说法不同,以本次实测为准)。", t=tl([f"回环: {s(cb['E']['lo'])}", f"局域网: {s(cb['E']['lan'])}"], cur=[0], mark=[1]), kv=KV([['E', 'bind 了局域网地址仍被拒']], ['E'])),
    step(f"用 ACL 给 default 用户加密码(不写 requirepass):局域网无 AUTH → {s(R['acl_pw']['lan'])};AUTH 之后 → {s(R['acl_pw']['lan_auth'])}。效果和 requirepass 一样。", kv=KV([['ACL SETUSER default >密码', '同样解除 protected-mode 的拦截']], ['ACL SETUSER default >密码'])),
]
A = dict(
    n=128, series='redis', tags='Redis,安全,Protected Mode,真实验证,动画演示',
    desc=f'Protected Mode 实测:用本机的回环地址和局域网地址({R["lan"]})做对照,出厂默认、bind *、requirepass、protected-mode no、显式 bind 局域网地址、ACL 设密码,各种组合下谁能连、谁被 DENIED。',
    lead='Redis 有个 Protected Mode:没设密码时只接受来自回环地址的连接。它到底在什么条件下生效?加了密码呢?写了 bind 呢?这篇不靠文档转述,直接用本机的回环地址和局域网地址做对照实验。',
    facts=[('DENIED', '默认(protected-mode yes、default 无密码)时,来自非回环地址的连接被拒,并给出明确的报错'), ('不看 bind', '显式 bind 到局域网地址,protected-mode 仍然拒绝非回环来源(本次实测)'), ('密码接管', '给 default 设了密码(requirepass 或 ACL)之后,protected-mode 不再拦截,由 NOAUTH / AUTH 负责')],
    body=[
        sec('出厂默认', '', term('', blk('r128', 1)), '<p>不带配置文件启动时,Redis 监听所有网卡(<code>bind * -::*</code>),但 <code>protected-mode yes</code> 把非回环来源拦下。启动日志里有一条 WARNING:「Redis does not require authentication. Redis will accept connections from any local client.」——日志说的是「本地」。</p>'),
        sec('四种组合', '', term('', blk('r128', 2)), '<p>本机对自己的局域网地址发起连接,服务端看到的来源是局域网地址,不是回环,所以可以在一台机器上做这个对照。结论:protected-mode 只在「default 用户没有密码」并且来源不是回环时拒绝。</p>'),
        sec('用 ACL 设密码', '', term('', blk('r128', 3)), '<p>用 ACL 给 default 加密码与 <code>requirepass</code> 等价。</p>'),
        sec('别把它当成安全措施', '', '<p>Protected Mode 是最后一道兜底:防的是「忘了配置就暴露」。<code>CONFIG SET protected-mode no</code> 一条命令就能关掉(上面第一节的实验),它也不会保护任何已经在回环上的、来自同机其它进程的连接。真正的保护是密码 / ACL、只 bind 需要的地址、防火墙和 TLS。</p>'),
        sec('分步演示:谁能连', '', demo('Protected Mode', [('n', 'flow', '实例状态'), ('t', 'term', '连接结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + f'。本机局域网地址 {R["lan"]}(从本机连自己的局域网地址,来源不是回环)', '没有验证:IPv6 来源、Unix socket 连接、来自另一台机器的真实网络连接(这里用同机不同地址代替)、Redis 8 之前版本的行为、Docker / 容器网络里的来源地址、bind 到具体地址时 protected-mode 的文档描述与本次结果的差异原因'],
)

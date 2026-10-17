import json
from lib import *
R = J('r126'); b = R['brute']; un = R['unauth']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("没设密码时发 AUTH:服务端拒绝,提示 called without any password configured for the default user。AUTH 不是「试一下」,是要求服务端已经配置了密码。", n=fl([['AUTH whatever', 'ERR … without any password configured']], mark=[0]), kv=KV([['requirepass', '未设置']], ['requirepass'])),
    step("设了 requirepass 之后,没登录的连接:PING、GET、SET、ECHO、INFO、COMMAND COUNT、CLIENT SETNAME、SELECT 全部 NOAUTH Authentication required;HELLO 2(不带 AUTH)也是 NOAUTH;只有 QUIT 回 OK。", t=tl([f"{k:<18} {v[:60]}" for k, v in un.items()], mark=list(range(len(un)))), kv=KV([['能做的', 'AUTH / HELLO … AUTH / QUIT']], ['能做的'])),
    step("三种登录:AUTH <密码>(等于 default 用户)、AUTH default <密码>、HELLO 2 AUTH default <密码>,登录后 ACL WHOAMI 都是 default。错误密码 → WRONGPASS invalid username-password pair or user is disabled(用户名错、密码错、用户被 off,同一句话,不区分)。", n=fl([['AUTH 密码', 'default'], ['AUTH default 密码', 'default'], ['HELLO 2 AUTH …', 'default'], ['错误密码', 'WRONGPASS']], done=[0, 1, 2], mark=[3]), kv=KV([['WRONGPASS', '不区分用户不存在 / 密码错 / 用户 off']], ['WRONGPASS'])),
    step("requirepass 就是 default 用户的密码:ACL LIST 里 default 从 nopass 变成 #哈希。有个坑:ACL SETUSER default nopass 把它改回免密后,CONFIG GET requirepass 仍返回旧密码明文;再执行同值的 CONFIG SET requirepass 也不会把密码加回去(default 依旧 nopass)。CONFIG GET requirepass 本身会返回明文密码。", n=fl([['CONFIG SET requirepass', 'default: #哈希'], ['ACL SETUSER default nopass', 'default: nopass'], ['CONFIG GET requirepass', '仍显示明文旧密码'], ['同值 CONFIG SET', '无效,仍 nopass']], done=[0], mark=[1, 2, 3]), kv=KV([['CONFIG GET requirepass', '返回明文'], ['以谁为准', 'ACL LIST']], ['以谁为准'])),
    step("同一条连接可以再次 AUTH 切换身份(alice → bob,WHOAMI 随之变化)。之后用错误密码 AUTH bob → WRONGPASS,但连接仍然是 bob,没有被降级或断开。", n=fl([['AUTH alice', 'WHOAMI = alice'], ['AUTH bob', 'WHOAMI = bob'], ['AUTH bob 错误密码', 'WRONGPASS'], ['WHOAMI', 'bob(不变)']], done=[0, 1], mark=[2, 3]), kv=KV([['失败的 AUTH', '不影响已有登录身份']], ['失败的 AUTH'])),
    step("改密码:先用旧密码登录一条连接,再 CONFIG SET requirepass 新密码——旧连接继续可用;新连接用旧密码 → WRONGPASS,用新密码才行。改密码不会踢掉已登录的连接。", n=fl([['旧连接(已登录)', '继续可用'], ['新连接 + 旧密码', 'WRONGPASS'], ['新连接 + 新密码', 'OK']], done=[0, 2], mark=[1]), kv=KV([['已登录连接', '不受改密码影响']], ['已登录连接'])),
    step("密码会不会泄露到观察工具:MONITOR 里 AUTH 的参数是 (redacted);SLOWLOG(阈值调到 0)里 AUTH、CONFIG SET requirepass、ACL SETUSER 的敏感参数也是 (redacted);CLIENT LIST 里没有出现密码文本。", t=tl(['MONITOR: "AUTH" "(redacted)" "(redacted)"'] + [f"SLOWLOG: {a}" for a in R['slowlog'][:3]], cur=[0, 1, 2, 3]), kv=KV([['MONITOR / SLOWLOG', 'AUTH 参数被打码']], ['MONITOR / SLOWLOG'])),
    step(f"猜密码有多快(本机回环):一问一答 {b['n1']} 次错误 AUTH 用 {b['secs1']:.2f} s ≈ {b['rate1']:.0f} 次/秒;流水线一次发出 {b['n2']} 次错误 AUTH + 1 次正确 AUTH,{b['secs2']:.2f} s 后就收到最后的 PONG(≈ {b['rate2']:.0f} 次/秒),服务端 acl_access_denied_auth 增加 {b['counter']}——每次尝试都被计数,客户端却只收到 {b['wrong_replies']} 条 WRONGPASS 回复。", b=bars([['一问一答 次/秒', b['rate1'], f"{b['rate1']:.0f}"], ['流水线 次/秒', b['rate2'], f"{b['rate2']:.0f}"]], b['rate2'], mark=[0, 1]), kv=KV([['服务端计数', b['counter']], ['客户端收到的 WRONGPASS', b['wrong_replies']]], ['服务端计数'])),
]
A = dict(
    n=126, series='redis', tags='Redis,认证,ACL,安全,真实验证,动画演示',
    desc=f'Redis 认证流程实测:未登录只能 AUTH / HELLO / QUIT;WRONGPASS 不区分用户与密码错误;requirepass 就是 default 用户的密码,CONFIG GET requirepass 返回明文;AUTH 参数在 MONITOR / SLOWLOG 里被打码;本机上错误密码尝试可达 {b["rate1"]:.0f} 次/秒(一问一答)、流水线 {b["rate2"]:.0f} 次/秒。',
    lead='连上 Redis 之后到底要经过什么才能执行命令?这篇把认证流程每一步的服务端回答量出来:没登录能做什么,几种登录方式,requirepass 和 ACL 是什么关系,改密码对老连接的影响,密码会不会漏到监控里,以及最关键的——错误密码能试多快。',
    facts=[('NOAUTH', '设了密码后未登录的连接,除 AUTH / HELLO … AUTH / QUIT 外全部被拒'), (f'{b["rate1"]:.0f}/s', f'本机回环上一问一答的错误 AUTH 速率;流水线约 {b["rate2"]:.0f}/s,没有观察到任何限速或锁定'), ('明文', 'CONFIG GET requirepass 返回明文密码;AUTH 在 MONITOR / SLOWLOG 里被打码')],
    body=[
        sec('没设密码时的 AUTH,以及设了之后未登录能做什么', '', term('', blk('r126', 1)), term('', blk('r126', 2)), '<p>设了 <code>requirepass</code> 后,未登录连接发出的几乎任何命令都是 <code>NOAUTH</code>,包括 <code>PING</code>、<code>INFO</code>、<code>HELLO 2</code>(不带 AUTH)。<code>QUIT</code> 回 OK(它只是关连接)。</p>'),
        sec('三种登录方式', '', term('', blk('r126', 3)), '<p>错误的用户名、错误的密码、被 <code>off</code> 的用户,得到的是同一句 <code>WRONGPASS</code>,攻击者无法据此判断用户名是否存在。</p>'),
        sec('requirepass 与 default 用户', '', term('', blk('r126', 4)), '<p><code>requirepass</code> 只是设置 default 用户密码的旧接口。要小心两点:一是 <code>CONFIG GET requirepass</code> 返回的是明文,任何有 <code>+config|get</code> 权限的用户都能读到(第 123 篇的子命令粒度可以限制);二是 <code>ACL SETUSER default nopass</code> 之后 <code>CONFIG GET requirepass</code> 还显示旧值,同值的 <code>CONFIG SET requirepass</code> 没有效果。判断当前到底要不要密码,看 <code>ACL LIST</code> 里的 default 一行。</p>'),
        sec('身份切换、改密码', '', term('', blk('r126', 5)), term('', blk('r126', 6)), '<p>同一条连接可以重新 AUTH 成另一个用户。失败的 AUTH 不改变当前身份。改密码只影响之后的登录,已经登录的连接继续有效——所以怀疑密码泄露时,改密码之后还要把旧连接踢掉(<code>CLIENT KILL</code> 本文没有验证)。</p>'),
        sec('密码会不会漏到观察工具里', '', term('', blk('r126', 7)), '<p>AUTH 的参数、<code>CONFIG SET requirepass</code> 与 <code>ACL SETUSER</code> 里的密码在 SLOWLOG 里都是 <code>(redacted)</code>;MONITOR 里 AUTH 也被打码。这次 MONITOR 抓取里没有出现 <code>CONFIG SET</code> 和 <code>ACL SETUSER</code> 两行(原因没有验证)。但要注意:<code>redis.conf</code> 里的 <code>requirepass</code> 是明文,备份与配置文件的权限见第 132 篇。</p>'),
        sec('错误密码能试多快', '', term('', blk('r126', 8)), f'<p>一问一答 {b["rate1"]:.0f} 次/秒,流水线把 {b["n2"]} 次错误尝试在 {b["secs2"]:.2f} s 里送完,最后的正确密码照样收到 <code>OK</code>。服务端把每次尝试都计入 <code>acl_access_denied_auth</code>,但流水线里的失败回复客户端只收到了 {b["wrong_replies"]} 条——为什么没有验证,只是观察到的事实。这里没有观察到任何延迟、限速或锁定。所以 Redis 的密码不能当「有人试就会被挡住」的机制,它需要足够长的随机密码 + 不暴露在不可信网络。</p>'),
        sec('分步演示:认证的每一步', '', demo('Redis 认证', [('n', 'flow', '请求与结果'), ('t', 'term', '输出'), ('b', 'bars', '尝试速度'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。本机回环、密码是测试用的短串', '没有验证:网络往返下的尝试速度、CLIENT KILL USER、多连接并发下的速率、Redis 8 之前版本的 MONITOR 打码行为、流水线里失败回复被合并/丢弃的原因、密码比较是否为常量时间'],
)

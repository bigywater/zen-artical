import json
from lib import *
R = J('r125'); ag = R['agg']; br = R['brute']; cp = R['cap']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
rs = R['reasons']
steps = [
    step("四种失败各触发一次:DEL(命令被拒)、GET other:1(key 被拒)、PUBLISH(这个用户没有 +publish,所以是命令被拒;频道权限那一层没走到)、错误密码 AUTH。ACL LOG 里得到 4 条,reason 分别是 command、key、command、auth。", t=tl([f"reason={a:<8} context={b:<8} object={c:<8} count={d}" for a, b, c, d in rs], cur=[0, 1, 2, 3]), kv=KV([['字段', ' '.join(R['fields'])]], ['字段'])),
    step(f"同一种失败连续 {200} 次(同一用户、同一 key):只有 {ag['entries']} 条记录,count = {ag['count']}。换一个 key(other:2)就是新的一条。ACL LOG 按(原因、上下文、对象、用户)合并。", b=bars([['GET other:1 被拒次数', 200, '200'], ['ACL LOG 条数', ag['entries'], str(ag['entries'])]], 200, mark=[0], done=[1]), kv=KV([['合并后 count', ag['count']]], ['合并后 count'])),
    step(f"暴力猜密码:500 次错误 AUTH(每次新连接)用了 {br['secs']:.2f} s——约 {br['n'] / br['secs']:.0f} 次/秒;ACL LOG 里只有 {br['entries']} 条 reason=auth,count = {br['count']}。日志能告诉你「被猜了多少次」,但不会替你封锁。", b=bars([['错误 AUTH 次数', br['n'], str(br['n'])], ['ACL LOG count', br['count'], str(br['count'])]], 500, mark=[0, 1]), kv=KV([['耗时', f"{br['secs']:.2f} s"], ['条数', br['entries']]], ['耗时'])),
    step(f"context 字段区分来源:直接执行是 toplevel;MULTI 里被拒是 {R['ctx'][1][1]};Lua 脚本里被拒是 {R['ctx'][0][1]}(脚本报错 ERR ACL failure in script: … has no permissions to run the 'del' command)。", n=fl([['toplevel', '直接执行'], ['multi', 'MULTI 里的命令'], ['lua', 'EVAL 里 redis.call']], mark=[1, 2]), kv=KV([['MULTI', 'context=multi'], ['EVAL', 'context=lua']], ['EVAL'])),
    step(f"acllog-max-len 默认 {R['maxlen_default']}。设成 5 后制造 12 条不同 key 的拒绝:只保留最新的 {cp['kept']} 条({', '.join(cp['objs'])}),旧的被挤掉。ACL LOG 2 只取最新 2 条,ACL LOG RESET 清空。", b=bars([['产生的不同拒绝', 12, '12'], ['保留', cp['kept'], str(cp['kept'])]], 12, mark=[0], done=[1]), kv=KV([['acllog-max-len', '128 → 5']], ['acllog-max-len'])),
]
A = dict(
    n=125, series='redis', tags='Redis,ACL,审计,安全,真实验证,动画演示',
    desc=f'ACL LOG 实测:command / key / auth 三种拒绝原因(本次触发到的);相同失败合并成一条(200 次 → count={ag["count"]});500 次错误 AUTH 用了 {br["secs"]:.2f} s 且只占 1 条日志;MULTI 与 Lua 里被拒有各自的 context;acllog-max-len 挤掉旧记录。',
    lead='用户权限配好了,谁在撞墙?ACL LOG 记录每一次被 ACL 拒绝的操作。这篇把它每个字段的含义、合并规则、上限都在本机触发一遍,并回答一个实际问题:暴力猜密码时它能告诉你什么。',
    facts=[('合并', '同用户、同原因、同对象的重复失败合成一条,count 递增(200 次 → 1 条)'), (f'{br["n"] / br["secs"]:.0f}/s', '本机上错误 AUTH 的尝试速率(每次新连接);日志里只有 1 条 count 累加'), ('128', 'acllog-max-len 默认值;超出后旧记录被挤掉')],
    body=[
        sec('四种拒绝', '', term('', blk('r125', 1)), '<p>reason 有 <code>command</code>(命令没权限)、<code>key</code>(key 没权限)、<code>auth</code>(认证失败),还有 <code>channel</code>(频道没权限,本文这一轮没有触发,没有验证)。<code>PUBLISH</code> 被记成 <code>command</code>,因为这个用户根本没有 <code>+publish</code>,判定停在命令那一层。<code>client-info</code> 是 <code>CLIENT LIST</code> 同样格式的一行,能看出是哪个连接(地址、name、库、最后命令)。</p>'),
        sec('合并规则', '', term('', blk('r125', 2)), f'<p>200 次相同的失败只有 {ag["entries"]} 条记录,<code>count</code> 是 {ag["count"]}。所以 ACL LOG 是「什么类型的拒绝、多少次」的摘要,不是逐条流水。要逐条审计需要另外的手段(这里没有验证)。</p>'),
        sec('暴力猜密码', '', term('', blk('r125', 3)), f'<p>{br["n"]} 次错误 AUTH 用了 {br["secs"]:.2f} s。Redis 对认证失败没有任何限速或锁定(本次实测中没有观察到),ACL LOG 只是把它们累加进一条 <code>reason=auth</code> 记录。所以:密码必须足够长且随机,并且不要把端口暴露给不可信网络(第 128、129 篇)。监控 <code>count</code> 的增长速度可以当告警信号。</p>'),
        sec('context:MULTI 与 Lua', '', term('', blk('r125', 4)), '<p>MULTI 里被拒的命令让整个事务 <code>EXECABORT</code>;Lua 里被拒则整个脚本报错。ACL LOG 用 <code>context</code> 字段告诉你这是从哪里来的。</p>'),
        sec('容量与清理', '', term('', blk('r125', 5)), '<p>日志有条数上限,超过 <code>acllog-max-len</code> 就挤掉最旧的。想长期留存要定期拉取(<code>ACL LOG</code>)并写到外部。</p>'),
        sec('分步演示:ACL LOG', '', demo('ACL LOG', [('t', 'term', 'ACL LOG 记录'), ('b', 'bars', '数量'), ('n', 'flow', 'context'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。500 次 AUTH 是本机回环、每次新建连接,速率取决于机器,只作数量级参考', '没有验证:reason=channel 的记录、长期运行下的合并窗口(文档说的时间窗口本文没有测)、并发多个连接的合并、ACL LOG 内存占用'],
)

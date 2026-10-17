import json
from lib import *
R = J('r97'); lt = R['latest']; h = R['history']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("延迟监控的事件类型有名字:这里出现 command(慢命令)和 aof-fsync-always(每次写 AOF 时 fsync 的耗时)。LATENCY LATEST 每个事件一行:[事件名, 最近一次的时间戳, 最近一次的毫秒数, 历史最大毫秒数]。", t=tm([f"{x[0]}  最近 {x[1]} ms  历史最大 {x[2]} ms" for x in lt]), kv=KV([['LATEST', '每个事件一行']], ['LATEST'])),
    step(f"LATENCY HISTORY command:该事件最近的采样点 [时间戳, 毫秒数]。我在同一秒内做了 DEBUG SLEEP ×3 和 KEYS *,却只有一个采样点(值 {h[0][1]} ms)——同一秒里的多个事件被合并成一个,记录的是该秒的最大值(这是我从这份数据和文档得到的理解,没有单独验证)。", t=tm([f"[{p[0]}, {p[1]} ms]" for p in h]), kv=KV([['采样点', f'{len(h)} 个']], ['采样点'])),
    step("LATENCY GRAPH command:把采样点画成 ASCII 图,标题给出 high / low / all time high。这里 high 100 ms、low 11 ms;图下面的数字是每列采样距今的时间。", t=tm(R['graph'].splitlines()[:6]), kv=KV([['GRAPH', 'high 100 ms / low 11 ms']], ['GRAPH'])),
    step("LATENCY RESET 清除事件:返回被清除的事件个数(2),之后 LATENCY LATEST 是空数组。", t=tm(['> LATENCY RESET', '(integer) 2', '> LATENCY LATEST', '(empty array)'], mark=[1, 3]), kv=KV([['RESET', '返回 2,LATEST 为空']], ['RESET'])),
    step("只有超过 latency-monitor-threshold 的才记录:阈值 100 ms 时 50 ms 的阻塞 LATEST 为空,150 ms 的记录为 151 ms。", t=tm(['50 ms(阈值 100)→ 空', '150 ms(阈值 100)→ command 151 ms'], cur=[1]), kv=KV([['阈值', '决定记不记']], ['阈值'])),
]
A = dict(
    n=98, series='redis', tags='Redis,LATENCY,延迟事件,真实验证,动画演示',
    desc=f'逐个命令看 Redis 的延迟监控:LATENCY LATEST 每个事件一行(事件名、最近一次时间戳与毫秒数、历史最大),HISTORY 每秒一个采样点(同一秒的 DEBUG SLEEP ×3 与 KEYS 合并为一个 {h[0][1]} ms 的采样点),GRAPH 画 ASCII 图,RESET 返回清除的事件数;阈值决定记不记录。',
    lead='LATENCY LATEST、HISTORY、GRAPH、RESET 是延迟监控的四个基础命令。这篇不看报告,只看数据:每个命令返回什么结构、采样的粒度是多大、RESET 之后剩什么、阈值边界在哪。',
    facts=[('4 个字段', 'LATENCY LATEST 每行:事件名、最近时间戳、最近毫秒数、历史最大毫秒数'), ('1 秒 1 点', '同一秒里的多个慢事件在 HISTORY 里只有一个采样点(该秒最大值)'), ('阈值', '不超过 latency-monitor-threshold 的事件不被记录')],
    body=[
        sec('LATENCY LATEST', '', term('', blk('r97', 2)), '<p>每个事件类型一行,四个字段。第一次出现的 <code>command</code> 事件最近一次 11 ms、历史最大 100 ms。</p>'),
        sec('LATENCY HISTORY', '', term('', blk('r97', 3)), '<p>返回该事件最近的采样点。我在同一秒内连续制造了 DEBUG SLEEP(30/60/90 ms)和 KEYS *,只得到一个 100 ms 的采样点,另一个 11 ms 的点来自稍晚的另一秒。</p>'),
        sec('LATENCY GRAPH', '', term('', blk('r97', 4)), '<p>标题里的 high、low 是当前保留的采样中的最大、最小值,括号里是历史最大;下面是竖条,最下面的数字是每一列距今的时间。</p>'),
        sec('LATENCY RESET', '', term('', blk('r97', 6)), '<p>返回被清除的事件数(2:command 与 aof-fsync-always),清完之后 LATEST 为空。</p>'),
        sec('阈值边界', '', term('', blk('r97', 7)), '<p>阈值 100 ms 时 50 ms 的阻塞不记录,150 ms 的记录为 151 ms。</p>'),
        sec('分步演示:四个命令', '', demo('LATENCY LATEST 与延迟事件', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。数据来自第 97 篇同一次实验', '没有验证:HISTORY 最多保留的采样点数、GRAPH 的刻度规则、多个事件类型同时出现、其它事件类型(fork、expire-cycle 等)'],
)

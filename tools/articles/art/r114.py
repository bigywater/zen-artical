import json
from lib import *
R = J('r114'); mx = R['max']; cn = R['conn']; tmo = R['timeout']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx_, cur=(), mark=(), done=()): return {'items': items, 'max': mx_, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("默认:maxclients = 10000;本机 shell 的 ulimit -n 是 1048576(文件描述符上限很大),所以 maxclients 就是 10000。Redis 启动时会检查系统的文件描述符上限,不够时会自动降低 maxclients(本机没有触发,日志里没有相关提示)。", t=tm(['CONFIG GET maxclients → 10000', 'INFO clients: maxclients = 10000', 'ulimit -n = 1048576'], cur=[0, 1, 2]), kv=KV([['默认 maxclients', '10000']], ['默认 maxclients'])),
    step(f"把 maxclients 设成 100,连续建 120 个连接:{mx['ok']} 个成功(含最初的管理连接),第 {mx['first']} 个开始被拒,回复 {mx['msg'].strip()},共 {mx['rej']} 个被拒;INFO stats 里 rejected_connections = 21。被拒的连接会收到一条错误再被关闭,不是无声地断开。", b=bars([['成功', mx['ok'], str(mx['ok'])], ['被拒', mx['rej'], str(mx['rej'])]], 110, done=[0], mark=[1]), kv=KV([['第 100 个起被拒', mx['msg'].strip()]], ['第 100 个起被拒'])),
    step(f"maxclients 满了以后,连管理连接(INFO)也连不上——所以生产上要给自己留出管理用的连接余量。", t=tm(['100 个连接已满', 'INFO → 连接被拒'], mark=[1]), kv=KV([['教训', '留出管理连接余量']], ['教训'])),
    step(f"timeout 2:空闲 2 秒的连接会被服务器关闭。实测空闲连接在 {tmo:.1f} 秒后被关闭(对端读到 EOF),比 2 秒多约 {tmo-2:.1f} 秒——空闲检查由后台定时任务(第 110 篇的 hz)周期性执行,不是精确定时。", b=bars([['配置 timeout', 2, '2 s'], ['实际关闭', tmo, f'{tmo:.1f} s']], 3.5, done=[0], mark=[1]), kv=KV([['timeout 2', f'{tmo:.1f} s 后关闭']], ['timeout 2'])),
    step(f"每个连接的内存与描述符:开 1000 个空闲连接,used_memory 增加约 {cn['per']*1000/1e6:.1f} MB(每个连接约 {cn['per']/1024:.1f} KB);Redis 进程打开的文件描述符有 {cn['fds']} 个(lsof 行数,含 1000 个连接与其它文件)——每个连接占一个文件描述符。", b=bars([['每个空闲连接 KB', cn['per'] / 1024, f"{cn['per']/1024:.1f} KB"], ['1000 个连接的文件描述符', cn['fds'] / 100, f"{cn['fds']}(÷100 显示)"]], 20, done=[0, 1]), kv=KV([['1000 个连接', f"+{cn['per']*1000/1e6:.0f} MB,{cn['fds']} 个描述符"]], ['1000 个连接'])),
]
A = dict(
    n=114, series='redis', tags='Redis,连接数,文件描述符,真实验证,动画演示',
    desc=f'验证 Redis 的连接限制:默认 maxclients 10000;设成 100 后第 {mx["first"]} 个连接起收到「ERR max number of clients reached」({mx["rej"]} 个被拒,rejected_connections = 21),此时连 INFO 都连不上;timeout 2 的空闲连接约 {tmo:.1f} 秒后被关闭;1000 个空闲连接每个约 {cn["per"]/1024:.0f} KB、占 1 个文件描述符。',
    lead='Redis 能同时接多少个连接?连接满了会怎样?一个连接占多少资源?这篇把 maxclients、文件描述符、空闲超时逐个验证:包括「maxclients 满了连管理连接都进不去」这个容易被忽略的后果。',
    facts=[('10000', '默认 maxclients(本机 ulimit -n 足够大,没有被自动降低)'), (f'第 {mx["first"]} 个', 'maxclients 100 时,开始被拒的连接序号(ERR max number of clients reached)'), (f'{cn["per"]/1024:.0f} KB / 个', '1000 个空闲连接的 used_memory 增量平均值(每个还占 1 个文件描述符)')],
    body=[
        sec('默认值', '', term('', blk('r114', 1)), '<p><code>maxclients</code> 默认 10000;实际可用还受进程的文件描述符上限(<code>ulimit -n</code>)限制——Redis 启动时会检查,不够就自动调小 <code>maxclients</code> 并在日志里说明。本机上限是 1048576,没有触发。</p>'),
        sec('连接满了', '', term('', blk('r114', 2)), f'<p>maxclients 100:第 {mx["first"]} 个及以后的连接收到 <code>-ERR max number of clients reached</code> 后被关闭,<code>INFO stats</code> 的 <code>rejected_connections</code> 是 21。<b>此时任何新连接都进不去,包括你想用来登录排查的那个</b>:我的脚本要先关掉一个已有连接,才能读到 INFO。</p>'),
        sec('空闲超时', '', term('', blk('r114', 3)), f'<p><code>timeout 2</code>:空闲连接在 {tmo:.1f} 秒后被关闭,对端读到 EOF。比配置的 2 秒略晚,因为空闲检查是后台周期任务(第 110 篇)。默认 <code>timeout 0</code> 表示不关闭空闲连接。</p>'),
        sec('每个连接的成本', '', term('', blk('r114', 4)), f'<p>1000 个空闲连接:<code>used_memory</code> 增加约 {cn["per"]*1000/1e6:.0f} MB(每个约 {cn["per"]/1024:.1f} KB),<code>lsof</code> 显示进程打开 {cn["fds"]} 个文件描述符(每个连接 1 个,加上 Redis 自己的若干个)。第 112 篇用 <code>mem_clients_normal</code> 得到的是每个约 8.5 KB,口径不同(这里含连接引起的全部分配)。所以 10000 个连接要预留百余 MB 内存与一万多个描述符。</p>'),
        sec('分步演示:连接的上限与成本', '', demo('Redis 连接数与文件描述符', [('t', 'term', '说明'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。maxclients 演示为临时设成 100;文件描述符数来自 lsof;timeout 演示为 2 秒', '没有验证:ulimit -n 小于 maxclients 时 Redis 自动降低的提示原文、tcp-backlog 与 somaxconn 对突发连接的影响、TLS 连接的额外开销、被 timeout 关闭的连接在客户端库里的表现'],
)

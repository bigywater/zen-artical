import json
from lib import *
R = J('r47'); saw = R['saw']; bench = R['bench']; big = R['big']; ln = dict((str(a), b) for a, b in R['len'])
ex, ap = saw['MAXLEN 1000'], saw['MAXLEN ~ 1000']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("流里已经有 1000 条,上限 MAXLEN 1000。接着逐条 XADD,每条后读 XLEN。stream-node-max-entries = 100:1000 条 = 10 个满节点。", ln1={'values': ['1000', '1000', '1000'], 'cur': []}, kv=KV([['节点容量', '100 条/节点']], ['节点容量'])),
    step(f"精确裁剪(MAXLEN 1000):每次 XADD 后立刻删掉最老的一条,XLEN 恒为 {min(ex)}(300 次采样最小 {min(ex)}、最大 {max(ex)})。", ln1={'values': [str(x) for x in ex[:20:2]], 'cur': []}, kv=KV([['XLEN 范围', f'{min(ex)} – {max(ex)}']], ['XLEN 范围'])),
    step(f"近似裁剪(MAXLEN ~ 1000):只有整个最老的节点都能删掉时才删,所以 XLEN 先涨到 {max(ap)},再一次掉 100 条回到 {min(ap)}——锯齿。取样:{ap[::20]}。", ln1={'values': [str(x) for x in ap[:20:2]], 'cur': []}, kv=KV([['XLEN 范围', f'{min(ap)} – {max(ap)}']], ['XLEN 范围'])),
    step(f"好处:每条 XADD 的耗时。稳态下:不裁剪 {bench['不裁剪']:.2f} µs,近似裁剪 {bench['MAXLEN ~ 1000']:.2f} µs,精确裁剪 {bench['MAXLEN 1000']:.2f} µs(20 万条管道写入,三次取中位)。", b=bars([['不裁剪', bench['不裁剪'], f"{bench['不裁剪']:.2f} µs"], ['MAXLEN ~ 1000', bench['MAXLEN ~ 1000'], f"{bench['MAXLEN ~ 1000']:.2f} µs"], ['MAXLEN 1000', bench['MAXLEN 1000'], f"{bench['MAXLEN 1000']:.2f} µs"]], 6, done=[1], mark=[2]), kv=KV([['精确 / 近似', f"{bench['MAXLEN 1000']/bench['MAXLEN ~ 1000']:.1f} 倍"]], ['精确 / 近似'])),
    step(f"我预想「一次裁很多」会很慢,实测不是:100 万条的流 XTRIM MAXLEN 0 一次删 100 万条只要 {big[0]:.1f} ms。整段节点是直接释放的,便宜的是整节点删除。", b=bars([['MAXLEN 0(删 100 万条)', big[0], f'{big[0]:.1f} ms'], ['MAXLEN ~ 0(默认 LIMIT,删 1 万条)', big[1], f'{big[1]:.1f} ms'], ['MAXLEN ~ 0 LIMIT 1000(删 1000 条)', big[2], f'{big[2]:.1f} ms']], max(big) * 1.2 or 1, done=[0]), kv=KV([['结论', '整节点删除本身很便宜']], ['结论'])),
    step("但近似裁剪有个默认的 LIMIT:MAXLEN ~ 0 只删了 10000 条(= 100 × stream-node-max-entries),不是全部;想清空要么用精确的 MAXLEN 0,要么多次调用。LIMIT 只能和 ~ 一起用,否则报 syntax error。", ln1={'values': ['~ 0 → 删 1 万条', '~ 0 LIMIT 1000 → 删 1000 条', '0 LIMIT 1000 → 语法错误'], 'mark': [2]}, kv=KV([['默认 LIMIT', '100 × stream-node-max-entries = 10000']], ['默认 LIMIT'])),
]
A = dict(
    n=47, series='redis', tags='Redis,Stream,XTRIM,真实验证,动画演示',
    desc=f'实测 Stream 的 MAXLEN ~(近似裁剪):逐条 XADD 时精确裁剪 XLEN 恒为 {min(ex)},近似裁剪在 {min(ap)}–{max(ap)} 之间锯齿(一次掉一个 100 条的节点);稳态下每条 XADD 耗时:不裁剪 {bench["不裁剪"]:.2f} µs、近似 {bench["MAXLEN ~ 1000"]:.2f} µs、精确 {bench["MAXLEN 1000"]:.2f} µs;整节点裁剪很便宜(100 万条 {big[0]:.1f} ms),但 ~ 的默认 LIMIT 只删 1 万条。',
    lead='给 Stream 限长有两种写法:MAXLEN 1000(精确)和 MAXLEN ~ 1000(近似)。文档说近似写法更高效。这篇把「更高效」量化,同时把「近似」的意思画出来:近似到底差多少,什么时候会多留,以及那个容易被忽略的 LIMIT。',
    facts=[(f'{min(ap)}–{max(ap)}', 'MAXLEN ~ 1000 时 XLEN 的实际波动区间(精确写法恒为 1000)'), (f'{bench["MAXLEN 1000"]/bench["MAXLEN ~ 1000"]:.1f} 倍', '稳态下精确裁剪比近似裁剪的单条 XADD 耗时'), (f'{big[0]:.1f} ms', '100 万条的流一次 XTRIM MAXLEN 0 的命令耗时')],
    body=[
        sec('近似的意思:按节点删,不按条删', '', term('', blk('r47', 1)), '<p>这一组恰好都落在 1000 条,因为总数 5000 是节点容量 100 的整数倍——看不出「近似」。要看清它,得逐条观察。</p>', term('', blk('r47', 2)),
            f'<p>先写满 5050 条,再逐条 XADD 300 次、每次读 XLEN。精确裁剪永远是 {min(ex)};近似裁剪在 {min(ap)}–{max(ap)} 之间锯齿:长度涨到 1099,再一次性掉 100 条(一个整节点),回到 1000 之后重新涨。<b>近似裁剪不会少于你给的上限,只会多留至多一个节点。</b></p>'),
        sec('节点容量改变「近似」的幅度', '', term('', blk('r47', 3)), f'<p>节点容量 10 与 100 时 5000 条之后 XLEN 都是 1000(恰好对齐);节点容量调到 500 后,同样的写入得到 {ln["500"]}。这一列取决于写入总数与节点边界的相对位置,只说明「多留的量不会超过一个节点」,不是稳定的数值。(默认还有 4096 字节的节点上限,见第 39 篇。)</p>'),
        sec('代价:每条 XADD 的耗时', '', term('', blk('r47', 4)), f'<p>流已满 1000 条的稳态下,不裁剪 {bench["不裁剪"]:.2f} µs/条;近似裁剪 {bench["MAXLEN ~ 1000"]:.2f} µs;精确裁剪 {bench["MAXLEN 1000"]:.2f} µs,是近似的 {bench["MAXLEN 1000"]/bench["MAXLEN ~ 1000"]:.1f} 倍。精确裁剪每次 XADD 都要改动最老节点里的一条(把它标记删除),近似裁剪则是每 100 次才整体释放一个节点(这一层解释来自现象和第 46 篇对 XDEL 的观察,我没有另外抓取内部调用)。这是管道下每条的均摊值,不含网络往返。</p>'),
        sec('一次裁很多:比想象的便宜,但有默认 LIMIT', '', term('', blk('r47', 5)),
            f'<p>我原以为一次清空 100 万条会阻塞很久。实测 <code>XTRIM MAXLEN 0</code> 删除 100 万条只花了 {big[0]:.1f} ms:整个节点是整体释放的。<code>MAXLEN ~ 0</code> 只删了 10000 条——近似写法有个默认的 <code>LIMIT</code>,等于 100 × <code>stream-node-max-entries</code>;显式给 <code>LIMIT 1000</code> 只删 1000 条。<code>LIMIT</code> 必须和 <code>~</code> 同时使用,否则报语法错误。</p><p><b>实际后果:</b>用 <code>MAXLEN ~ 0</code> 想清空一个大流,一次调用清不完,要么用精确的 <code>MAXLEN 0</code>,要么循环调用。</p>'),
        sec('分步演示:锯齿与代价', '', demo('MAXLEN ~ 近似裁剪', [('ln1', 'chips', 'XLEN 取样序列 / 说明'), ('b', 'bars', '耗时'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。单连接、管道 2000 条一批;每种写法测三次取中位数', '没有验证:多连接并发 XADD 下的差别、值更大时的差别、XTRIM 在有大量消费组 PEL 时的行为、MINID 写法的近似效果(本文只测了 MAXLEN)'],
)

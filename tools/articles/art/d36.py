from lib import *
import re
R = J('d36')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
perf = L('perf'); upd = L('upd')
def ms(l): return float(re.search(r'([\d.]+) ms', l).group(1))
def nq(l): return int(re.search(r'查询\s+(\d+)\s+次', l).group(1))
pl = [(nq(l), ms(l)) for l in perf]
bu = [l for l in upd if 'batch_size=' in l and l.strip().startswith('batch')]
bul = [(re.search(r'batch_size=(\d+)', l).group(1), int(re.search(r'查询\s+(\d+)\s+次', l).group(1)), ms(l)) for l in bu]
loop = [l for l in upd if l.startswith('逐个')][0]; loop_ms = ms(loop)
steps = [
    step(f"5000 条:循环 save() {pl[0][0]} 次查询 {pl[0][1]:.0f} ms,且每条都触发 pre_save / post_save;bulk_create(默认){pl[1][0]} 次查询 {pl[1][1]:.0f} ms;batch_size=1000 时 {pl[2][0]} 次(5 条 INSERT + BEGIN + COMMIT){pl[2][1]:.0f} ms。两种 bulk 都不触发信号(0/0)。", b=bars([['循环 save()(ms)', pl[0][1], f"{pl[0][1]:.0f}"], ['bulk_create(ms)', pl[1][1], f"{pl[1][1]:.0f}"], ['batch_size=1000(ms)', pl[2][1], f"{pl[2][1]:.0f}"]], pl[0][1] * 1.1, mark=[0], done=[1, 2]), kv=KV([['bulk_create', '不调用 save(),不发信号']], ['bulk_create'])),
    step("bulk_create 返回的对象在 SQLite(本机版本支持 RETURNING)上 pk 已被设置(如 15001、15002),auto_now_add 的字段也被填上了(字段自己的 pre_save 仍会运行)。", t=tl(R['pk'].splitlines()), kv=KV([['pk', '已设置(本次 SQLite)'], ['auto_now_add', '生效']], ['pk'])),
    step("bulk_update 的 SQL 是一条 UPDATE … SET n = CASE WHEN id = … THEN … END(BEGIN / COMMIT 包着)。5000 个对象:" + '、'.join(f"batch_size={b}:{q} 次查询 {m:.0f} ms" for b, q, m in bul) + f";逐个 save(update_fields=['n']):5000 次查询 {loop_ms:.0f} ms,并触发 5000 次信号。", b=bars([[f'batch_size={b}(ms)', m, f"{m:.0f}"] for b, q, m in bul] + [['逐个 save(ms)', loop_ms, f"{loop_ms:.0f}"]], max(m for b, q, m in bul + [(0, 0, loop_ms)]) * 1.1, done=[0, 1, 2], mark=[len(bul)]), kv=KV([['本机 SQLite', 'bulk_update 未必比逐个 save 快'], ['查询数', '随 batch_size 明显减少']], ['本机 SQLite'])),
    step("冲突处理:默认遇到重复 → IntegrityError(UNIQUE constraint failed);ignore_conflicts=True 静默跳过冲突行,返回对象的 pk 是 None;update_conflicts=True 配 unique_fields、update_fields 才会更新冲突行(表里 a 的 v 变成 100,新增 c)。", t=tl(R['conf'].splitlines(), cur=[0, 1, 2], mark=[1]), kv=KV([['ignore_conflicts', 'pk 不会回填'], ['update_conflicts', '需要 unique_fields + update_fields']], ['ignore_conflicts'])),
    step("限制:多表继承的子类 bulk_create → ValueError: Can't bulk create a multi-table inherited model;bulk_create 不触发 pre_save / post_save 信号(0 0),而一次 save() 触发 1 1。依赖信号做的事(缓存失效、审计、索引更新)在 bulk 操作里不会发生。", t=tl(R['limits'].splitlines(), mark=[0, 1], cur=[2]), kv=KV([['信号', 'bulk 不触发']], ['信号'])),
]
A = dict(
    n=36, series='django', tags='Django,ORM,bulk_create,bulk_update,真实验证,动画演示',
    desc=f'实测 bulk_create / bulk_update:5000 条循环 save() {pl[0][0]} 次查询 {pl[0][1]:.0f} ms,bulk_create {pl[1][0]} 次 {pl[1][1]:.0f} ms;bulk 不触发信号;ignore_conflicts 不回填 pk;多表继承不支持;本机 SQLite 上 bulk_update 未必比逐个 save 快。',
    lead='bulk_create 快是共识,但它「省掉了什么」「不能做什么」常被忽略:信号、pk、冲突、继承。bulk_update 又到底快多少?这篇在 5000 条数据上逐项验证。',
    facts=[(f'{pl[0][0]} → {pl[1][0]}', '5000 条:循环 save() → bulk_create 的查询次数'), ('0 次信号', 'bulk_create 不触发 pre_save / post_save;循环 save() 触发 5000 次'), ('bulk_update', f'本机 SQLite:不同 batch_size {bul[-1][2]:.0f}~{bul[0][2]:.0f} ms,逐个 save {loop_ms:.0f} ms——差别没有查询数那么大')],
    body=[
        sec('bulk_create vs 循环 save()', '', term('', blk('d36', 1)), '<p>查询数和耗时都差一个数量级(本机 SQLite,没有网络往返;换成远程数据库,差别只会更大)。<b>信号 0 次</b>——所以依赖 <code>post_save</code> 的逻辑不会执行。</p>'),
        sec('pk 与自动字段', '', term('', blk('d36', 2)), '<p>SQLite 3.35+ 与 PostgreSQL 支持 <code>RETURNING</code>,所以能回填 pk;其它数据库不保证(本文没有测)。字段自己的 <code>pre_save</code>(比如 <code>auto_now_add</code>)仍会执行。</p>'),
        sec('bulk_update', '', term('', blk('d36', 3)), '<p>用 <code>CASE WHEN</code> 一次更新多行。<code>batch_size</code> 控制每条 UPDATE 涵盖多少对象,同时决定查询数。<b>这里量到的耗时并没有随查询数同比下降</b>:SQLite 在本机没有网络往返,一条巨大的 <code>CASE WHEN</code> 本身有代价。这个结论只适用于这台机器的 SQLite,不代表远程数据库。</p>'),
        sec('冲突处理', '', term('', blk('d36', 4)), '<p><code>ignore_conflicts</code> 会让 pk 不再被回填(全是 None);<code>update_conflicts</code> 要同时给 <code>unique_fields</code> 和 <code>update_fields</code>。</p>'),
        sec('限制', '', term('', blk('d36', 5)), '<p>多表继承的子类、多对多字段(本文没有测)都不能靠 bulk_create 一次写完;绕过 <code>save()</code> 意味着自定义 <code>save()</code> 里的逻辑也不会运行。</p>'),
        sec('分步演示:bulk 系列', '', demo('bulk_create / bulk_update', [('b', 'bars', '耗时'), ('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite,5000 条;查询数含 BEGIN / COMMIT', '没有验证:PostgreSQL / MySQL 上的耗时与 bulk_update 的 SQL、pk 回填在 MySQL 上是否可用、多对多批量写入(through 表 bulk_create)、超大批量时 SQLite 变量个数上限触发的自动分批边界'],
)

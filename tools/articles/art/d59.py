from lib import *
R = J('d59'); ops = R['ops']
def o(i): return ops[i]
steps = [
    step(f"200 万行的表上,一个后台线程每 5 ms 更新一行(模拟线上写入)。加列 AddField(int, default=0, NOT NULL):迁移总用时 {o(0)['secs']:.2f} s(其中包含约 0.25 s 的 Django 进程启动),期间最长的一次写入 {o(0)['max_write_ms']:.0f} ms;AddField(null=True):{o(1)['secs']:.2f} s,写入最长 {o(1)['max_write_ms']:.0f} ms。加列是元数据变更,几乎不阻塞。", b=bars([[x['label'][:26], x['max_write_ms'], f"{x['max_write_ms']:.0f} ms"] for x in ops[:3]], 1300, done=[0, 1, 2]), kv=KV([['加列', '毫秒级,不阻塞写入']], ['加列'])),
    step(f"varchar(20) → varchar(60):{o(2)['secs']:.2f} s,写入最长 {o(2)['max_write_ms']:.0f} ms——放宽长度不重写表。integer → bigint:{o(3)['secs']:.2f} s,期间写入最长阻塞 {o(3)['max_write_ms']:.0f} ms(重写整张表,持有排他锁)。", b=bars([[x['label'][:30], x['max_write_ms'], f"{x['max_write_ms']:.0f} ms"] for x in ops[2:4]], o(3)['max_write_ms'] * 1.1, mark=[1], done=[0]), kv=KV([['改类型', f"写入被阻塞 {o(3)['max_write_ms']:.0f} ms"]], ['改类型'])),
    step(f"null → NOT NULL:{o(4)['secs']:.2f} s,写入最长阻塞 {o(4)['max_write_ms']:.0f} ms(要扫描全表验证没有 NULL)。普通 AddIndex(CREATE INDEX):{o(5)['secs']:.2f} s,写入最长阻塞 {o(5)['max_write_ms']:.0f} ms;用 AddIndexConcurrently(CREATE INDEX CONCURRENTLY,需要 atomic = False):{o(6)['secs']:.2f} s,写入最长只有 {o(6)['max_write_ms']:.0f} ms。", b=bars([[x['label'][:32], x['max_write_ms'], f"{x['max_write_ms']:.0f} ms"] for x in ops[4:7]], o(5)['max_write_ms'] * 1.1, mark=[0, 1], done=[2]), kv=KV([['建索引', 'CONCURRENTLY 几乎不阻塞写入']], ['建索引'])),
    step("规模效应:这里是 200 万行、每行很小、本机 SSD,阻塞时间都在秒级以内;真实的大表(几亿行、宽行)上,同样的操作会按行数线性放大到分钟甚至小时。要预估就在同规模的副本上先跑一遍,同时观察写入延迟。", kv=KV([['结论', '重写表 / 全表扫描 / 普通建索引 = 阻塞写入']], ['结论'])),
]
A = dict(
    n=59, series='django', tags='Django,Migration,大表,锁,PostgreSQL,真实验证,动画演示',
    desc=f'在 200 万行的 PostgreSQL 表上,一边每 5 ms 写一行一边跑迁移:加列几乎不阻塞({o(0)["max_write_ms"]:.0f} ms);integer → bigint 重写整表阻塞写入 {o(3)["max_write_ms"]:.0f} ms;改 NOT NULL {o(4)["max_write_ms"]:.0f} ms;普通建索引 {o(5)["max_write_ms"]:.0f} ms,CONCURRENTLY 只有 {o(6)["max_write_ms"]:.0f} ms。',
    lead='迁移在开发库上一秒完成,到了生产大表上会锁多久?这篇造一张 200 万行的表,让一个线程持续写入,再对它执行 7 种常见迁移操作,把「写入被阻塞了多久」量出来。',
    facts=[(f'{o(3)["max_write_ms"]:.0f} ms', 'integer → bigint(重写整表)期间,后台写入最长被阻塞的时间'), (f'{o(5)["max_write_ms"]:.0f} → {o(6)["max_write_ms"]:.0f} ms', '普通 CREATE INDEX → CREATE INDEX CONCURRENTLY 期间写入最长阻塞'), (f'{o(0)["max_write_ms"]:.0f} ms', '加带常量默认值的列(PostgreSQL)几乎不阻塞')],
    body=[
        sec('7 种操作实测', '', term('', blk('d59', 1)), '<p>「迁移总用时」包含 Django 命令自己的启动(约 0.25 s)。「期间写入最长一次」是后台线程在迁移进行期间(前后各留 0.3 s 余量)观察到的单次 <code>UPDATE</code> 最长耗时,平时中位数约 0.2–0.4 ms。</p>'),
        sec('怎么办', '', '<ul><li>加列:用 null=True 或常量默认值(第 60 篇)。</li><li>改类型、加 NOT NULL:分步做,或在低峰期做;先在副本上量。</li><li>建索引:PostgreSQL 用 <code>AddIndexConcurrently</code>(迁移要 <code>atomic = False</code>,失败后可能留下无效索引,要手工清理——这一点本文没有验证)。</li><li>任何迁移都要看它持有什么锁、持有多久;线上前先在等量数据上演练。</li></ul>'),
        sec('分步演示:迁移与写入阻塞', '', demo('大表迁移', [('b', 'bars', '写入最长阻塞'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9434,fsync 关闭),200 万行;后台线程 psycopg 直连每 5 ms 一次 UPDATE;每项只测一次', '没有验证:MySQL(在线 DDL 算法)、更大或更宽的表、多个并发写入者、SET lock_timeout 的保护效果、NOT VALID 约束两步法、CREATE INDEX CONCURRENTLY 失败后的清理'],
)

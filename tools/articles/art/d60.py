from lib import *
R = J('d60'); ops = R['ops']
def o(i): return ops[i]
steps = [
    step(f"200 万行、常量默认值:AddField(default=0) 用 {o(0)['secs']:.2f} s;Django 发出两条 SQL:ADD COLUMN … DEFAULT 0 NOT NULL,然后 ALTER COLUMN … DROP DEFAULT——模型里的 default 是 Django 层面的,建完列就把数据库的默认值去掉了。null=True(没有默认值):{o(1)['secs']:.2f} s,一条 SQL。PostgreSQL 11+ 加常量默认值的列不重写表,所以都很快(总用时里含约 0.25 s 进程启动)。", t=tl(o(0)['sql'] + o(1)['sql'], cur=[0], mark=[1]), kv=KV([['常量默认值', '快,但 Django 会 DROP DEFAULT']], ['常量默认值'])),
    step(f"可调用默认值(UUIDField, default=uuid.uuid4)只被计算一次:SQL 里是同一个字面量 DEFAULT '85f4…'::uuid,200 万行里不同的 uuid 只有 {R['uuid_distinct']} 个——所有已有行拿到同一个值。想让每行不同,要用 null=True + 迁移里回填。", t=tl(o(2)['sql'] + [f"200 万行里不同的 uuid 数: {R['uuid_distinct']}"], mark=[0, 2]), kv=KV([['callable default', '整张表同一个值']], ['callable default'])),
    step(f"db_default=5(Django 5.0 起):SQL 是 ADD COLUMN … DEFAULT 5 NOT NULL,没有 DROP DEFAULT——数据库层面的默认值被保留(information_schema 里 column_default = {R['dbdef_kept']}),耗时 {o(3)['secs']:.2f} s。", t=tl(o(3)['sql'] + [f"之后表上该列默认值 = {R['dbdef_kept']}"], cur=[0]), kv=KV([['db_default', '保留在数据库里']], ['db_default'])),
    step(f"volatile 函数做默认值:db_default=Random() → DEFAULT (RANDOM()) NOT NULL,耗时 {o(4)['secs']:.2f} s(约为常量默认值的 {o(4)['secs'] / o(0)['secs']:.0f} 倍),因为 PostgreSQL 必须为每一行求值、重写整张表;每行的值不同。", b=bars([['常量默认值(s)', o(0)['secs'], f"{o(0)['secs']:.2f}"], ['volatile 函数默认值(s)', o(4)['secs'], f"{o(4)['secs']:.2f}"]], o(4)['secs'] * 1.1, mark=[1], done=[0]), kv=KV([['volatile 默认值', '重写整张表,持锁']], ['volatile 默认值'])),
    step(f"分三步的安全做法:①AddField(null=True) {o(5)['secs']:.2f} s;②分 20 批(每批 10 万行,各自提交)回填 {R['backfill']:.2f} s;③AlterField 改成 NOT NULL {R['notnull']:.2f} s。每一步要么很快,要么可以分批中断——不会一次长时间持有表锁(第 59 篇量过第③步这类操作会阻塞写入)。", b=bars([['①加 null 列(s)', o(5)['secs'], f"{o(5)['secs']:.2f}"], ['②分批回填(s)', R['backfill'], f"{R['backfill']:.2f}"], ['③改 NOT NULL(s)', R['notnull'], f"{R['notnull']:.2f}"]], R['backfill'] * 1.1, done=[0, 2], mark=[1]), kv=KV([['三步法', '加 null 列 → 分批回填 → 改 NOT NULL']], ['三步法'])),
]
A = dict(
    n=60, series='django', tags='Django,Migration,默认值,大表,PostgreSQL,真实验证,动画演示',
    desc=f'200 万行 PostgreSQL 表上给字段加默认值:常量默认值 {o(0)["secs"]:.2f} s 且 Django 会 DROP DEFAULT;callable default(uuid4)整表拿到同一个值({R["uuid_distinct"]} 个不同值);db_default 保留数据库默认值;volatile 函数默认值 {o(4)["secs"]:.2f} s(重写整表);null → 分批回填 → NOT NULL 的三步法。',
    lead='「加一个带默认值的字段」会不会锁表?这取决于默认值是什么。这篇在 200 万行的表上,把常量、可调用、db_default、volatile 函数四种默认值各加一遍,看 Django 发出的 SQL 和耗时,再演示分三步的安全做法。',
    facts=[(f'{o(0)["secs"]:.2f} vs {o(4)["secs"]:.2f} s', '常量默认值 vs volatile 函数默认值(RANDOM())加列的用时'), (f'{R["uuid_distinct"]} 个', 'default=uuid.uuid4 加列后,200 万行里不同 uuid 的个数(callable 默认值只算一次)'), ('DROP DEFAULT', 'Django 加带 default 的列后会把数据库默认值去掉;db_default 才保留')],
    body=[
        sec('各种默认值的 SQL 与耗时', '', term('', blk('d60', 1)), '<p>PostgreSQL 11 起,加一个带「常量」默认值的列不再重写表(默认值存在目录里,读到旧行时补上)。所以前两个都是毫秒到亚秒级。本机总用时里约 0.25 s 是 Django 命令自身的启动。</p>'),
        sec('分三步的安全做法', '', term('', blk('d60', 2)), '<p>对确实要「每行不同」或者「基于其它列计算」的新列:先加一个可空的列(快)、分批回填(每批一个事务,可以随时中断)、最后再加 NOT NULL(会扫全表一次,见第 59 篇)。批的大小要根据写入负载调。</p>'),
        sec('分步演示:默认值与锁', '', demo('字段默认值', [('t', 'term', 'SQL'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9435,fsync 关闭),200 万行;每项测一次;没有并发写入(锁的阻塞见第 59 篇)', '没有验证:MySQL / SQLite 的行为、PostgreSQL 10 及更老版本(加带默认值的列会重写整表)、加 NOT NULL 前用 CHECK (… IS NOT NULL) NOT VALID 的两步法、分批回填期间的复制延迟'],
)

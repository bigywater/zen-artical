from lib import *
txt = out('73').splitlines()
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())

def kvs(items, hl): return {'items': items, 'hl': hl}
F = lambda cur, done=(): {'nodes': [['写连接 W', ''], ['读连接 R', ''], ['第二个写连接 W2', '']], 'cur': list(cur), 'done': list(done), 'noarrow': True}
steps = [
    step("W 执行 SELECT:仍然没有开启事务(in_transaction = False)。", flow=F([0]),
         kv=kvs([['W.in_transaction', 'False'], ['目录文件', 'a.db']], ['W.in_transaction'])),
    step("W 执行 INSERT:模块在这条 DML 之前悄悄发了 BEGIN,in_transaction 变 True,磁盘上出现回滚日志 a.db-journal。", flow=F([0]),
         kv=kvs([['W.in_transaction', 'True'], ['目录文件', 'a.db, a.db-journal']], ['W.in_transaction', '目录文件'])),
    step("W 在事务里数到 1 行;读连接 R 数到 0 行——未提交的数据别人看不到(R 读的是 a.db 里的旧内容)。", flow=F([0, 1]),
         kv=kvs([['W 看到', '1 行'], ['R 看到', '0 行'], ['目录文件', 'a.db, a.db-journal']], ['W 看到', 'R 看到'])),
    step("W2 也想写:OperationalError: database is locked(timeout=0.2 s 内等不到锁)。", flow=F([2]),
         kv=kvs([['W2 结果', 'OperationalError: database is locked'], ['目录文件', 'a.db, a.db-journal']], ['W2 结果'])),
    step("W commit:日志文件被删除;R 再查,看到 1 行。", flow=F([0, 1], [0]),
         kv=kvs([['R 看到', '1 行'], ['目录文件', 'a.db']], ['R 看到', '目录文件'])),
    step("换个场景:R 有一个没读完的查询,W 有一条待提交的 INSERT。DELETE 日志模式下 W.commit() → database is locked。", flow=F([0, 1]),
         kv=kvs([['journal_mode', 'delete'], ['W.commit()', 'database is locked'], ['目录文件', 'b.db, b.db-journal']], ['W.commit()'])),
    step("同一个场景改成 WAL:W.commit() 成功,目录里多出 b.db-wal 和 b.db-shm。", flow=F([0], [1]),
         kv=kvs([['journal_mode', 'wal'], ['W.commit()', '成功'], ['目录文件', 'b.db, b.db-wal, b.db-shm']], ['W.commit()'])),
]
bench = [l.strip() for l in block('== 五', 'zzzz').splitlines()]
def num(line): return float(line.split('每行')[1].split('µs')[0])
per = [num(l) for l in bench]

A = dict(
    n=73,
    tags='Python,标准库,数据库,SQLite,真实验证,动画演示',
    desc='本机真实验证 sqlite3 模块的隐式事务(INSERT 才 BEGIN,SELECT 和 DDL 不会)、未提交数据对其他连接不可见、第二个写连接得到 database is locked;读游标未读完会让默认日志模式下的 commit 失败而 WAL 模式不会;逐条 commit 每行 266 µs,放进一个事务每行 0.8 µs。',
    lead='<code>sqlite3</code> 一行 <code>connect</code> 就能用,但事务是它最容易踩坑的部分:什么时候开始、别人看得到什么、谁会被锁住。这篇用同一个数据库文件上的多个连接把每种情形真跑一遍,并且直接看磁盘上出现了什么文件。',
    facts=[('INSERT 才 BEGIN', 'SELECT 与 DDL 之后 in_transaction 仍是 False'), ('database is locked', '第二个写连接 / 有未读完查询时 DELETE 模式的 commit'), ('266 → 0.8 µs', '每行插入成本:每条 commit vs 全放一个事务(synchronous=full)')],
    body=[
        sec('做的事:同一个文件,多个连接', 'W 写、R 读、W2 抢着写,同时看 <code>in_transaction</code> 和目录里的文件',
            src('实验脚本(节选)', '''w = sqlite3.connect(path, timeout=0.2)
r = sqlite3.connect(path, timeout=0.2)
w.execute("insert into t(v) values ('uncommitted')")   # 没有 commit
r.execute("select count(*) from t")                    # 另一个连接读
os.listdir(dirname)                                    # 看磁盘上多了什么'''),
            term('', txt[0])),
        sec('验证一:到底什么时候 BEGIN', '默认模式下的隐式事务',
            term('', block('== 一', '== 二')),
            '<p>连接建立、<code>SELECT</code> 之后都不在事务里;第一条 <code>INSERT</code> 之后 <code>in_transaction</code> 变成 True——模块在 DML 语句前自动补了一个 <code>BEGIN</code>。<code>rollback()</code> 之后表里 0 行,刚才的插入没有留下。最后一行说明:<b>DDL(<code>create table</code>)不会开启事务</b>,它立即生效,不受之后 <code>rollback()</code> 影响(本机 3.14 实测)。</p>'),
        sec('验证二:未提交的数据别人看不到,第二个写连接被挡在门外', '还能在磁盘上看到回滚日志',
            term('', block('== 二', '== 三')),
            '<p>写连接自己数到 1 行,读连接是 0 行;此时目录里多出 <code>a.db-journal</code>——这是 SQLite 默认的回滚日志(journal_mode=delete):旧页面先备份到日志里,提交后日志删除。第二个写连接想插入,等了 0.2 秒就得到 <code>OperationalError: database is locked</code>。commit 之后日志文件消失,读连接看到 1 行。</p>',
            term('', out('73b')),
            callout('<code>timeout</code> 参数就是「等锁的最长秒数」——不指定时实测等了 5.21 秒才报错。看到 <code>database is locked</code> 时,几乎总是有另一个连接的事务没结束——先找谁没 commit 或没关游标,再考虑调大 timeout。', True)),
        sec('验证三:with conn 管提交和回滚,不管关闭', '',
            term('', block('== 三', '== 四')),
            '<p>with 块正常结束会 commit,抛异常会 rollback——上面第二次块里插入的 <code>will roll back</code> 确实没留下(行数仍是 2)。但连接<b>没有被关闭</b>:出块后还能继续查询。真的要释放文件句柄得自己 <code>conn.close()</code>(或用 <code>contextlib.closing</code>)。</p>'),
        sec('验证四:一个没读完的查询,能让写方 commit 失败', 'DELETE 日志 与 WAL 的差别',
            term('', block('== 四', '== 五')),
            '<p>读连接执行了 <code>select</code> 只取了一行,游标还开着,占着共享锁;写连接想 commit,DELETE 日志模式下要独占数据库文件,等不到就 <code>database is locked</code>。同样的场景切到 <code>journal_mode=wal</code> 就成功了,目录里出现 <code>-wal</code>、<code>-shm</code> 两个文件:写入先追加到 WAL 文件,读方仍然读旧快照,互不阻塞。所以「读的地方忘记 fetchall / 关游标」在默认模式下会以「写失败」的形式表现出来。WAL 也不是没有代价——它需要 <code>-shm</code> 共享内存文件,不适合放在网络文件系统上;这条我没有验证,请以官方文档为准。</p>'),
        sec('验证五:commit 次数决定成本', 'synchronous=full 时每次 commit 都要等落盘',
            term('', '\n'.join(bench)),
            f'<p>每条语句单独 commit,每行要 {per[0]:.0f} µs;放进一个事务提交,每行只要 {per[2]:.1f} µs,差了约 {per[0]/per[2]:.0f} 倍。把 <code>synchronous</code> 设成 off 只把逐条 commit 降到 {per[1]:.0f} µs,说明代价不全在 fsync,创建/删除日志文件等开销也很显著。注意这里逐条提交只跑了 1000 行、单事务跑了 10000 行,表里用的是每行摊销值,不同数据量下绝对值会变。</p>'),
        sec('分步演示:两个连接在同一个文件上', '每一步的结果都是上面实验的原始输出',
            demo('事务、锁和日志文件',
                 [('flow', 'flow', '哪个连接在动'), ('kv', 'kv', '此刻的结果')],
                 steps, '这一步被高亮的连接 / 结果')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,SQLite 3.53.4,标准库 <code>sqlite3</code>(<code>autocommit</code> 保持默认的 LEGACY_TRANSACTION_CONTROL)',
          '只测了单机文件数据库;没有验证 isolation_level 的其他取值、<code>BEGIN IMMEDIATE</code>、多线程共享连接(check_same_thread),也没有评估 WAL 的代价与适用场景'],
)

from lib import *
R = J('d47')
nr = R['nr']; lu = R['lu']; ks = list(nr)
def short(s): return s.split('→')[-1].strip()
steps = [
    step(f"Django 自己不改隔离级别,PostgreSQL 上默认是 {R['default']}(READ COMMITTED)。同一个事务里两次读同一行,中间别人提交了修改:第一次 100、第二次 200——不可重复读。", t=tl([nr[ks[0]]], mark=[0]), kv=KV([['默认', R['default']], ['同事务两次读', '100 → 200']], ['同事务两次读'])),
    step("READ COMMITTED 下,事务开始后别人先改了这一行,自己再 update(F('bal') + 1):提交成功,最终 201——update 基于最新的已提交值,不会失败,也不会丢别人的修改。", t=tl([lu[ks[0]]], done=[0]), kv=KV([['更新冲突', '基于最新值,成功']], ['更新冲突'])),
    step("REPEATABLE READ(在 DATABASES 的 OPTIONS 里设置 isolation_level):同一个事务里两次读同一行都是 100——看到的是同一个快照。但此时更新一行、而别人在事务开始后已改过它 → OperationalError: could not serialize access due to concurrent update,需要应用重试。", t=tl([nr[ks[1]], '更新:' + lu[ks[1]]], cur=[0], mark=[1]), kv=KV([['读', '快照,可重复'], ['并发更新', '序列化失败,要重试']], ['并发更新'])),
    step("SERIALIZABLE 下的这两个实验结果与 REPEATABLE READ 相同(读到 100;更新同样序列化失败)。这次只测了「读一行、更新同一行」,不足以体现 SERIALIZABLE 与 REPEATABLE READ 的区别(比如写偏斜),没有验证。", t=tl([nr[ks[2]], '更新:' + lu[ks[2]]], cur=[0], mark=[1]), kv=KV([['SERIALIZABLE', '本实验里与 RR 表现相同']], ['SERIALIZABLE'])),
]
A = dict(
    n=47, series='django', tags='Django,事务,隔离级别,PostgreSQL,真实验证,动画演示',
    desc='在 PostgreSQL 上实测三种隔离级别下的 Django 行为:默认 READ COMMITTED 会不可重复读(100 → 200);REPEATABLE READ 读到同一快照,但并发更新同一行会 OperationalError: could not serialize access due to concurrent update,需要应用重试。',
    lead='Django 没有自己的隔离级别,用的是数据库默认。但默认是什么?换成 REPEATABLE READ 之后,代码要改什么?这篇在 PostgreSQL 上用两个线程构造「事务里别人改了同一行」,看每个级别下读与写的结果。',
    facts=[('read committed', 'PostgreSQL 的默认隔离级别(SHOW transaction_isolation)'), ('100 → 200', 'READ COMMITTED:同一事务两次读同一行,读到别人提交的修改'), ('serialize', 'REPEATABLE READ:并发更新同一行 → could not serialize access,应用要捕获并重试')],
    body=[
        sec('默认:READ COMMITTED', '', term('', blk('d47', 1)), '<p>没有设置任何选项时的行为。</p>'),
        sec('更严格的级别', '', '<p>在 <code>DATABASES[\'default\'][\'OPTIONS\']</code> 里设置 <code>isolation_level</code>(psycopg 3 的 <code>IsolationLevel</code>)。上一节的对照见演示。更严格的级别把「读到旧值」变成了「写的时候失败」——好处是不会悄悄基于旧值提交,代价是必须写重试逻辑。</p>'),
        sec('分步演示:三个级别', '', demo('隔离级别', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9423);每个级别各用一个全新的 Django 进程;别人的修改由另一个线程的独立连接完成', '没有验证:MySQL(默认 REPEATABLE READ,语义不同)、幻读与写偏斜的复现、SERIALIZABLE 下的 SerializationFailure 重试模式、间隙锁'],
)

from lib import *
R = J('d118')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
b = L('bench')
steps = [
    step("10 个线程各对同一行计数器 +1 共 200 次,期望 2000。PostgreSQL,默认隔离级别 read committed。先看最常见的写法:c = get(pk=1); c.n += 1; c.save()——最终 n = 347,丢了 1653 次。", t=tl(b[:1]), mark=[0], b=bars([['期望', 2000, '2000'], ['get → n += 1 → save()', 347, '347']], 2000, mark=[1]), kv=KV([['丢失', '1653 / 2000']], ['丢失'])),
    step("外面再包一个 atomic() 也没用:最终 n = 250,丢了 1750。事务保证原子提交,不保证「读到的值还是最新的」。", t=tl(b[1:2]), mark=[0], b=bars([['期望', 2000, '2000'], ['get → save()', 347, '347'], ['+ atomic()', 250, '250']], 2000, mark=[1, 2]), kv=KV([['atomic()', '不能防止丢失更新']], ['atomic()'])),
    step("filter(pk=1).update(n=F('n') + 1):最终 2000,0 丢失,用时 414 ms(最快)——在数据库里做 n = n + 1,读与写是同一条语句。", t=tl(b[2:3]), done=[0], b=bars([['update(F)', 2000, '2000 · 414 ms']], 2000, done=[0]), kv=KV([['F() + update()', '正确、最快']], ['F() + update()'])),
    step("atomic + select_for_update().get → +1 → save:最终 2000,0 丢失,810 ms(先锁行再读再写,串行化);get → c.n = F('n') + 1 → save():最终 2000,0 丢失,850 ms。", t=tl(b[3:]), done=[0, 1], b=bars([['update(F)', 414, '414 ms'], ['select_for_update', 810, '810 ms'], ['save() + F()', 850, '850 ms']], 900, done=[0, 1, 2]), kv=KV([['三种正确写法', '414 / 810 / 850 ms']], ['三种正确写法'])),
    step("F() 赋给实例后 save():在 PostgreSQL、Django 6.1.1 上,save() 之后 c.n 的类型是 int(不是表达式对象),库里是 6,refresh_from_db() 之后仍是 6。(其它数据库与旧版本没有测,旧文档说要 refresh_from_db 才能得到数值。)", t=tl(L('f')), kv=KV([['F 赋值后 save()', 'c.n 已是 int(本环境)']], ['F 赋值后 save()'])),
]
A = dict(
    n=118, series='django', tags='Django,并发,F表达式,select_for_update,PostgreSQL,真实验证,动画演示',
    desc='10 个线程各 +1 共 200 次(期望 2000):get → n += 1 → save() 只剩 347、外面包 atomic 只剩 250;F() 表达式 update、select_for_update、save() 配 F() 都精确得到 2000(414 / 810 / 850 ms)。',
    lead='「读出来加一再存回去」是最经典的并发 bug。这篇在 PostgreSQL 上用 10 个线程做真正的并发计数,量出丢了多少,再对比几种正确写法的结果和耗时。',
    facts=[('347 / 2000', 'get → n += 1 → save() 的最终值,丢失 1653 次'), ('250 / 2000', '外面包 atomic() 后的最终值——事务本身不解决丢失更新'), ('2000 / 2000', 'F() + update()、select_for_update、save() + F() 三种写法')],
    body=[
        sec('五种写法的结果', '', term('', blk('d118', 1)), '<p>丢失更新的原因:两个线程各自读到同一个旧值 n,各自加一再写回,后写的覆盖先写的。<code>atomic()</code> 只保证「一组语句要么都提交要么都回滚」,PostgreSQL 的默认隔离级别 read committed 下并不会让另一个事务等你。<code>F()</code> 把计算放到数据库里做,<code>select_for_update()</code> 先把行锁住再读。</p>'),
        sec('F() 赋给实例之后', '', term('', blk('d118', 2)), '<p>这一段的结果只在本环境(PostgreSQL、Django 6.1.1)观察到:<code>save()</code> 之后内存里的值已经是整数。别的后端不一定同样,稳妥的做法还是 <code>refresh_from_db()</code>。</p>'),
        sec('耗时的解读', '', '<p>单条 <code>update(F)</code> 最快(414 ms),因为只需要一次往返;<code>select_for_update</code> 与 <code>save()</code> + <code>F()</code> 都要至少两次往返(810 / 850 ms)。这些数字来自 fsync=off 的本机临时 PostgreSQL,线程数与次数都很小,只用来比较相对关系。</p>'),
        sec('分步演示', '', demo('并发计数', [('t', 'term', '输出'), ('b', 'bars', '最终值 / 耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。自己起的临时 PostgreSQL 16(fsync=off、synchronous_commit=off);10 线程 × 200 次;每种写法只跑了一次,丢失的具体数字每次会不同', '没有验证:repeatable read / serializable 隔离级别下的表现、MySQL、SQLite 的行为、批量 bulk_update 的并发、乐观锁(版本号)写法、更多线程时的耗时'],
)

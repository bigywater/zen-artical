from lib import *
import re
R = J('d31')
rc = [l for l in R['race'].splitlines() if '最终' in l]
def num(l, k): return int(re.search(k + r'\s*=?\s*(\d+)', l).group(1))
lost = [int(re.search(r'丢失\s*(\d+)', l).group(1)) for l in rc]; final = [int(re.search(r'最终 n =\s*(\d+)', l).group(1)) for l in rc]
rounds = re.findall(r'\d+', R['rounds'].split(':')[1])
steps = [
    step("读-改-写:c.n = c.n + 1; c.save() 的 SQL 是 UPDATE … SET name = 'c', n = 1(把整行、算好的具体数值写回去);update(n=F('n') + 1) 的 SQL 是 SET n = (n + 1)——加法在数据库里做。", t=tl([l for l in R['sql'].splitlines() if l.strip()][:5], cur=[1], mark=[3]), kv=KV([['读-改-写', 'Python 里算,写回具体值'], ['F()', '数据库里算']], ['F()'])),
    step(f"8 个线程 × 每个 200 次 +1,PostgreSQL(READ COMMITTED),期望 1600:读-改-写最终 n = {final[0]},丢失 {lost[0]} 次更新;update(n=F('n') + 1) 最终 n = {final[1]},丢失 {lost[1]} 次。", b=bars([['读-改-写 最终值', final[0], str(final[0])], ['F() 最终值', final[1], str(final[1])], ['期望值', 1600, '1600']], 1700, mark=[0], done=[1, 2]), kv=KV([['丢失更新', f"{lost[0]} vs {lost[1]}"]], ['丢失更新'])),
    step(f"重复 5 轮,读-改-写每轮丢失的次数:{'、'.join(rounds)}——不是偶然,是稳定的大量丢失(每个线程读到的是旧值,再写回去覆盖别人的更新)。", b=bars([[f'第 {i+1} 轮丢失', int(x), x] for i, x in enumerate(rounds)], 1600, mark=list(range(len(rounds)))), kv=KV([['结论', '并发计数不能在 Python 里读-改-写']], ['结论'])),
    step("F() 的边界:update() 返回受影响行数(存在 1,不存在 0);F 可以组合运算(n = n*2 + n);对象上 c.n = F('n') + 1; c.save() 在 PostgreSQL 上生成 UPDATE … RETURNING n,save 之后 c.n 已经是 int(本次 PostgreSQL 实测)。", t=tl(R['misc'].splitlines() + [R['sql'].splitlines()[-1]], cur=[0, 1, 3], mark=[4]), kv=KV([['update()', '返回行数'], ['F 组合', '在数据库里完成']], ['update()'])),
]
A = dict(
    n=31, series='django', tags='Django,ORM,F表达式,并发,PostgreSQL,真实验证,动画演示',
    desc=f'在 PostgreSQL 上用 8 个线程各加 200 次计数:读-改-写最终 {final[0]}(丢失 {lost[0]} 次,5 轮都丢约 1260 次),update(n=F("n") + 1) 精确得到 1600;并对比两种写法的 SQL。',
    lead='F() 表达式被说成「并发安全的计数」。到底安全在哪?不用它会丢多少?这篇在真实的 PostgreSQL 上用 8 个线程同时加 1600 次,把丢失的更新数出来。',
    facts=[(f'{final[0]} / 1600', '读-改-写:8 线程 × 200 次 +1 的最终值(PostgreSQL)'), (f'{final[1]} / 1600', 'update(n=F("n") + 1) 的最终值'), ('RETURNING', '对象上 c.n = F("n") + 1; c.save() 在 PostgreSQL 上用 RETURNING 取回新值')],
    body=[
        sec('两种写法,两种 SQL', '', term('', blk('d31', 1)), '<p>F() 的本质是把「加一」写进 SQL 里由数据库执行,而不是先读出值再写回具体数值。数据库在执行 <code>UPDATE … SET n = n + 1</code> 时对这行加锁,并发的更新会排队,每次都基于最新值。</p>'),
        sec('8 个线程实测', '', term('', blk('d31', 2)), '<p>用 <code>threading.Barrier</code> 让 8 个线程同时起跑。读-改-写丢了绝大多数更新——每个线程读到旧值,各自写回,互相覆盖。</p>'),
        sec('每轮都丢', '', term('', blk('d31', 3)), '<p>丢失数量在 5 轮里几乎一样,不是偶发。(丢失的具体数字和机器速度、线程数有关,别当作通用值。)</p>'),
        sec('F() 的边界', '', term('', blk('d31', 4)), '<p><code>update()</code> 返回的是受影响行数,不是新值。想要新值:PostgreSQL 上对象 <code>save()</code> 用了 <code>RETURNING</code>(本次实测),其它数据库没有测;通用做法是 <code>refresh_from_db()</code>。F() 只解决「在数据库里做运算」,不解决「基于旧值做判断」(比如「库存够才扣」需要 <code>select_for_update</code> 或带条件的 <code>update</code>,见第 46 篇)。</p>'),
        sec('分步演示:丢失的更新', '', demo('F() 并发计数', [('t', 'term', 'SQL'), ('b', 'bars', '最终值'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9401,fsync 关闭),默认 READ COMMITTED,8 个线程各自独立连接', '没有验证:SQLite / MySQL 上的表现、REPEATABLE READ / SERIALIZABLE 隔离级别下的行为、线程数与迭代数改变时丢失比例的变化、F() 与 select_for_update 组合、save() 的 RETURNING 在其它数据库上的行为'],
)

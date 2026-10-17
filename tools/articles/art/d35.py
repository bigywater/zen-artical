from lib import *
R = J('d35')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("get_or_create 的 SQL:先 SELECT … LIMIT 21;没找到,则 BEGIN → INSERT … RETURNING id → COMMIT(在一个保存点/事务里);已存在时只有一条 SELECT,defaults 不生效。", t=tl(L('sql'), cur=[1, 3, 4], mark=[2, 5]), kv=KV([['存在', '1 条 SELECT'], ['不存在', 'SELECT + INSERT']], ['不存在'])),
    step("8 个线程同时 get_or_create 同一个名字,重复 20 轮。name 有 unique=True:每轮恰好 1 个线程创建成功、表里该名字 1 行,没有任何线程抛异常——INSERT 撞上唯一约束时 Django 捕获 IntegrityError 再 get 一次。", t=tl([L('race')[0]], cur=[0]), kv=KV([['有唯一约束', '每轮 1 行,无异常']], ['有唯一约束'])),
    step("name 没有唯一约束:20 轮里 20 轮出现重复行(同一个名字被创建了 2~6 次,例如 6 个线程都返回 created=True),还有线程抛 MultipleObjectsReturned。", t=tl(L('race')[1:3], cur=[0], mark=[1]), kv=KV([['没有唯一约束', '20/20 轮出现重复行']], ['没有唯一约束'])),
    step("重复行的后遗症:表里已有两行 name='dup',之后 get_or_create(name='dup') 就抛 MultipleObjectsReturned: get() returned more than one PTag -- it returned 2!。竞态创造的脏数据会让原本正常的调用永久失败。", t=tl(L('multi'), mark=[0]), kv=KV([['之后', '每次 get_or_create 都失败']], ['之后'])),
    step("update_or_create 同理:第一次 created=True,第二次 created=False 且值更新为 2;get_or_create 在已存在时 defaults 不生效。8 线程同时 update_or_create 同一个键,有唯一约束时行数 = 1、无异常。", t=tl(L('upd'), cur=[0, 1], mark=[2], done=[3]), kv=KV([['唯一约束', 'get_or_create / update_or_create 并发安全的前提']], ['唯一约束'])),
]
A = dict(
    n=35, series='django', tags='Django,ORM,get_or_create,并发,PostgreSQL,真实验证,动画演示',
    desc='在 PostgreSQL 上用 8 个线程并发 get_or_create:有唯一约束时每轮恰好 1 行、无异常;没有唯一约束时 20 轮全部出现重复行,之后 get_or_create 永久抛 MultipleObjectsReturned;update_or_create 同样依赖唯一约束。',
    lead='get_or_create 常被当作「并发安全的幂等创建」。它真的安全吗?这篇在 PostgreSQL 上让 8 个线程同时抢同一个名字,分别在有和没有唯一约束的表上重复 20 轮。',
    facts=[('有 vs 没有', '有唯一约束:20 轮每轮 1 行;没有:20/20 轮出现重复行'), ('MultipleObjectsReturned', '重复行一旦产生,之后的 get_or_create 永久失败'), ('前提', 'get_or_create / update_or_create 的并发安全依赖数据库层面的唯一约束')],
    body=[
        sec('它做了什么', '', term('', blk('d35', 1)), '<p>典型的「先查后写」:先 <code>SELECT</code>,没有再 <code>INSERT</code>。两个线程都没查到,就会都去 <code>INSERT</code>——能不能拦住,只靠数据库的唯一约束。</p>'),
        sec('并发实验', '', term('', blk('d35', 2)), '<p>用 <code>Barrier</code> 让 8 个线程同时起跑。有唯一约束时,后到的 <code>INSERT</code> 触发 <code>IntegrityError</code>,Django 内部捕获并重新查一次,所以调用方看到的仍是「一个创建、其余获取」。没有约束时,Django 无能为力。</p>'),
        sec('重复行的后果', '', term('', blk('d35', 3)), '<p>一次并发竞态造成的脏数据,会让以后所有同名的 <code>get_or_create</code> 抛 <code>MultipleObjectsReturned</code>。要修,得先清理重复行,再加唯一约束。</p>'),
        sec('update_or_create', '', term('', blk('d35', 4)), '<p>规则相同。另外注意 <code>get_or_create</code> 在对象已存在时 <code>defaults</code> 不生效——要「存在就更新」用 <code>update_or_create</code>。</p>'),
        sec('分步演示:竞态与唯一约束', '', demo('get_or_create 并发', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9402),READ COMMITTED,8 线程 × 20 轮', '没有验证:MySQL / SQLite 下的行为、REPEATABLE READ 或 SERIALIZABLE、多列联合唯一约束、在外层事务(atomic)里使用 get_or_create 时的保存点行为(第 44 篇)、get_or_create 内部的 SELECT 之后另一个事务回滚的时序'],
)

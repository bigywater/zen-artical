from lib import *
R = J('d50')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("makemigrations 为三个 app 各生成 0001_initial:people.0001 的 dependencies 是空的;orders.0001 依赖 ('people', '0001_initial')(因为 Order 有指向 Person 的外键);billing.0001 依赖 ('orders', '0001_initial')(OneToOne 指向 Order)。跨 app 的外键决定了迁移之间的依赖。", t=tl(L('make') + ['people.0001 dependencies = ' + R['deps']['people'], 'orders.0001 dependencies = ' + R['deps']['orders'], 'billing.0001 dependencies = ' + R['deps']['billing']], mark=[9, 10, 11]), kv=KV([['外键', '产生跨 app 依赖']], ['外键'])),
    step("再改模型(给 Person 加 email)后 makemigrations people 生成 0002_person_email,dependencies = " + R['dep2'] + "——同一个 app 里,后一个迁移依赖前一个。", t=tl(['0002_person_email dependencies = ' + R['dep2']]), kv=KV([['同 app', '后一个依赖前一个']], ['同 app'])),
    step("showmigrations --plan 是整张图拓扑排序后的执行计划:people.0001 → orders.0001 → billing.0001 → contenttypes 两个 → people.0002(people.0002 排在最后——依赖满足的前提下,顺序由图遍历决定,不是按 app 或按编号排好的)。", t=tl(L('plan'), cur=[0, 1, 2], mark=[5]), kv=KV([['计划', '拓扑排序,不是按 app 分组']], ['计划'])),
    step("django_migrations 表只记录「哪些迁移已应用」:(1, people, 0001_initial)、(2, orders, 0001_initial)——没有图、没有依赖。showmigrations 里 orders.0001、people.0001 是 [X],people.0002、billing.0001 是 [ ]。", t=tl(L('table')[1:3] + [l for l in L('show')]), kv=KV([['django_migrations', '只存应用记录']], ['django_migrations'])),
    step("图对象(MigrationLoader):共 6 个节点;叶子节点每个 app 一个(各 app 的最新迁移);billing.0001 的直接依赖是 orders.0001,它的前向计划是 people.0001 → orders.0001 → billing.0001。已应用的是 orders.0001、people.0001。", t=tl(L('graph'), cur=[0, 1, 2, 3, 4]), kv=KV([['forwards_plan', '需要先执行的所有迁移']], ['forwards_plan'])),
    step("循环依赖:把 people.0001 改成依赖 billing.0001 后,任何迁移命令都报 CircularDependencyError: orders.0001_initial, billing.0001_initial, people.0001_initial。图必须是有向无环图。", t=tl([R['circular']]), kv=KV([['循环', 'CircularDependencyError']], ['循环'])),
]
A = dict(
    n=50, series='django', tags='Django,Migration,依赖图,真实验证,动画演示',
    desc='三个 app(people ← orders ← billing)实测迁移文件与依赖图:外键决定跨 app 依赖、同 app 后一个依赖前一个;showmigrations --plan 是拓扑排序后的计划;django_migrations 只记录已应用的迁移;MigrationLoader 的节点与叶子;循环依赖抛 CircularDependencyError。',
    lead='migrations 目录里的一堆 0001、0002 文件,Django 是怎么把它们串成执行顺序的?django_migrations 表里存了什么?这篇用三个互相依赖的 app,把迁移文件、依赖、执行计划和已应用记录一层层摊开。',
    facts=[('外键 → 依赖', 'orders.0001 依赖 people.0001,billing.0001 依赖 orders.0001;同 app 的 0002 依赖 0001'), ('图不入库', 'django_migrations 表只存已应用的迁移名,依赖图每次从文件里重新构建'), ('无环', '循环依赖抛 CircularDependencyError')],
    body=[
        sec('迁移文件与依赖', '', term('', blk('d50', 1)), term('', blk('d50', 2)), '<p>依赖写在每个迁移的 <code>dependencies</code> 里,由 <code>makemigrations</code> 根据外键自动生成。你也可以手工添加(比如「必须在另一个 app 的某个数据迁移之后」)。</p>'),
        sec('执行计划', '', term('', blk('d50', 3)), '<p><code>migrate</code> 按依赖图的拓扑排序执行。排序只保证依赖先于被依赖者,其余顺序不要依赖。</p>'),
        sec('已应用记录', '', term('', blk('d50', 4)), '<p><code>django_migrations</code> 只是「已应用清单」。所以手工改这张表(或 <code>--fake</code>,第 56 篇)就能让 Django 认为某个迁移已经执行过。</p>'),
        sec('图对象', '', term('', blk('d50', 5)), '<p><code>MigrationLoader(connection).graph</code> 是 <code>makemigrations</code> 与 <code>migrate</code> 共用的数据结构:节点是 (app, name),边是依赖。叶子节点用来判断「每个 app 的最新迁移」,多个叶子节点就是迁移冲突(第 57 篇)。</p>'),
        sec('循环依赖', '', term('', blk('d50', 6)), '<p>互相引用的 app 要靠拆分迁移(先建表、后加外键)打破循环;本文没有演示怎么拆。</p>'),
        sec('分步演示:迁移依赖图', '', demo('迁移文件与依赖图', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;三个 app 没有预先存在的 migrations 目录,由 makemigrations 生成', '没有验证:squashed migrations 在图里的替换(第 58 篇)、run_before、swappable_dependency(AUTH_USER_MODEL)、迁移里的 atomic 属性、跨数据库迁移(router)'],
)

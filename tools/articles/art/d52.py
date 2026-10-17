from lib import *
R = J('d52')
def L(lst): return [l for l in lst]
steps = [
    step("三个 app:a 有 0001、0002;b 依赖 a.0001;c 有 0001、0002。全新数据库 migrate --plan 的顺序:a.0001 → a.0002 → b.0001 → c.0001 → c.0002 → contenttypes … 依赖关系只规定「a.0001 先于 b.0001」,其余顺序是图遍历的结果。", t=tl([l for l in R['plan_all'][1:11]], cur=[0, 2, 4], done=[6, 8]), kv=KV([['顺序', '依赖 + 图遍历']], ['顺序'])),
    step("只迁移某个 app:migrate b --plan 只有 a.0001 和 b.0001——先做它依赖的,不多做别的(a.0002 不在计划里);migrate a 0001 --plan 只有 a.0001。", t=tl(R['plan_b'] + R['plan_a1']), kv=KV([['migrate <app>', '只补齐依赖']], ['migrate <app>'])),
    step("真的执行后 django_migrations 里的记录是:" + '、'.join(x.split(',')[0].strip("() ").replace("'", '') + '.' + x.split(',')[1].strip("() ").replace("'", '') for x in R['applied'].splitlines()) + "。表里只存「应用了哪些」,不存顺序依赖。", t=tl(R['applied'].splitlines()), kv=KV([['django_migrations', '只存已应用记录']], ['django_migrations'])),
    step("回退按反向依赖:migrate a 0001(全部已应用)→ 只撤销 a.0002(Undo Add field z to a);migrate a zero → 先撤销依赖 a 的 b.0001,再 a.0002,最后 a.0001。被依赖的迁移不能在依赖它的迁移之前撤销。", t=tl(R['back'] + ['---'] + R['zero']), kv=KV([['回退', '先撤销依赖者']], ['回退'])),
    step("run_before:给 c.0001 写 run_before = [('a', '0002_a_z')] 后,showmigrations --plan 里 c.0001 排到了 a.0001 / a.0002 之前。它让「别的 app 的迁移」排在自己前面,用来给第三方 app 插入依赖时才需要。", t=tl(R['run_before'], cur=[0]), kv=KV([['run_before', '声明「我必须先于它」']], ['run_before'])),
]
A = dict(
    n=52, series='django', tags='Django,Migration,执行顺序,真实验证,动画演示',
    desc='用三个互相依赖的 app 实测 migrate 的执行顺序:migrate --plan 是依赖 + 图遍历的结果;只迁移某个 app 时只补齐依赖;回退按反向依赖(先撤销依赖者);django_migrations 只存已应用记录;run_before 能让别的 app 的迁移排到自己后面。',
    lead='migrate 是按什么顺序执行迁移的?指定 app 时会多做哪些?回退时谁先撤销?这篇用 --plan 把每种情形的计划直接打出来,再用真实执行验证。',
    facts=[('--plan', 'migrate --plan 打印将要执行的迁移与操作,不真正执行'), ('只补依赖', 'migrate b 只执行 b 依赖的迁移和 b 自己,不多做'), ('反向依赖', '回退 a 到 zero 时,先撤销依赖 a 的 b.0001')],
    body=[
        sec('全新数据库的计划', '', term('', blk('d52', 1)), '<p>计划顺序不是「按 app 分组」也不是「按编号排序」,只保证依赖先于被依赖者。不要依赖计划里没有依赖声明的顺序。</p>'),
        sec('指定 app 与目标', '', term('', blk('d52', 2)), '<p><code>migrate &lt;app&gt; &lt;name&gt;</code> 是「迁移到这个点」:补齐依赖并停在这里;如果目标在当前状态之前,就是回退。</p>'),
        sec('执行记录', '', term('', blk('d52', 3)), '<p>记录的顺序就是实际执行的顺序(id 递增)。</p>'),
        sec('回退', '', term('', blk('d52', 4)), '<p>回退计划同样由图决定:要撤销的迁移的「依赖者」必须先被撤销。</p>'),
        sec('run_before', '', term('', blk('d52', 5)), '<p>本实验里我只验证了 <code>showmigrations --plan</code> 里的顺序变了,没有真正在会因顺序出错的场景里验证。</p>'),
        sec('分步演示:迁移的执行顺序', '', demo('migrate 执行顺序', [('t', 'term', '计划 / 记录'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;三个 app,a / c 各两个迁移,b 依赖 a.0001', '没有验证:swappable_dependency、跨 app 的循环依赖拆分、--plan 在 PostgreSQL 上的输出与 SQLite 是否一致、大量迁移下 migrate 的加载耗时'],
)

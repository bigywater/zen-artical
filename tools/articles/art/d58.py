from lib import *
R = J('d58'); nm = R['names']
steps = [
    step("五个迁移:0001 CreateModel;0002、0003、0005 各 AddField;0004 AlterField。squashmigrations lab 0001 0005 会把它们合并。", t=tl([f"{n}: {R['ops_before'][n]}" for n in nm], cur=[0, 1, 2, 3, 4]), kv=KV([['迁移数', '5'], ['操作', '1 个 CreateModel + 3 个 AddField + 1 个 AlterField']], ['迁移数'])),
    step(f"squashmigrations 输出「Optimized from 5 operations to 1 operations」:优化器把后面对同一个模型的 AddField / AlterField 全部并进 CreateModel。生成的 {R['sq_name']} 里操作是 {R['sq_ops']},并带 replaces = [(lab, 0001…0005)]。它提示:提交新迁移但保留旧的;确认所有实例都应用了旧迁移之后,才能删除旧的。", t=tl([l.strip() for l in R['squash_out'].splitlines() if l.strip()][:9] + [f"生成:{R['sq_name']};操作:{R['sq_ops']}"], mark=[7, 9]), kv=KV([['优化', '5 个操作 → 1 个']], ['优化'])),
    step("新旧迁移文件同时存在时怎么选:全新数据库 → 使用合并后的迁移(计划里只有 lab.0001_initial_squashed_0005_p_c)。已经应用了旧迁移的前三个(0001~0003)时 → 继续用旧迁移,计划是 0004、0005;全部应用后 django_migrations 里还会多出合并迁移自己的记录,再 migrate 无事可做。", t=tl(['全新数据库计划: ' + str(R['fresh']), '应用到 0003 之后记录: ' + R['partial'], '这时计划: ' + str(R['partial_plan']), '全部 migrate 之后记录: ' + R['done']], cur=[0, 2]), kv=KV([['全新库', '走合并迁移'], ['部分应用', '继续走旧迁移']], ['部分应用'])),
    step(f"SQL 数量:五个旧迁移合计 {R['sql']['old']} 条 SQL(SQLite 每次改列都要重建表),合并后的迁移 {R['sql']['squashed']} 条。合并的价值主要是新环境从头迁移更快、更简单。", b=bars([['五个旧迁移(SQL 条数)', R['sql']['old'], str(R['sql']['old'])], ['合并后(SQL 条数)', R['sql']['squashed'], str(R['sql']['squashed'])]], R['sql']['old'] * 1.1, mark=[0], done=[1]), kv=KV([['SQL', f"{R['sql']['old']} → {R['sql']['squashed']} 条"]], ['SQL'])),
]
A = dict(
    n=58, series='django', tags='Django,Migration,squashmigrations,真实验证,动画演示',
    desc=f'实测 squashmigrations:5 个迁移优化成 1 个操作(SQL {R["sql"]["old"]} → {R["sql"]["squashed"]} 条);新旧迁移共存时,全新数据库走合并迁移,部分应用的数据库继续走旧迁移;replaces 声明它替代的迁移。',
    lead='迁移文件积累到几百个,新环境 migrate 很慢。squashmigrations 能压缩它们,但已经部署的库怎么办?这篇把「新旧迁移共存」时的三种状态都验证一遍。',
    facts=[('5 → 1', 'squashmigrations 把 5 个迁移优化成 1 个 CreateModel 操作'), ('replaces', '合并迁移用 replaces 声明它替代哪些迁移'), ('共存', '全新库走合并迁移;已经应用了旧迁移(部分)的库继续走旧迁移')],
    body=[
        sec('原始迁移', '', term('', blk('d58', 1)), '<p>五个迁移,每个操作都很小。</p>'),
        sec('合并', '', term('', blk('d58', 2)), '<p><code>squashmigrations app 0001 0005</code> 生成新文件并保留旧文件。合并迁移里的 <code>replaces</code> 列出被替代的迁移。官方建议的流程:提交合并迁移 → 等所有环境都应用了旧迁移 → 删除旧迁移并把合并迁移的 <code>replaces</code> 去掉(后两步本文没有做)。</p>'),
        sec('新旧共存时选哪套', '', term('', blk('d58', 3)), '<p>规则(实测):如果 <code>replaces</code> 里的迁移在数据库里<b>要么全部应用要么全部没应用</b>,就用合并迁移;部分应用则用旧迁移,直到全部应用后 Django 会补一条合并迁移自己的记录。</p>'),
        sec('收益', '', term('', blk('d58', 4)), '<p>SQL 条数是 SQLite 上的(它对每次改列都重建表),PostgreSQL 上收益要小一些。</p>'),
        sec('分步演示:压缩迁移', '', demo('squashmigrations', [('t', 'term', '输出'), ('b', 'bars', 'SQL 条数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:合并迁移里包含 RunPython 时的处理(优化器不会跨越 RunPython)、跨 app 依赖的压缩、删除旧迁移后的行为、替换关系里「部分应用」的其它变体'],
)

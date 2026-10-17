from lib import *
R = J('d55'); a = R['atomic']; n = R['nonatomic']
steps = [
    step(f"迁移里两条操作:第一条 ADD COLUMN c1 成功,第二条是一条非法 SQL。默认(atomic = True,PostgreSQL 支持事务性 DDL):整个迁移回滚——失败({a['last']}),c1 列存在数 {a['c1_exists']}、django_migrations 有记录数 {a['recorded']}。库里没有残留。", n=fl([['第一条 ADD COLUMN c1', '执行'], ['第二条 非法 SQL', '失败'], ['整个事务', '回滚']], done=[0], mark=[1, 2]), t=tl([f"c1 列存在: {a['c1_exists']}", f"django_migrations 有记录: {a['recorded']}"], done=[0, 1]), kv=KV([['atomic = True', '失败 = 全部回滚']], ['atomic = True'])),
    step(f"atomic = False(比如需要 CREATE INDEX CONCURRENTLY 时必须这样):第二条失败时,第一条已经留在库里:c1 列存在数 {n['c1_exists']},而迁移没有被记录(记录数 {n['recorded']})——库处于「半应用」状态。再次 migrate 会把第一条重复执行,得到 {R['rerun']}。", n=fl([['第一条 ADD COLUMN c1', '已提交,留下'], ['第二条 非法 SQL', '失败'], ['django_migrations', '没有记录']], done=[0], mark=[1, 2]), t=tl([f"c1 列存在: {n['c1_exists']}", f"django_migrations 有记录: {n['recorded']}", '再次 migrate → ' + R['rerun']], mark=[0, 2]), kv=KV([['atomic = False', '失败 = 半应用']], ['atomic = False'])),
    step(f"恢复办法一:把库手工修回「第二条之前」的状态(DROP COLUMN c1),修好迁移文件,再 migrate:Applying lab.0002_fail... OK,记录数 {R['fixed']['recorded']}。核心原则:让「数据库的实际状态」与「django_migrations 的记录」重新一致。", t=tl(['手工 DROP COLUMN c1', '修好迁移文件 → migrate → OK', f"记录数 = {R['fixed']['recorded']}"], done=[0, 1, 2]), kv=KV([['恢复', '让实际状态与记录一致']], ['恢复'])),
    step(f"恢复办法二:数据库里已经是最终结果、只缺一条记录时,用 --fake。这里演示反向(migrate lab 0001 --fake):Unapplying … FAKED,记录被删除({R['fake']['recorded']}),但 c1 列仍在({R['fake']['c1_exists']})——--fake 只改记录不改表(第 56 篇展开)。", t=tl([f"记录数: {R['fake']['recorded']}", f"c1 列仍存在: {R['fake']['c1_exists']}"], mark=[1]), kv=KV([['--fake', '只改 django_migrations']], ['--fake'])),
]
A = dict(
    n=55, series='django', tags='Django,Migration,失败恢复,PostgreSQL,真实验证,动画演示',
    desc='在 PostgreSQL 上让迁移的第二条操作失败:默认 atomic 时整个迁移回滚,库里无残留;atomic = False 时第一条已提交而迁移没有记录(半应用),再次 migrate 会因列已存在而失败;恢复的办法是让实际状态与 django_migrations 记录重新一致,或用 --fake。',
    lead='迁移跑到一半失败了,库里是什么状态?下一次 migrate 会怎样?这篇故意写一个「先成功、后失败」的迁移,分别在 atomic 与非 atomic 下跑,再演示两种恢复办法。',
    facts=[('atomic', '默认(PostgreSQL 事务性 DDL):失败全部回滚,库里没有残留、没有记录'), ('半应用', 'atomic = False:前面的操作已提交,迁移没有记录,再 migrate 会因「列已存在」失败'), ('原则', '恢复 = 让数据库实际状态与 django_migrations 记录一致')],
    body=[
        sec('atomic = True(默认)', '', term('', blk('d55', 1)), '<p>PostgreSQL、SQLite 支持事务性 DDL,所以整个迁移是一个事务。MySQL 不支持(DDL 会隐式提交),那里失败就是半应用状态(本文没有测)。</p>'),
        sec('atomic = False', '', term('', blk('d55', 2)), '<p>需要它的场景:<code>CREATE INDEX CONCURRENTLY</code>、大数据回填分批提交。代价就是失败后自己收拾。写非 atomic 迁移时,建议每个迁移只放一个操作,失败后现场容易判断。</p>'),
        sec('恢复办法一:修到一致', '', term('', blk('d55', 3)), '<p>手工撤销已执行的部分,让迁移可以「从头再来」;或者把剩下的部分手工做完再 <code>--fake</code>。</p>'),
        sec('恢复办法二:--fake', '', term('', blk('d55', 4)), '<p><code>--fake</code> 只改记录。用之前要确认库里的实际状态确实与你要标记的迁移一致。</p>'),
        sec('分步演示:迁移失败之后', '', demo('迁移失败与恢复', [('n', 'flow', '过程'), ('t', 'term', '状态'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9431)', '没有验证:MySQL(DDL 隐式提交)上的半应用、SQLite 的事务性 DDL、大表迁移中途被终止(kill)时的锁与残留、迁移里 RunPython 失败时的行为'],
)

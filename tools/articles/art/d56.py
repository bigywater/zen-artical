from lib import *
R = J('d56'); ec = R['fake_email']
steps = [
    step("库里已经有同名表(手工建的,结构与模型相同),直接 migrate lab → " + R['exists'] + ";迁移没有被记录(django_migrations 里没有 lab 的记录)。", t=tl(['migrate lab → ' + R['exists'], 'django_migrations 里 lab 的记录:(无)'], mark=[0]), kv=KV([['已有表', 'CREATE TABLE 失败']], ['已有表'])),
    step("--fake-initial:Django 检查初始迁移里 CreateModel 的表是否已存在,存在就只记录不执行:Applying lab.0001_initial... FAKED。之后读写正常(create 成功,表里 1 行)。", t=tl(R['fake_initial'] + ['记录:0001_initial', R['rw']], done=[0, 1, 2]), kv=KV([['--fake-initial', '表已存在 → 只记录']], ['--fake-initial'])),
    step("陷阱:手工表少了一列(没有 age)。--fake-initial 仍然 FAKED——它只判断表是否存在,不核对列;之后写入才失败:" + R['missing_use'] + "。", t=tl(R['missing_col'] + ['之后写入 → ' + R['missing_use']], cur=[0], mark=[1]), kv=KV([['--fake-initial', '不核对列']], ['--fake-initial'])),
    step(f"--fake(不限于初始迁移):0002 是「加 email 列」,migrate lab --fake 只写记录(FAKED),数据库里 lab_p 的列仍是 {ec['cols']},没有 email;之后写入失败:{ec['use']}。", t=tl(['migrate lab --fake → 0002_email FAKED', f"数据库里的列:{ec['cols']}(没有 email)", '写入 → ' + ec['use']], mark=[1, 2]), kv=KV([['--fake', '不碰数据库,记录与实际不一致']], ['--fake'])),
    step(f"--fake 回退:migrate lab zero --fake 只删记录(记录:{R['fake_zero']['rec']}),表 lab_p 还在(存在数 {R['fake_zero']['table']})。", t=tl([f"记录: {R['fake_zero']['rec']}", f"表 lab_p 还在吗: {R['fake_zero']['table']}"], mark=[1]), kv=KV([['fake 回退', '只删记录,表还在']], ['fake 回退'])),
]
A = dict(
    n=56, series='django', tags='Django,Migration,fake,fake-initial,PostgreSQL,真实验证,动画演示',
    desc='实测 --fake 与 --fake-initial:库里已有同名表时直接 migrate 报 relation already exists;--fake-initial 检查表存在就只记录;但它不核对列,少一列也 FAKED,之后写入才失败;--fake 只写记录不碰表,回退同样只删记录。',
    lead='把已有的数据库接入 Django 迁移,或者迁移已经在库里手工做完了,就要用 --fake。这篇看它们各自「假装」了什么,以及最容易踩的两个坑:表存在但少列、fake 之后记录与实际不一致。',
    facts=[('只查表', '--fake-initial 判断的是初始迁移里的表是否存在,不核对列'), ('只写记录', '--fake 完全不碰数据库,记录与实际可以不一致'), ('回退也是假的', 'migrate lab zero --fake 只删记录,表还在')],
    body=[
        sec('已有表,直接 migrate', '', term('', blk('d56', 1)), '<p>典型场景:把一个手工建表的库接入 Django,或者从另一个 Django 项目搬来表。</p>'),
        sec('--fake-initial', '', term('', blk('d56', 2)), term('', blk('d56', 3)), '<p>它对「初始迁移」有效:CreateModel 的表已存在就跳过。它不比较列类型、不检查约束,所以之前要自己确认表结构与迁移一致。</p>'),
        sec('--fake', '', term('', blk('d56', 4)), term('', blk('d56', 5)), '<p>适合「手工在库里做完了这个变更,补一条记录」。风险是记录与实际不符时,之后的查询才报错(而不是迁移时)。</p>'),
        sec('分步演示:fake 的边界', '', demo('--fake / --fake-initial', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9432)', '没有验证:--fake-initial 对多个 app / 有外键依赖时的判断、--fake-initial 遇到 AddField 类初始迁移的列检查(文档说法不同版本不同,本文只测了 CreateModel)、fake 与 squashed migrations 的交互'],
)

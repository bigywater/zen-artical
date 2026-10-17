from lib import *
R = J('d51'); mu = R['muts']
def row(i): l, ops, n = mu[i]; return f"{l:<34} → {'; '.join(ops)[:60]}  (SQL {n} 条)"
steps = [
    step("makemigrations 拿「迁移文件重放出的旧状态」和「当前 models.py」比较。新增字段:有 default → Add field(SQLite 上要 4 条 SQL,因为 SQLite 只能重建表);null=True → Add field(1 条);既没有 default 又不允许 NULL → 无法生成,--noinput 下直接报错:Field 'stock' on model 'item' not migrated: it is impossible to add a non-nullable field without specifying a default。", t=tl([row(0), row(1), row(2)], cur=[0, 1], mark=[2]), kv=KV([['新增字段', '必须能给已有行一个值']], ['新增字段'])),
    step("字段属性变化:max_length 20 → 50、IntegerField → BigIntegerField 都是 Alter field;只改 help_text 或 choices 这种不影响数据库的属性,也会生成 Alter field 迁移,但 sqlmigrate 是 0 条 SQL(空操作)。所以每次改 choices 都会多一个迁移文件。", t=tl([row(3), row(4), row(5), row(6)], cur=[0, 1], mark=[2, 3]), kv=KV([['help_text / choices', '生成迁移,但没有 SQL']], ['help_text / choices'])),
    step("删除字段 → Remove field(1 条 SQL)。字段改名 price → cost:--noinput 时被当作「删除 price + 新增 cost」(数据会丢);交互模式会问「Was item.price renamed to item.cost (a IntegerField)? [y/N]」,回答 y 才得到 Rename field。模型类改名同理:Create model Product + Delete model Item。", t=tl([row(7), row(8), row(9), '--noinput:' + '; '.join(R['noinput']), '交互回答 y:' + '; '.join(R['answer_y']), '提问原文:' + R['question'][0].split('Migrations')[0].strip()], mark=[1, 2, 3], done=[4]), kv=KV([['改名', '需要回答「是改名」,否则丢数据']], ['改名'])),
    step("改名的同时改了类型(price IntegerField → cost BigIntegerField):即便交互回答 y 也不再被识别为改名,得到 Remove field + Add field。检测改名只在「除名字外完全相同」时才发问。", t=tl(['同时改名 + 改类型 → ' + '; '.join(R['rename_and_type'])], mark=[0]), kv=KV([['改名 + 改类型', '一定是删除 + 新增']], ['改名 + 改类型'])),
    step("其它:新增 Meta.indexes → Create index;新增 unique_together → Alter unique_together;改 Meta.ordering → Change Meta options(0 条 SQL);只加方法或 @property(纯 Python)→ 没有检测到变化,不产生迁移。", t=tl([row(10), row(11), row(13), row(12)], cur=[0, 1], mark=[2], done=[3]), kv=KV([['纯 Python 改动', '不产生迁移'], ['Meta.ordering', '生成迁移但无 SQL']], ['纯 Python 改动'])),
]
A = dict(
    n=51, series='django', tags='Django,Migration,makemigrations,真实验证,动画演示',
    desc='逐项改动模型,看 makemigrations 检测到什么、sqlmigrate 有多少条 SQL:新增字段需要默认值或 NULL;help_text / choices 会生成 0 条 SQL 的迁移;字段改名在 --noinput 下被当作删除 + 新增;改名同时改类型永远是删除 + 新增;纯 Python 方法不产生迁移。',
    lead='makemigrations 是怎么知道你改了什么的?为什么改个 choices 也要生成迁移?改名为什么会问你一句「是不是改名」?这篇一次只改一处,把 14 种改动各跑一遍。',
    facts=[('0 条 SQL', '只改 help_text / choices 也会生成 Alter field 迁移,但 sqlmigrate 是空的'), ('改名', '--noinput 下字段改名 = 删除 + 新增(数据丢失);改名同时改类型,永远是删除 + 新增'), ('纯 Python', '新增方法 / @property 不产生迁移')],
    body=[
        sec('14 种改动的检测结果', '', term('', blk('d51', 1)), '<p>比较的对象是「所有迁移文件按顺序重放得到的状态」与「当前 models」——不是数据库。所以数据库被手工改过的部分它不知道(第 56 篇)。SQL 条数是 SQLite 的(它改列要重建表);PostgreSQL 上同样的改动通常更少。</p>'),
        sec('改名的歧义', '', term('', blk('d51', 2)), term('', blk('d51', 3)), '<p>Django 无法区分「改名」和「删了一个再加一个同类型的」,于是交互式地问你。CI 里用 <code>--noinput</code> 或 <code>--check</code> 时它按「删除 + 新增」处理,这是数据丢失的来源。改名建议分两次提交:先改名(回答 y),再改类型。</p>'),
        sec('分步演示:makemigrations 检测什么', '', demo('makemigrations 检测', [('t', 'term', '检测结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;每个改动都在全新的临时项目里做;--dry-run 看检测,随后真正生成迁移并 sqlmigrate 数 SQL 条数(不含 BEGIN / COMMIT)', '没有验证:PostgreSQL 上每种改动的 SQL 条数、外键 / 多对多 / 自定义字段的检测、约束(CheckConstraint / UniqueConstraint)的检测、swappable 模型、我第一次跑时因为 .pyc 时间戳缓存漏检了 max_length 一项(已用 PYTHONDONTWRITEBYTECODE 排除)'],
)

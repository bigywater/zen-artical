from lib import *
R = J('d54')
steps = [
    step("RunPython 没有提供 reverse_code:migrate lab 0001(回退)→ IrreversibleError: Operation <RunPython …> in lab.0002_data is not reversible。补上 RunPython.noop 作为反向后,回退成功(Unapplying lab.0002_data... OK)。", t=tl([R['irr'], '加 noop 后:' + R['noop'][0]], mark=[0], done=[1]), kv=KV([['没有反向', 'IrreversibleError'], ['RunPython.noop', '声明「反向什么也不用做」']], ['RunPython.noop'])),
    step(f"Django 不检查正反是否「互逆」:正向把 name 改成大写(keep → KEEP),反向用 noop——回退后数据仍是 {R['upper']},没有还原。反向函数是你的承诺,不是 Django 的保证。", t=tl(['正向后:[(\'KEEP\',)]', '反向(noop)后:' + R['upper'] + ' ← 没有还原'], mark=[1]), kv=KV([['noop 反向', '数据不会回来']], ['noop 反向'])),
    step(f"自动生成的迁移的反向:AddField 的反向是 DROP COLUMN;RemoveField 的反向会把列重新加回来,但数据回不来——加列后把 extra 改成 99,删列再回退,列回来了,值是 default 的 7,不是 99({R['readd']})。", n=fl([['AddField', '反向 = DROP COLUMN'], ['RemoveField', '反向 = 加回列(数据丢失)'], ['extra 的值', '99 → 删列 → 回退 → 7']], mark=[1, 2]), kv=KV([['RemoveField 回退', '结构回来,数据不回来']], ['RemoveField 回退'])),
    step(f"DeleteModel 的反向:表被重建,但里面的数据全部丢失——删除前 1 行,回退之后表在、行数 {R['delmodel']}。可逆不等于无损。", t=tl(['删除前行数: [(1,)]', '删除模型后表还在吗(0=不在): [(0,)]', '回退后:表在吗(1=在)[(1,)]  行数 ' + R['delmodel']], mark=[2]), kv=KV([['DeleteModel 回退', '空表']], ['DeleteModel 回退'])),
]
A = dict(
    n=54, series='django', tags='Django,Migration,可逆迁移,真实验证,动画演示',
    desc='实测迁移的正向与反向:RunPython 没有 reverse_code 时回退抛 IrreversibleError,加 RunPython.noop 才能回退;noop 反向不还原数据;RemoveField 回退只恢复列不恢复数据(值变成 default);DeleteModel 回退得到空表。',
    lead='「迁移是可逆的」到底可逆到什么程度?RunPython 不写反向会怎样?删除字段再回退,数据回来了吗?这篇把每种情形都真的回退一遍。',
    facts=[('IrreversibleError', 'RunPython 没有 reverse_code,回退时直接抛这个异常'), ('99 → 7', '删列再回退,列回来了,但值是 default(7),不是删除前的 99'), ('空表', 'DeleteModel 回退重建的是空表,数据全部丢失')],
    body=[
        sec('RunPython 的反向', '', term('', blk('d54', 1)), '<p>没有反向就不能回退,这是好事:强迫你想清楚。确实不需要反向时,写 <code>RunPython.noop</code> 明确表态。</p>'),
        sec('反向不检查互逆', '', term('', blk('d54', 2)), '<p>Django 只负责在回退时调用你的反向函数,不验证它撤销了正向做的事。</p>'),
        sec('自动迁移的反向', '', term('', blk('d54', 3)), '<p>结构可以回退,数据不能。所以在生产环境「回退迁移」不是备份的替代品。</p>'),
        sec('DeleteModel', '', term('', blk('d54', 4)), '<p>同上。要保留数据,回退之前必须先备份。</p>'),
        sec('分步演示:回退的真相', '', demo('迁移的反向', [('t', 'term', '输出'), ('n', 'flow', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;每步真实执行 migrate 并用 SQL 查看数据', '没有验证:PostgreSQL 上同样的回退(数据行为应相同,但未测)、RunSQL 的 reverse_sql、AlterField 回退时数据类型转换失败的情形、elidable 标记'],
)

from lib import *
R = J('d53')
run = R['run']; import re
tl_py = re.search(r'Python 循环 \+ bulk_update\(20000 行\): ([\d.]+) s', run); tl_sql = re.search(r'\((\d+) 行\): ([\d.]+) s', run)
t_py = float(tl_py.group(1)); t_sql = float(tl_sql.group(2)); n_sql = int(tl_sql.group(1))
steps = [
    step("RunPython 的函数拿到的是 apps.get_model('lab', 'Person') 返回的「历史模型」:它的类是 __fake__.Person,没有你在 models.py 里定义的自定义方法(hasattr(Person, 'full_name') = False)。迁移里只能用字段和基本的 ORM,不能调用模型上的业务方法。", t=tl([l.strip() for l in run.splitlines() if '历史模型' in l], mark=[0]), kv=KV([['历史模型', '只有字段,没有自定义方法']], ['历史模型'])),
    step(f"给 10 万行回填一个由两列拼出来的列:Python 循环 + bulk_update 处理 2 万行就用了 {t_py:.2f} s(按比例 10 万行约 {t_py * 5:.1f} s);一条 UPDATE … SET display = first_name || ' ' || last_name 处理 {n_sql} 行只用 {t_sql:.2f} s。能用一条 ORM update()(F / Concat 表达式)完成的,就不要逐行循环。", b=bars([['Python 循环(2 万行,s)', t_py, f"{t_py:.2f}"], ['一条 UPDATE(10 万行,s)', t_sql, f"{t_sql:.2f}"]], t_py * 1.1, mark=[0], done=[1]), kv=KV([['回填', f"一条 UPDATE {t_sql:.2f} s(10 万行)"]], ['回填'])),
    step(f"结果与回退:迁移后 display 非空的行数 {R['filled']};回退(migrate lab 0001)执行反向函数,display 非空的行数 {R['reversed']}。反向函数是自己写的:正向填充、反向清空。", t=tl([f"已填充的行数: {R['filled']}", f"回退后非空的行数: {R['reversed']}"], done=[0, 1]), kv=KV([['正向', '填充'], ['反向', '自己写的清空']], ['反向'])),
    step("陷阱:在迁移里 import 真实模型(from lab.models import Person)。之后模型加了 later 字段,新的迁移 0003 会建这一列;但在全新库上从头 migrate 到 0002 时,真实模型已经有 later 字段而数据库里还没有这一列,查询直接失败:" + R['badreal'] + "。迁移里永远用 apps.get_model。", n=fl([['0002 里 import 真实模型', '模型是「今天的」'], ['数据库状态', '0002 时还没有 later 列'], ['查询', R['badreal'][:50]]], mark=[2]), kv=KV([['迁移里的模型', '必须是「当时的」历史模型']], ['迁移里的模型'])),
]
A = dict(
    n=53, series='django', tags='Django,Migration,RunPython,数据迁移,PostgreSQL,真实验证,动画演示',
    desc=f'实测 RunPython 数据迁移:apps.get_model 拿到的是没有自定义方法的历史模型;10 万行回填,一条 UPDATE(F / Concat){t_sql:.2f} s,Python 循环 + bulk_update 2 万行就要 {t_py:.2f} s;迁移里 import 真实模型会在全新库上因列不存在而失败。',
    lead='数据迁移最容易踩的坑:为什么不能用模型上的方法?为什么不能 import 真实模型?怎么回填才不会慢?这篇用 10 万行 PostgreSQL 数据把这几个问题一次跑清楚。',
    facts=[('历史模型', 'RunPython 里 apps.get_model 返回 __fake__.Person,没有自定义方法'), (f'{t_sql:.2f} s vs {t_py:.2f} s', f'一条 UPDATE 回填 10 万行 vs Python 循环 + bulk_update 回填 2 万行'), ('不要 import 真实模型', '全新库上从头 migrate 时,真实模型的字段比当时的表多,查询会失败')],
    body=[
        sec('历史模型', '', term('', blk('d53', 2)), '<p>迁移执行时,Django 用「迁移状态」构造一份临时的模型类(<code>__fake__</code> 模块)。它的字段与该迁移那一刻一致,但没有任何方法、管理器(除非迁移里声明 <code>use_in_migrations</code>)、信号连接。</p>'),
        sec('回填的写法与耗时', '', '<p>上面演示里「Python 循环」是读出来、改字段、<code>bulk_update</code>;「一条 UPDATE」是 <code>update(display=Concat(F(...), Value(\' \'), F(...)))</code>。耗时数字来自迁移自己打印的计时(本机 PostgreSQL,包含事务)。</p>'),
        sec('正向与反向', '', term('', blk('d53', 3)), '<p>回退时执行你提供的反向函数;不提供会 <code>IrreversibleError</code>(第 54 篇)。</p>'),
        sec('import 真实模型的后果', '', term('', blk('d53', 4)), '<p>这个 bug 在开发库上看不出来(表已经是最新的),只在新环境从头迁移时才炸。</p>'),
        sec('分步演示:数据迁移', '', demo('RunPython 数据迁移', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('n', 'flow', '过程'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9430),10 万行;耗时由迁移函数内 perf_counter 打印', '没有验证:atomic = False 与分批提交的回填、RunSQL 的对比、超大表(千万行以上)、迁移里使用 use_in_migrations 的自定义 Manager、并发写入期间回填的一致性'],
)

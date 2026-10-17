from lib import *
R = J('d38')
calls = [l for l in R['calls'].splitlines() if l.strip()]
steps = [
    step("自定义字段 CSVField(list ↔ 'a,b,c' 文本)各方法被调用的时刻:构造 Post(tags=[...]) 时什么都不调用;save() 时调用 get_prep_value(把 list 变成要写入数据库的值);从库里读出时调用 from_db_value(把文本变回 list)。", t=tl(calls[:3], cur=[1, 2]), kv=KV([['写入', 'get_prep_value'], ['读出', 'from_db_value']], ['读出'])),
    step("查询条件里的值也要经过 get_prep_value:filter(tags='a,b') 与 filter(tags=['a','b']) 都会调用它(后者被 join 成 'a,b'),所以两种写法都能查到;结果行读出时又调用 from_db_value。values_list('tags') 同样走 from_db_value,得到 list。", t=tl(calls[3:6], cur=[0, 1, 2]), kv=KV([['filter 的右值', '也走 get_prep_value'], ['values_list', '走 from_db_value']], ['filter 的右值'])),
    step("full_clean() 走 to_python(把表单/序列化来的值转成 Python 值并校验);serializers.serialize 走 value_to_string(再调用 get_prep_value),输出的 tags 是 'a,b' 字符串。", t=tl(calls[6:], cur=[0, 1]), kv=KV([['校验', 'to_python'], ['序列化', 'value_to_string']], ['序列化'])),
    step("迁移与数据库列:sqlmigrate 显示列类型是 text(继承 TextField 的 db_type);迁移文件里字段被写成 lab.fields.CSVField(default=list)——由 deconstruct() 决定。带 separator=';' 时 deconstruct 会多返回 {'separator': ';'}。", t=tl(R['sqlmigrate'].splitlines()[4:5] + [R['mig_line']] + R['decon'].splitlines()), kv=KV([['列类型', 'text'], ['迁移里的写法', 'deconstruct() 的结果']], ['迁移里的写法'])),
    step("deconstruct() 决定 makemigrations 能否发现字段参数变化:改成 separator=';' 后检测到 Alter field tags on post(0002_alter_post_tags.py);如果 deconstruct 里漏写了 separator,同样的改动 makemigrations 说 No changes detected。", n=fl([['deconstruct 写了 separator', 'Alter field tags on post'], ['deconstruct 没写 separator', 'No changes detected']], done=[0], mark=[1]), kv=KV([['漏写 deconstruct', '改了参数也检测不到']], ['漏写 deconstruct'])),
]
A = dict(
    n=38, series='django', tags='Django,ORM,自定义字段,Field,真实验证,动画演示',
    desc='写一个 list ↔ 逗号文本的自定义字段,记录 to_python / from_db_value / get_prep_value / value_to_string 在构造、保存、查询、values_list、full_clean、序列化时各自被调用的时刻;并验证 deconstruct 漏写参数会让 makemigrations 检测不到变化。',
    lead='自定义模型字段要写哪几个方法?各自什么时候被调用?为什么 deconstruct 那么重要?这篇写一个最小的 CSVField,给每个方法打点,把调用时机一步步记下来。',
    facts=[('get_prep_value / from_db_value', '写入数据库前调用前者,从数据库读出后调用后者;filter 的右值也走前者'), ('to_python', 'full_clean() 与反序列化用它'), ('deconstruct', '漏写参数时,改了字段参数 makemigrations 也报 No changes detected')],
    body=[
        sec('各方法什么时候被调用', '', term('', blk('d38', 1)), '<p>规律:<b>Python → 数据库</b>用 <code>get_prep_value</code>(保存、过滤都走它);<b>数据库 → Python</b>用 <code>from_db_value</code>(取对象、<code>values()</code>、<code>values_list()</code> 都走它);<b>校验 / 反序列化</b>用 <code>to_python</code>;序列化用 <code>value_to_string</code>。</p>'),
        sec('迁移与列类型', '', term('', blk('d38', 2)), '<p>继承 <code>TextField</code> 时列类型自然是 <code>text</code>;要换类型就实现 <code>db_type</code>(本文没有测)。迁移文件里字段怎么写,由 <code>deconstruct()</code> 返回的 (name, path, args, kwargs) 决定。</p>'),
        sec('deconstruct 漏写的后果', '', term('', blk('d38', 3)), '<p>Django 用 <code>deconstruct()</code> 比较新旧字段是否相同。<b>只要你的字段有构造参数,就必须在 deconstruct 里返回</b>,否则改参数不会生成迁移,数据库和代码悄悄不一致。</p>'),
        sec('分步演示:自定义字段的调用时机', '', demo('自定义字段', [('t', 'term', '调用日志'), ('n', 'flow', '迁移检测'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;调用日志由字段方法里的打点写入文件', '没有验证:db_type / rel_db_type 自定义列类型、formfield 在表单里的实际渲染、与 JSONField / ArrayField 的对比、在查询 lookup(如 contains)里的行为、bulk_create 时字段方法的调用'],
)

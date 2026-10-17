from lib import *
R = J('d125')
def S(k): return [l for l in out('d125').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("输入 P = x' OR '1'='1。ORM 的 filter(name=P):发给数据库的 SQL 是 WHERE \"lab_person\".\"name\" = %s,参数 (\"x' OR '1'='1\",) 单独传递,返回 0 行——输入始终是「值」,不会变成 SQL 的一部分。", t=tl(S(1)), done=[0, 1, 2], kv=KV([['ORM filter', '参数化,安全']], ['ORM filter'])),
    step("raw() 用 f-string 拼接同一个输入:返回全部 3 行(alice、bob、carol)——查询条件被改写了;raw('… name = %s', [P]) 返回 0 行。同样的 cursor.execute:f-string 3 行,参数化 0 行;extra(where=[f-string]) 3 行,extra(where=['name = %s'], params=[P]) 0 行。", t=tl(S(2) + S(3)[:2] + S(5)), mark=[0, 2, 4], done=[1, 3, 5], kv=KV([['f-string 拼接', '被注入,返回 3 行'], ['%s + 参数列表', '返回 0 行']], ['f-string 拼接'])),
    step("参数只能代替「值」,不能代替列名 / 表名:ORDER BY name DESC 写在 SQL 里得到 carol、bob、alice;ORDER BY %s DESC 传入 'name' 得到 alice、bob、carol(与插入顺序相同),说明参数被当作字符串值,没有按 name 排序。动态排序不能靠 %s,要用白名单。", t=tl(S(3)[2:]), mark=[1], kv=KV([['参数', '只能是值,不能是列名']], ['参数'])),
    step("order_by(用户输入):'name; DROP TABLE lab_person' 和 'nope' 都得到 FieldError(Cannot resolve keyword …),不是注入;但 order_by('secret') 会成功——结果 bob、carol、alice,能按任意字段排序,等于泄漏 secret 列的顺序。用白名单 {'name', '-name'} 限制后,传 'secret' 会退回 'name'。", t=tl(S(4)), mark=[2], done=[3, 4, 5], kv=KV([['order_by 用户输入', '不注入,但可按任意字段排序'], ['解法', '白名单']], ['解法'])),
]
A = dict(
    n=125, series='django', tags='Django,安全,SQL注入,ORM,参数化,真实验证,动画演示',
    desc="同一个输入 x' OR '1'='1:ORM filter 与 %s 参数化返回 0 行;raw / cursor.execute / extra 用 f-string 拼接返回全部 3 行;参数不能代替列名;order_by(用户输入) 不会注入但能按任意字段排序(泄漏顺序信息),要用白名单。",
    lead='ORM 通常是安全的,但 Django 也提供了 raw()、cursor、extra() 这些让你自己写 SQL 的口子。这篇在自己的本地表上用同一个输入,把安全写法与危险写法的结果并排摆出来。',
    facts=[('0 行 vs 3 行', "同一个输入 x' OR '1'='1:参数化 vs f-string 拼接"), ('%s 不能当列名', '参数是值;动态排序要用白名单'), ('order_by(用户输入)', '不注入,但可以按任意字段排序')],
    body=[
        sec('ORM 怎么发 SQL', '', term('', blk('d125', 1)), '<p>用 <code>connection.execute_wrapper</code> 截下来的 SQL 里是 <code>%s</code> 占位符,参数在第二个位置单独传递——这就是 ORM 防注入的原理。</p>'),
        sec('自己写 SQL:拼接 vs 参数', '', term('', blk('d125', 2)), '<p>拼接时输入里的单引号结束了字符串、<code>OR \'1\'=\'1\'</code> 变成永真条件。这里的数据是我自己建的 3 行本地数据,只演示「条件被改写」,没有做任何破坏性操作。</p>'),
        sec('cursor 与参数的限制', '', term('', blk('d125', 3))),
        sec('order_by 与字段泄漏', '', term('', blk('d125', 4)), '<p>这不是 SQL 注入(Django 会校验字段名),但如果排序参数直接来自请求,用户可以通过排序结果推断出你没想暴露的字段(比如 secret 列的大小关系)。</p>'),
        sec('extra() 里的拼接', '', term('', blk('d125', 5)), '<p><code>extra()</code> 和 <code>RawSQL</code> 一样,是「你负责安全」的接口;能用 ORM 表达的查询就不要用它们。</p>'),
        sec('分步演示', '', demo('SQL 注入', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;表 lab_person 三行本地数据(name + secret);SQL 用 execute_wrapper 记录', '没有验证:其它数据库驱动的参数绑定差异、JSONField / 注解 / 函数参数里的注入面(Django 历史上有过相关安全公告,本文没有复现)、存储过程、二阶注入'],
)

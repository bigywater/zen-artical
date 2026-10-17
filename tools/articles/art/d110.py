from lib import *
R = J('d110')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("写入 100 行(SQLite,给 Item 挂了 pre_save/post_save):逐个 save() 触发 pre_save 100 次、post_save 100 次,发 100 条 SQL;bulk_create 100 行:没有任何信号,1 条 SQL;bulk_update 100 行:没有信号,3 条 SQL;queryset.update():没有信号,1 条 SQL。", t=tl(L('write')), mark=[1, 2, 3], done=[0], kv=KV([['save()', '有信号'], ['bulk_create / bulk_update / update()', '没有信号']], ['bulk_create / bulk_update / update()'])),
    step("删除 2000 行(没有外键关联、没有 delete 信号):delete() 是 3 条 SQL、没有信号;给模型挂了 post_delete receiver 后,同样的 delete() 变成 23 条 SQL、post_delete 触发 2000 次——Django 必须先把 2000 个对象取出来,才能逐个发信号。", t=tl(L('delete')), mark=[1], kv=KV([['无信号', '3 条 SQL'], ['有 post_delete', '23 条 SQL,信号 2000 次']], ['有 post_delete'])),
    step("代价:删除 2 万行,没有 delete 信号 0.6 ms;有 post_delete receiver 125.9 ms(3 次取中位,SQLite,receiver 里只做计数)。", t=tl(L('bench')), b=bars([['无信号', 0.6, '0.6 ms'], ['有 post_delete', 125.9, '125.9 ms']], 130, mark=[1], done=[0]), kv=KV([['有信号后的删除', '约 200 倍慢(这个测法)']], ['有信号后的删除'])),
    step("既然 bulk 操作绕过信号,需要的话要自己补发:遍历 5 行手动 post_save.send(sender=Item, instance=i, created=True),receiver 触发了 5 次。注意这是伪造的「保存事件」,receiver 看到的 created / update_fields 等要自己填对。", t=tl(L('manual')), kv=KV([['手动 send', '可以补发,参数自己负责']], ['手动 send'])),
]
A = dict(
    n=110, series='django', tags='Django,Signal,bulk_create,delete,真实验证,动画演示',
    desc='bulk_create / bulk_update / queryset.update() 都不发 pre_save / post_save;queryset.delete() 在没有 delete 信号时是快速删除(2000 行 3 条 SQL),挂上 post_delete 后要取出对象逐个发信号(23 条 SQL);删 2 万行 0.6 ms → 125.9 ms。',
    lead='想用信号监听「所有写入」的人,常常在 bulk 操作那里踩空:批量写入不会触发保存信号,而删除又恰恰相反——一旦有人监听了 delete 信号,批量删除会变慢很多。这篇把这两头都量出来。',
    facts=[('没有信号', 'bulk_create / bulk_update / queryset.update() 都不发 pre_save、post_save'), ('3 → 23 条 SQL', '删 2000 行:没有 delete 信号 → 有 post_delete receiver'), ('0.6 → 125.9 ms', '删 2 万行的耗时,同样的对比')],
    body=[
        sec('写入:哪些发信号', '', term('', blk('d110', 1)), '<p>只有走 <code>save()</code> 的写入才会发 pre_save / post_save。如果业务上「所有的写入都要触发某个动作」,批量写入需要另外处理(比如写完之后自己调用同样的函数)。</p>'),
        sec('删除:反过来', '', term('', blk('d110', 2)), '<p>没有 delete 信号且没有需要级联处理的关系时,<code>queryset.delete()</code> 走快速删除(一条 DELETE)。只要模型上挂了 <code>pre_delete</code> / <code>post_delete</code> receiver,Django 就得把对象取出来逐个发信号。</p>'),
        sec('耗时差多少', '', term('', blk('d110', 4)), '<p>0.6 ms 这么快,可能有 SQLite 对无条件 DELETE 的优化(我没有验证),所以「200 倍」只适合这个测法,不要当作通用倍数;但方向是确定的:监听 delete 信号会让批量删除退化为逐行处理。</p>'),
        sec('手动补发', '', term('', blk('d110', 3))),
        sec('分步演示', '', demo('bulk 操作与信号', [('t', 'term', '输出'), ('b', 'bars', '删除耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;Item 模型监听 pre_save / post_save,Plain 模型(无外键)用来测 delete', '没有验证:有级联外键时的删除路径、PostgreSQL / MySQL 上的 SQL 条数与耗时、bulk_create 的 ignore_conflicts / update_conflicts、Django 对 SQLite 无条件 DELETE 的优化细节'],
)

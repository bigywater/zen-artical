from lib import *
R = J('d104')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("新建对象 Item(name='a').save():顺序是 pre_save(pk=None)→ INSERT → post_save(pk=1, created=True)。pre_save 时对象还没有 pk;post_save 时已经有了。", t=tl(L('create')), mark=[0], done=[2], kv=KV([['pre_save', 'pk=None'], ['post_save', 'created=True, 已有 pk']], ['post_save'])),
    step("更新已有对象:save() 生成 UPDATE 全部字段,post_save 的 created=False;save(update_fields=['n']) 只 UPDATE n 这一列,并且信号里的 update_fields 就是 ['n']——receiver 据此可以判断哪些字段被写了。", t=tl(L('update')), kv=KV([['created', 'False'], ['update_fields', '传给信号']], ['update_fields'])),
    step("在 atomic() 里保存:先 BEGIN,再 pre_save → INSERT → post_save,然后才轮到块里的最后一行——post_save 是在 COMMIT 之前触发的(记录里没有出现 COMMIT 这一行,原因我没有深究)。", t=tl(L('atomic')), mark=[2], kv=KV([['post_save', '在 COMMIT 之前']], ['post_save'])),
    step("删除:instance.delete() 是 BEGIN → pre_delete → DELETE → post_delete。queryset.update(n=1) 只有一条 UPDATE、没有任何信号。get_or_create 找不到时:SELECT → BEGIN → pre_save → INSERT → post_save(created=True)。", t=tl(L('delete')), mark=[1], kv=KV([['queryset.update()', '不发信号'], ['instance.delete()', 'pre_delete / post_delete']], ['queryset.update()'])),
    step("pre_save 里改字段会写入数据库(name 写成 lower,pre_save 里改成大写,库里是 LOWER);post_save 里改 instance 只改内存(内存里是 changed-after,库里还是保存时的 orig)——post_save 时 INSERT 已经执行完了。", t=tl(L('mutate')), mark=[1], kv=KV([['pre_save 里改字段', '会被写入'], ['post_save 里改字段', '只在内存']], ['pre_save 里改字段'])),
]
A = dict(
    n=104, series='django', tags='Django,Signal,pre_save,post_save,真实验证,动画演示',
    desc='用 execute_wrapper 记录 SQL,看 pre_save / post_save / pre_delete / post_delete 与 INSERT、UPDATE、DELETE 的交错顺序;update_fields 会传进信号;atomic 里 post_save 在 COMMIT 之前;queryset.update() 不发信号;pre_save 里改字段会写入。',
    lead='pre_save 和 post_save 到底在 save() 的哪个位置触发?对象有没有 pk?事务提交了没有?这篇把信号和 SQL 放进同一条时间线里,一行行对照。',
    facts=[('pk=None → 1', 'pre_save 时新对象没有 pk,post_save 时有'), ('update_fields', 'save(update_fields=[...]) 的字段列表会传给信号'), ('COMMIT 之前', 'atomic 里 post_save 触发时事务尚未提交')],
    body=[
        sec('新建对象', '', term('', blk('d104', 1)), '<p>用 <code>connection.execute_wrapper</code> 记下每条 SQL,和信号回调排进同一个列表,才能看出真实的先后。</p>'),
        sec('更新对象', '', term('', blk('d104', 2)), '<p>UPDATE 时 <code>created</code> 是 <code>False</code>;<code>update_fields</code> 为 <code>None</code> 表示保存了全部字段。</p>'),
        sec('在事务里保存', '', term('', blk('d104', 3)), '<p>post_save 在 COMMIT 之前触发,这是下一篇要展开的问题:receiver 里做的事看到的是「未提交」的数据。</p>'),
        sec('删除与不发信号的操作', '', term('', blk('d104', 4)), '<p>批量的 <code>queryset.update()</code> 不走 <code>save()</code>,不发信号;<code>bulk_create</code> 等见第 110 篇。</p>'),
        sec('在信号里改对象', '', term('', blk('d104', 5)), '<p>如果要在保存前修改字段,放在 pre_save(或者 <code>save()</code> / <code>clean()</code>);在 post_save 里改 instance 不会自动写回。</p>'),
        sec('分步演示', '', demo('save() 时间线', [('t', 'term', '时间线'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;SQL 用 connection.execute_wrapper 记录,只截取前 52 个字符', '没有验证:多对多 through 表的信号、继承模型(多表继承)的信号、raw=True(loaddata)时的行为、deferred 字段与 update_fields 的关系、PostgreSQL 上的行为差异'],
)

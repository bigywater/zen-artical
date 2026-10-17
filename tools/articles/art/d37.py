from lib import *
R = J('d37')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("BookQuerySet.as_manager():自定义方法 cheap()、by() 既能直接在 Book.objects 上调用,也能链在 filter() 之后:objects.cheap()、objects.filter(...).cheap()、objects.by('ann').cheap() 都可以。objects 的类型是自动生成的 ManagerFromBookQuerySet,filter 之后返回的是 BookQuerySet。", t=tl(L('qs'), cur=[0, 1, 2, 3]), kv=KV([['as_manager()', '方法同时出现在 Manager 与 QuerySet 上']], ['as_manager()'])),
    step("覆盖 Manager.get_queryset() 做软删除:Author.objects.all() 只看到 ann;另存一个 all_objects = models.Manager() 才看得到 ghost(deleted=True)。Author.objects.get(name='ghost') → DoesNotExist。_default_manager 是模型里第一个定义的 Manager(ActiveManager)。", t=tl(L('soft'), cur=[0, 1, 2], mark=[4]), kv=KV([['默认 Manager', '第一个定义的'], ['软删除', 'objects 过滤,all_objects 不过滤']], ['默认 Manager'])),
    step("关系访问不走自定义 Manager:Book 'gb' 的作者 ghost 已「软删除」,gb.author 仍然返回 ghost(deleted=True);Book.objects.filter(author__name='ghost') 的 JOIN 也不受影响。关联对象访问用的是 _base_manager(普通 Manager),不是 objects。", t=tl(L('rel'), cur=[0], mark=[1]), kv=KV([['book.author', '能取到已软删除的作者'], ['JOIN', '不受 objects 过滤']], ['book.author'])),
    step("Manager 顺序:Author._meta.managers 是 ['objects', 'all_objects'],第一个是默认;Book 只有 objects。想改默认可以用 Meta.default_manager_name。(本文只验证了顺序,没有验证 default_manager_name / base_manager_name 的效果。)", t=tl(L('order'), cur=[0, 1]), kv=KV([['顺序', '定义顺序决定默认 Manager']], ['顺序'])),
]
A = dict(
    n=37, series='django', tags='Django,ORM,Manager,QuerySet,软删除,真实验证,动画演示',
    desc='实测自定义 QuerySet + as_manager() 的链式调用、覆盖默认 Manager 做软删除;关系访问(book.author)与 JOIN 不走自定义 Manager,已软删除的对象仍能被取到;默认 Manager 是模型里第一个定义的。',
    lead='软删除最常见的写法是覆盖 Manager 的 get_queryset。它挡得住多少?为什么 book.author 还是能拿到「已删除」的作者?这篇用一个带软删除的小模型逐项验证。',
    facts=[('as_manager()', '自定义 QuerySet 的方法可以出现在 Manager 上,也可以链在 filter 后面'), ('第一个定义的', '模型的默认 Manager 是第一个定义的 Manager'), ('关系不走 objects', 'book.author 与 JOIN 都不受自定义 Manager 的过滤(已软删除的对象仍然能取到)')],
    body=[
        sec('自定义 QuerySet', '', term('', blk('d37', 1)), '<p>把可复用的过滤写成 <code>QuerySet</code> 的方法,再 <code>as_manager()</code>,既能 <code>Book.objects.cheap()</code>,也能 <code>Book.objects.filter(...).cheap()</code>。直接写 Manager 方法则没法链在 filter 后面。</p>'),
        sec('软删除:覆盖 get_queryset', '', term('', blk('d37', 2)), '<p>把「排除已删除」放进默认 Manager,业务代码里 <code>Author.objects</code> 就天然看不到它们。同时保留一个不过滤的 Manager 供管理用。</p>'),
        sec('过滤挡不住的地方', '', term('', blk('d37', 3)), '<p>外键的正向访问(<code>book.author</code>)使用 <code>_base_manager</code>,不受你自定义的默认 Manager 影响——这是有意的(否则外键会「悬空」)。JOIN、<code>filter(author__…)</code> 也一样。如果业务要求「已删除的作者不应出现」,要在这些地方显式处理。</p>'),
        sec('顺序', '', term('', blk('d37', 4)), '<p>第一个定义的 Manager 是默认 Manager(<code>_default_manager</code>),admin、序列化等许多内部功能用它。把「过滤后的」放第一位要想清楚这些内部用途(本文没有验证 admin 的行为)。</p>'),
        sec('分步演示:Manager 与 QuerySet', '', demo('Manager 与软删除', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:Meta.default_manager_name / base_manager_name 的效果、admin 与序列化对默认 Manager 的使用、反向关系管理器(author.books)是否继承自定义 Manager、迁移里的 managers 选项(use_in_migrations)'],
)

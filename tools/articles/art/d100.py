from lib import *
R = J('d100'); sc = R['scale']
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("admin 列表页 N+1(50 篇文章、10 个作者、3 个分类):文章列表 list_display=(title, author) 需要 55 次查询;作者列表 list_display=(name, category) 只要 5 次。区别在哪?admin 会自动对 list_display 里的外键列做 select_related(所以文章的 author、作者的 category 都不再单独查),但模型的 __str__ 在展示时又访问了更深一层的外键——Author.__str__ 里用了 category.name,每个作者对象显示时再查一次 category。", t=tl(L('default')), kv=KV([['admin 已自动 select_related', 'list_display 里的外键列'], ['没覆盖的', '__str__ 里更深的外键']], ['没覆盖的'])),
    step("藏 N+1 的地方:__str__ 调用别的对象的 __str__(Post.__str__ → Author.__str__ → category)——5 篇文章各 str(p) 共 10 次查询(每篇取 author + 取 category);方法 / @property(label 用 author.category.name)5 篇共 11 次(含 1 次取列表)。任何在循环里被反复调用、又访问了关联对象的东西,都是候选。", t=tl(L('str')), mark=[0, 1], kv=KV([['__str__ / property', '在列表页里被每行调用']], ['__str__ / property'])),
    step("修复:list_select_related = ('author__category')(文章)、('category',)(作者)后,两个列表页都是 5 次查询(会话 / 用户 / 计数 / 主查询等固定开销)。", t=tl(L('fixed')), kv=KV([['list_select_related', '把嵌套的外键一起 JOIN 出来']], ['list_select_related'])),
    step("随数据量的变化:文章数 10 / 50 / 200 → 未优化 " + ' / '.join(str(sc[k]['未优化']) for k in ('10', '50', '200')) + " 次查询,优化后都是 " + str(sc['50']['优化']) + " 次。200 篇时未优化只是 105 次,因为 admin 默认每页 100 条(所以 N+1 的上限被分页压住了,但也就是每页 100 次多余查询)。", b=bars([[f'{k} 篇 未优化', sc[k]['未优化'], str(sc[k]['未优化'])] for k in ('10', '50', '200')] + [['优化后(任意)', sc['50']['优化'], str(sc['50']['优化'])]], 110, mark=[0, 1, 2], done=[3]), kv=KV([['未优化', '≈ 每行 1 次额外查询'], ['优化后', '与行数无关']], ['优化后'])),
]
A = dict(
    n=100, series='django', tags='Django,N+1,admin,list_select_related,真实验证,动画演示',
    desc=f'在 admin 列表页上实战 N+1:admin 会自动对 list_display 里的外键做 select_related,但 __str__ 里更深的外键(author.category)仍然每行一次({sc["50"]["未优化"]} 次查询 / 50 行);list_select_related 之后固定 {sc["50"]["优化"]} 次;10/50/200 行的查询数 {sc["10"]["未优化"]}/{sc["50"]["未优化"]}/{sc["200"]["未优化"]}(admin 每页 100 条)。',
    lead='N+1 不只出现在你自己写的视图里,admin 列表页、__str__、@property 也会悄悄制造它。这篇用一个三层关系(分类 → 作者 → 文章)的 admin,把 N+1 从发现到修复走一遍。',
    facts=[(f'{sc["50"]["未优化"]} → {sc["50"]["优化"]}', '50 行文章列表的查询数:未优化 → list_select_related'), ('__str__', '模型的 __str__ 里访问外键,在每一行显示时都会触发查询'), ('自动 select_related', 'admin 对 list_display 里的外键列会自动 select_related,但不会跟到 __str__ 里更深一层')],
    body=[
        sec('admin 列表页', '', term('', blk('d100', 1)), '<p>这里的关键是「admin 已经帮你做了一层」——所以有时候你以为没问题,换一个模型的 <code>__str__</code> 就出现了 N+1。</p>'),
        sec('藏在 __str__ 与 property 里', '', term('', blk('d100', 2)), '<p>最好的习惯:模型的 <code>__str__</code> 只用自己的字段,不要访问外键;需要展示关联信息时用专门的 <code>list_display</code> 方法并配合 <code>list_select_related</code>。</p>'),
        sec('修复', '', term('', blk('d100', 3)), '<p><code>list_select_related</code> 接受字段名元组(可以带 <code>__</code> 做多层)。也可以在 <code>get_queryset</code> 里自己 <code>select_related</code> / <code>prefetch_related</code>。</p>'),
        sec('数据量的影响', '', term('', blk('d100', 4)), '<p>用不同的行数各跑一遍,就能确认查询数是不是与行数成正比——这是判断 N+1 最直接的办法。</p>'),
        sec('分步演示:N+1 实战', '', demo('admin 里的 N+1', [('t', 'term', '输出'), ('b', 'bars', '查询数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;admin 页面由 django.test.Client 以超级用户请求,查询数由 CaptureQueriesContext 统计(含会话、用户、计数等固定开销)', '没有验证:admin 详情页 / inline 里的 N+1、DRF 序列化器里的 N+1、django-debug-toolbar 的重复查询检测(第 101 篇)、更早版本的 admin 是否也自动 select_related(6.1.1 的行为已读 ChangeList.apply_select_related 源码确认)'],
)

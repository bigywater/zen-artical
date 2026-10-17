from lib import *
import re
R = J('d91')
def rows(k): return [(l.rsplit('  ', 1)[0].strip(), int(re.search(r'(\d+) 次', l).group(1))) for l in R[k].splitlines() if '次' in l and not l.startswith('传')]
b = rows('basic'); f = rows('fk')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("模板里的 QuerySet 用法与查询次数(20 篇文章):遍历一次 1 次;同一个 QuerySet 对象遍历两次仍是 1 次(结果缓存);{% if posts %} 再 for 1 次;{{ posts|length }} + for 1 次;{% for %}{% empty %} 1 次。", t=tl([f"{k:<50} {v} 次" for k, v in [b[i] for i in (0, 1, 2, 4, 7)]], cur=[0, 1, 2, 3, 4]), kv=KV([['同一个 QuerySet', '求值一次,之后走缓存']], ['同一个 QuerySet'])),
    step("会多查的写法:{{ posts.count }} + for + {{ posts.count }} 共 2 次(第一个 .count 在还没求值时发 COUNT,for 求值一次,第二个 .count 用缓存);{% for p in posts.all %} 写两次共 2 次——每个 .all 产生新的 QuerySet,缓存不共享;{{ posts.0.title }} 和 {{ posts.first.title }} 各查一次共 2 次(没有求值时按下标/first 取,各发一条 LIMIT 查询)。", t=tl([f"{k:<50} {v} 次" for k, v in b[3:4] + b[5:7]], mark=[0, 1, 2]), kv=KV([['.all / .first / [0]', '各产生新的查询']], ['.all / .first / [0]'])),
    step("N+1 藏在「看起来没查」的地方:遍历里访问 p.author.name 21 次查询(1 + 20);__str__ 里用了 self.author.name 的模型,模板里只写 {{ p }} 也是 21 次;a.posts.count / a.posts.all|length 每个作者各查一次共 6 次。加 select_related('author') 变 1 次;prefetch_related('posts') 变 2 次。", t=tl([f"{k:<56} {v} 次" for k, v in f]), mark=[0, 2, 4, 5], done=[1, 3, 6, 7], b=bars([['p.author.name 不优化', f[0][1], str(f[0][1])], ['+ select_related', f[1][1], str(f[1][1])], ['a.posts.count 不优化', f[4][1], str(f[4][1])], ['+ prefetch_related', f[7][1], str(f[7][1])]], 22, mark=[0, 2], done=[1, 3]), kv=KV([['__str__ 里的外键', '也是 N+1']], ['__str__ 里的外键'])),
    step("最省心的办法:在视图里先求值(list(...)),把列表传给模板:模板里怎么遍历、取长度都是 0 次查询(列表已经在内存里)。代价是失去 QuerySet 的方法(.count 等,对 list 是另一个含义),并且要在视图里就把 select_related / prefetch_related 写对。", t=tl(L('list')), kv=KV([['传 list', '模板里再多的遍历也不查库']], ['传 list'])),
]
A = dict(
    n=91, series='django', tags='Django,模板,QuerySet,N+1,真实验证,动画演示',
    desc=f'在模板里数 QuerySet 的查询次数:同一个 QuerySet 遍历多次只查 1 次;{{% for p in posts.all %}}、.first、.0 各自新查;遍历里访问外键或 __str__ 里用了外键是 {f[0][1]} 次(1 + 20),select_related 后 {f[1][1]} 次;a.posts.count / all 每个作者一次;prefetch_related 后 {f[6][1]} 次;传 list 给模板 0 次。',
    lead='QuerySet 是惰性的,而模板是最容易「不知不觉」触发查询的地方。这篇用 12 个小模板,把每种写法发了几次查询数清楚,尤其是 __str__ 和反向关系里的 N+1。',
    facts=[('1 次', '同一个 QuerySet 在模板里遍历几次都只查 1 次(结果缓存)'), (f'{f[0][1]} → {f[1][1]}', '遍历里访问 p.author.name(或 __str__ 里用外键):不优化 → select_related'), ('.all / .first / [0]', '每次都产生新的查询,不共享缓存')],
    body=[
        sec('QuerySet 在模板里的求值', '', term('', blk('d91', 1)), '<p>模板语言里 <code>posts.count</code> 是方法调用(没有括号),<code>posts.0</code> 是下标。它们对「还没求值」的 QuerySet 各发一次查询。</p>'),
        sec('藏在关系与 __str__ 里的 N+1', '', term('', blk('d91', 2)), '<p>值得注意的是 <code>__str__</code>:admin 的列表页、下拉框、日志里打印对象,都会调用它。如果 <code>__str__</code> 里访问了外键,每一行都会多一次查询。另外一个细节:在预取过的关系上 <code>.count</code> 用的是预取缓存(实测 2 次),而没有预取时每个作者一次 COUNT。</p>'),
        sec('在视图里先求值', '', term('', blk('d91', 3)), '<p>这不是通用建议,但它让「模板会查多少次库」变得可预测。</p>'),
        sec('分步演示:模板里的查询', '', demo('模板里的 QuerySet', [('t', 'term', '查询次数'), ('b', 'bars', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;用 render_to_string + CaptureQueriesContext 数查询', '没有验证:{% include %} 里的重复求值、自定义 tag 里的查询、模板缓存({% cache %})对查询的影响(第 95 篇)、Jinja2 后端的行为'],
)

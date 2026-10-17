from lib import *
R = J('d57'); cl = R['clash']
steps = [
    step("两个分支各加一个迁移(0002_add_a、0002_add_b),都依赖 0001:图里有两个叶子节点。migrate 与 makemigrations 都拒绝工作,提示 " + R['migrate'] + "。showmigrations 里两个 0002 并列。", t=tl(R['show'].splitlines() + ['migrate → ' + R['migrate']], mark=[2, 3, 4]), kv=KV([['两个叶子', '迁移冲突']], ['两个叶子'])),
    step("makemigrations --merge 生成一个合并迁移:输出会列出两个分支各自的操作(Branch 0002_add_a + Add field a;Branch 0002_add_b + Add field b);生成的 0003_merge_… 文件本身 operations 为空,只是 dependencies 同时指向两个 0002。之后 migrate 依次执行三个迁移。", t=tl(R['merge_out'].splitlines()[:6] + ['0003 的 dependencies = [(\'lab\', \'0002_add_a\'), (\'lab\', \'0002_add_b\')];operations = []'] + R['applied'], cur=[6], done=[7, 8, 9]), kv=KV([['合并迁移', '空操作,把两条线接成图的一个节点']], ['合并迁移'])),
    step(f"合并只管图,不管两个分支的操作是否兼容:两边都给同一个字段 x 加列(一个 IntegerField、一个 TextField)。SQLite 上合并后 migrate 不报错,最终列是 {cl['SQLite']['cols']}——后执行的重建表覆盖了先执行的;PostgreSQL 上第二个迁移报错:{cl['PostgreSQL']['error']},留下的是先执行的那个(x:text)。同样的迁移,不同数据库结局不同。", n=fl([['SQLite', '无报错,列被悄悄改成 INTEGER'], ['PostgreSQL', '报错 column x already exists']], mark=[0, 1]), kv=KV([['合并不检查兼容性', '要人工核对两个分支']], ['合并不检查兼容性'])),
]
A = dict(
    n=57, series='django', tags='Django,Migration,冲突,merge,真实验证,动画演示',
    desc='两个分支各生成一个依赖 0001 的迁移时 migrate / makemigrations 都拒绝工作;makemigrations --merge 生成空操作的合并迁移;合并不检查两个分支是否兼容——同一字段加不同类型,SQLite 悄悄改成后者,PostgreSQL 直接报错。',
    lead='团队并行开发时最常见的迁移问题:两个人各生成了 0002。Django 怎么发现的,merge 到底做了什么,它能保证合并后正确吗?这篇复现冲突,并故意制造一个「合并后仍然冲突」的例子。',
    facts=[('两个叶子节点', '同一个 app 出现两个叶子迁移时,migrate 与 makemigrations 都拒绝运行'), ('空操作', '--merge 生成的迁移 operations 为空,只把两条依赖线接起来'), ('不检查兼容', '两个分支给同一字段加不同类型,SQLite 悄悄成功,PostgreSQL 报错')],
    body=[
        sec('冲突的样子', '', term('', blk('d57', 1)), '<p>迁移之间的依赖是图,同一个 app 有两个「没有后继」的迁移就是分叉。</p>'),
        sec('makemigrations --merge', '', term('', blk('d57', 2)), '<p>合并迁移只是一个把 <code>dependencies</code> 指向两个叶子的节点,operations 默认为空。如果两个分支的操作会互相影响(比如改同一个字段),要手工在合并迁移里补操作。</p>'),
        sec('合并之后仍然可能出错', '', term('', blk('d57', 3)), '<p>Django 不分析两个分支的操作是否兼容。<b>而且不同数据库的表现不同</b>:SQLite 通过重建表悄悄把问题掩盖了,PostgreSQL 则报错——在 SQLite 上测试通过的迁移不代表在生产数据库上也行。</p>'),
        sec('分步演示:迁移冲突与合并', '', demo('迁移冲突与合并', [('t', 'term', '输出'), ('n', 'flow', '两个数据库'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite 与 PostgreSQL 16.15(本机临时实例,端口 9433)', '没有验证:三个及以上分支的合并、合并迁移里手工补操作、多个 app 之间的依赖冲突、run_before 的交互、在版本控制里预防冲突的流程建议'],
)

from lib import *
import re
R = J('d87')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
pf = re.findall(r'([\d.]+) µs', R['perf']); pf = [float(x) for x in pf]
steps = [
    step("三层继承 base → mid → leaf:base 有 title / content / footer 三个 block;mid 覆盖 title(mid-title/{{ block.super }})和 content(里面再定义 inner);leaf 覆盖 content(leaf-content/{{ block.super }})与 inner。渲染 leaf 得到 [base-top]mid-title/base-title|leaf-content/mid-content(leaf-inner)|base-footer[base-bottom]:{{ block.super }} 取的是「上一层的同名 block」。", t=tl(L('levels')), kv=KV([['子覆盖父', '最子的优先'], ['block.super', '取上一层同名 block']], ['block.super'])),
    step("被忽略的:leaf 里定义了父链里不存在的 block(nosuch),输出里没有 IGNORED;子模板里 block 之外的内容被忽略;{% extends %} 前面有文字时,这次实测没有报错,文字 \"text before\" 还出现在输出最前面(文档要求 extends 必须是第一个标签,这里只验证了没有报错);同一个模板里定义两个同名 block → TemplateSyntaxError。", t=tl(L('ignored')), kv=KV([['不存在的 block', '被忽略,不报错'], ['重名 block', 'TemplateSyntaxError']], ['不存在的 block'])),
    step("{% extends 变量 %} 可以是变量(dyn.html 的 parent_tpl='base.html')。每次渲染实际读盘:base.html 加载 1 个文件;mid.html 加载 mid + base 2 个;leaf.html 加载 leaf + mid + base 3 个(用无 cached 加载器,带日志)。层数 = 读盘次数;cached 加载器把它们缓存起来(第 82 篇)。", t=tl(L('loads')), b=bars([['base.html 读盘', 1, '1'], ['mid.html 读盘', 2, '2'], ['leaf.html 读盘', 3, '3']], 3, done=[0, 1, 2]), kv=KV([['读盘次数', '= 继承层数(无 cached)']], ['读盘次数'])),
    step("include 与 extends 不同:include 的子模板独立渲染,inc.html 里的 block b 不会被外层覆盖(输出仍是 inc-block),用 with 传参(x=1)。with_inc.html 一共加载 with_inc、base、inc 三个文件。", t=tl(L('include')), kv=KV([['include', '独立渲染,不能覆盖 block'], ['extends', '子覆盖父的 block']], ['include'])),
    step(f"渲染耗时(cached 加载器,300 次中位):单层 base {pf[0]:.1f} µs;两层 leaf2 {pf[1]:.1f} µs;三层 leaf {pf[2]:.1f} µs——继承层数增加渲染成本近似线性,但绝对值很小(微秒级)。", b=bars([['base(1 层)µs', pf[0], f"{pf[0]:.1f}"], ['leaf2(2 层)µs', pf[1], f"{pf[1]:.1f}"], ['leaf(3 层)µs', pf[2], f"{pf[2]:.1f}"]], pf[2] * 1.1, mark=[2]), kv=KV([['层数', '几乎不是性能问题']], ['层数'])),
]
A = dict(
    n=87, series='django', tags='Django,模板,模板继承,block,真实验证,动画演示',
    desc=f'实测模板继承与 block 渲染:三层继承里子覆盖父、block.super 取上一层;父链里不存在的 block 被忽略、重名 block 报错;继承层数 = 读盘次数(无 cached);include 与 extends 的差别;1/2/3 层继承渲染 {pf[0]:.1f}/{pf[1]:.1f}/{pf[2]:.1f} µs。',
    lead='{% extends %} 和 {% block %} 是怎么把几层模板拼成一个页面的?{{ block.super }} 取的是哪一层?加载模板要读几次盘?这篇用三层模板和一个带日志的加载器把这些都摊开。',
    facts=[('block.super', '取「上一层同名 block」的内容,不是最顶层'), ('读盘', '继承 N 层 = 无 cached 时读 N 次文件;cached 加载器缓存'), ('不存在的 block', '子模板定义了父链里没有的 block,被静默忽略')],
    body=[
        sec('三层继承', '', term('', blk('d87', 1)), '<p>渲染从最子的模板开始:它 <code>extends</code> 的链一路向上,直到根模板;最后根模板被渲染,遇到 block 时取链上「最子的」那个定义。</p>'),
        sec('被忽略与报错', '', term('', blk('d87', 2)), '<p>拼错 block 名是常见 bug:子模板的内容因此被静默忽略,页面上看不到——排查时先核对 block 名。</p>'),
        sec('读盘次数', '', term('', blk('d87', 3)), '<p>这是 <code>filesystem</code> 加载器的读盘计数(手工在加载器的 <code>get_contents</code> 上加了日志)。</p>'),
        sec('include 与 extends', '', term('', blk('d87', 4)), '<p>选择:「页面骨架 + 可替换区域」用 extends;「可复用的片段」用 include(带参数用 <code>with</code>,隔离用 <code>only</code>,后者本文没有测)。</p>'),
        sec('耗时', '', term('', blk('d87', 5)), '<p>合成模板,渲染很小;真实页面的开销主要在数据库和你的变量。</p>'),
        sec('分步演示:模板继承', '', demo('模板继承', [('t', 'term', '输出'), ('b', 'bars', '数量 / 耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 render_to_string;读盘次数由 monkey-patch filesystem.Loader.get_contents 记录', '没有验证:extends 必须是第一个标签这一文档要求的报错情形(本次实测有文字在前也没报错,原因没有查)、block 里的 {% if %} 与 super 的组合、自定义 tag 里的 block 渲染、include 的 only 参数'],
)

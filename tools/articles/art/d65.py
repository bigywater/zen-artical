from lib import *
R = J('d65')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("save()(commit=True):INSERT 对象、然后在一个事务里写多对多(SELECT 现有关系 → INSERT OR IGNORE lab_post_tags)。一次调用全部完成,tags = a、b。", t=tl(L('commit_true')), kv=KV([['commit=True', '对象 + 多对多一起写']], ['commit=True'])),
    step("save(commit=False):不发任何查询(0 次),返回 pk=None 的未保存对象,库里 Post 数量仍是 0。你可以改字段(owner='me')再自己 p.save();此时 tags 仍为空——多对多要对象有 pk 之后才能写。最后调用 f.save_m2m():才写多对多关系,tags = a、b。save_m2m 这个方法就是 save(commit=False) 挂在表单上的。", t=tl(L('commit_false')[:1] + L('commit_false')[1:]), kv=KV([['commit=False', '不写库,不写多对多'], ['save_m2m()', '你来决定什么时候写']], ['save_m2m()'])),
    step("最危险的坑:save(commit=False) 后自己 p.save() 却忘了 f.save_m2m():用户选的标签 c 悄悄丢失(tags = []),没有任何报错。还没调用 save(commit=False) 就调用 save_m2m():AttributeError: 'PF' object has no attribute 'save_m2m'。", t=tl(L('forgot')), n=fl([['p.save() 之后忘了 save_m2m()', 'tags = [],不报错']], mark=[0]), kv=KV([['忘了 save_m2m()', '静默丢数据']], ['忘了 save_m2m()'])),
    step("正确写法:p = f.save(commit=False) → 设置只有服务端知道的字段(owner = request.user)→ p.save() → f.save_m2m()。这是 commit=False 最常见的用途:补上不来自表单的字段。", t=tl(L('owner')), kv=KV([['标准写法', 'commit=False → 改字段 → save() → save_m2m()']], ['标准写法'])),
]
A = dict(
    n=65, series='django', tags='Django,ModelForm,commit=False,真实验证,动画演示',
    desc='实测 ModelForm.save(commit=False):不发任何查询、返回 pk=None 的对象;多对多要等 save_m2m();忘了 save_m2m() 时多对多悄悄丢失且不报错;标准写法是补上服务端字段后 save() 再 save_m2m()。',
    lead='commit=False 让你在保存前补几个服务端字段,但它有一个经典的坑:多对多。这篇看它到底做了什么、没做什么,并复现那个不会报错的数据丢失。',
    facts=[('0 次查询', 'save(commit=False) 不写库,pk 为 None'), ('静默丢失', 'commit=False 后忘了 save_m2m(),多对多不写、也不报错'), ('save_m2m', '是 save(commit=False) 时挂到表单对象上的方法')],
    body=[
        sec('commit=True', '', term('', blk('d65', 1)), '<p>普通路径:<code>form.save()</code> 一步到位。</p>'),
        sec('commit=False', '', term('', blk('d65', 2)), '<p>返回的是一个还没有主键的对象,所以多对多关系此刻不可能写。Django 把「稍后补写多对多」的动作打包成 <code>form.save_m2m</code>。</p>'),
        sec('忘了 save_m2m', '', term('', blk('d65', 3)), '<p>这个 bug 只在使用多对多的表单上出现,而且不会抛异常。代码审查时看到 <code>commit=False</code> 就要找 <code>save_m2m()</code>。</p>'),
        sec('标准写法', '', term('', blk('d65', 4)), '<p>如果只是想补一个字段,还有另一种写法:重写 <code>form.save()</code> 或在 <code>form.instance</code> 上先设置字段再 <code>form.save()</code>(本文没有测)。</p>'),
        sec('分步演示:commit=False', '', demo('commit=False', [('t', 'term', '实测输出'), ('n', 'flow', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:PostgreSQL 上多对多写入的 SQL、commit=False 与 inline formset 的组合、instance 在 form.instance 上预先设置字段的写法'],
)

from lib import *
R = J('d16'); pf = R['perf']; Ns = sorted(pf, key=int)
F = R['forms'].splitlines()
steps = [
    step("reverse('post', args=[5]) 与 kwargs={'pk': 5}、甚至 args=['5'] 都得到 /post/5/;args=['abc'](不符合 <int:pk>)、不传参数、多传参数、多传 kwargs,全都是 NoReverseMatch,并且报错里会列出「已尝试的模式」。", t=tl(F[:7], cur=[0, 1, 2], mark=[3, 4, 5, 6]), kv=KV([['规则', '参数必须能匹配模式的正则']], ['规则'])),
    step("转换器的 to_url:自定义 yyyy 转换器 to_url 补零,year=7 → /arch/0007/;slug 转换器不接受 'a b/é' → NoReverseMatch;path 转换器允许 /,空格被编码成 %20:/files/a%20b/c%20d.txt。", t=tl(F[7:12], cur=[2, 3, 4], mark=[0]), kv=KV([['to_url', '反向时把值转成字符串,并校验']], ['to_url'])),
    step("同名多个模式:opt 有无参数两个模式,按传入参数选合适的那个;两条同名同参数的模式(dup/one/ 与 dup/two/),reverse('dup') 得到后定义的 /dup/two/。命名空间:v1:users、v2:user 各走自己的前缀;不指定实例命名空间的 api:users 会按默认规则,加 current_app='v2' 可指定。", t=tl(R['names'].splitlines(), cur=[0, 1, 2, 3, 4], mark=[2]), kv=KV([['同名同参数', '后定义的胜出'], ['命名空间', 'current_app 选实例']], ['同名同参数'])),
    step("reverse 的代价:第一次调用要构建反向字典,urlconf 越大越慢——" + ';'.join(f"N={n}:{pf[n][0]:.1f} ms" for n in Ns) + f";之后每次约 {pf[Ns[0]][1]:.1f} µs,与 N 无关(N={Ns[-1]} 时 {pf[Ns[-1]][1]:.2f} µs)。", b=bars([[f'N={n} 第一次(ms)', pf[n][0], f"{pf[n][0]:.1f}"] for n in Ns], pf[Ns[-1]][0] * 1.1, mark=[len(Ns) - 1]), kv=KV([['第一次', '建反向字典,一次性代价'], ['之后', f"≈{pf[Ns[0]][1]:.1f} µs / 次"]], ['第一次'])),
]
A = dict(
    n=16, series='django', tags='Django,URL,reverse,真实验证,动画演示',
    desc=f'实测 reverse():args / kwargs / 字符串参数的行为与 NoReverseMatch 的报错原文;自定义转换器的 to_url;同名同参数时后定义的胜出;命名空间;第一次调用要建反向字典(N={Ns[-1]} 时 {pf[Ns[-1]][0]:.0f} ms),之后每次约 {pf[Ns[-1]][1]:.1f} µs。',
    lead='reverse() 是把视图名变回 URL 的那半边。它有哪些行为你以为知道、其实没验证过:参数类型怎么校验、同名怎么选、命名空间怎么解析、第一次调用有多贵?这篇逐条实测。',
    facts=[('校验', '反向时参数也要能匹配模式的正则:int 路径传 "abc" 会 NoReverseMatch'), ('后定义的胜出', '两条同名同参数的模式,reverse 返回后定义的那条'), (f'{pf[Ns[-1]][0]:.0f} ms → {pf[Ns[-1]][1]:.1f} µs', f'N={Ns[-1]} 个命名路由时 reverse 第一次 vs 之后每次的耗时')],
    body=[
        sec('参数与转换器', '', term('', blk('d16', 1)), '<p>报错信息里有「已尝试的模式」和你传入的参数,基本足够定位。注意 <code>args=[\'5\']</code>(字符串)也能反向出 <code>/post/5/</code>——因为反向时是用模式的正则去匹配参数的字符串形式。</p>'),
        sec('同名与命名空间', '', term('', blk('d16', 2)), '<p>同一个 name 出现多次是允许的:Django 会按你传入的参数找能匹配的那条(<code>opt</code> 的两个模式)。如果两条都能匹配,后定义的胜出——所以给不同页面起同一个 name 是个静悄悄的 bug。</p>'),
        sec('代价', '', term('', blk('d16', 3)), '<p>第一次 <code>reverse()</code> 会构建整个 urlconf 的反向字典(与路由数量成正比),之后每次调用几乎是常数。这也是 Django 进程「第一个请求慢一点」的来源之一。</p>'),
        sec('分步演示:reverse 的规则', '', demo('reverse()', [('t', 'term', '结果'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。耗时为进程内调用,每种规模取 5 轮里最快的一轮', '没有验证:reverse_lazy、i18n 前缀下的 reverse、include() 深层嵌套与 namespace 冲突、reverse 结果与反向 resolve 的往返一致性(除本文几个例子)'],
)

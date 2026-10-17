from lib import *
R = J('d15'); pf = R['perf']; Ns = sorted(pf, key=int)
steps = [
    step("urlpatterns 从上到下逐个尝试,第一个匹配的胜出:/a/5/ → a_int;/a/new/ 虽然也符合 <str:s>,但写在前面的 a/new/ 先匹配,得到 a_new;/a/abc/ → a_str。同名路径重复写(/first/ 两条),后一条永远到不了。", t=tl(R['resolve'].splitlines()[:5] + [R['resolve'].splitlines()[5]], cur=[0, 1, 2], mark=[4, 5]), kv=KV([['规则', '第一个匹配的胜出'], ['遮蔽', '后面的同名模式永远匹配不到']], ['遮蔽'])),
    step("转换器的边界:<slug:> 拒绝空格;<path:> 可以匹配含 / 的内容;<uuid:> 只认合法 UUID(kwargs 里直接是 UUID 对象);<str:> 不匹配 /;re_path 没有转换器,year 是字符串 '2026'。/a/5(无结尾斜杠)是 Resolver404——匹配本身不管斜杠补全。", t=tl(R['resolve'].splitlines()[6:13], cur=[0, 2, 4, 5], mark=[1, 3, 6]), kv=KV([['转换器', '决定能匹配什么,也决定 kwargs 的类型']], ['转换器'])),
    step("include() 的 ResolverMatch:route = api/v1/users/<int:pk>/,url_name = user,namespace = 'v1',app_names = ['api'],view_name = v1:user。路径前缀一路累加。", t=tl(R['match'].splitlines(), cur=[1, 2, 3, 4, 6]), kv=KV([['view_name', 'v1:user'], ['namespace / app_names', "v1 / ['api']"]], ['view_name'])),
    step("结尾斜杠不属于匹配:GET /a/new → 301 到 /a/new/(CommonMiddleware + APPEND_SLASH),查询串保留;POST /a/new(DEBUG=False)也是 301——请求体被悄悄丢掉。DEBUG=True 时同一个请求直接抛 RuntimeError,提醒你表单该指向带斜杠的地址。", n=fl([['GET /a/new', '301 → /a/new/'], ['GET /a/new?x=1', '301 → /a/new/?x=1'], ['POST /a/new(DEBUG=False)', '301(体丢失)'], ['POST /a/new(DEBUG=True)', 'RuntimeError']], done=[0, 1], mark=[2, 3]), kv=KV([['POST 无斜杠', 'DEBUG=False 静默重定向']], ['POST 无斜杠'])),
    step("匹配是线性扫描:" + ';'.join(f"N={n}:第 1 个 {pf[n][0]:.1f} µs,最后一个 {pf[n][2]:.0f} µs,不匹配 {pf[n][3]:.0f} µs" for n in Ns[1:]) + "。第一个模式的耗时与 N 无关,越靠后越慢,404 的耗时和匹配最后一个相当。", b=bars([[f'N={n} 匹配最后一个(µs)', pf[n][2], f"{pf[n][2]:.0f}"] for n in Ns], pf[Ns[-1]][2] * 1.1, mark=[len(Ns) - 1]), kv=KV([['结论', 'urlpatterns 很长时,常用路由放前面']], ['结论'])),
]
A = dict(
    n=15, series='django', tags='Django,URL,路由,真实验证,动画演示',
    desc=f'实测 Django URL Resolver:第一个匹配的模式胜出、转换器的边界、include() 的命名空间;APPEND_SLASH 下 POST 无斜杠在 DEBUG=False 时静默 301 丢体;匹配是线性扫描(N=5000 时匹配最后一个 {pf[Ns[-1]][2]:.0f} µs)。',
    lead='请求进来之后,Django 怎么在 urlpatterns 里找到视图?顺序有多重要?模式多了会不会慢?这篇不靠文档,用真实的路由表逐条试,并量了不同长度路由表下的匹配耗时。',
    facts=[('第一个胜出', '按 urlpatterns 顺序,第一个匹配的模式生效,后面同名的永远到不了'), ('POST 无斜杠', 'APPEND_SLASH 下 DEBUG=False 时是 301(请求体丢失),DEBUG=True 才抛 RuntimeError'), (f'{pf[Ns[-1]][2]:.0f} µs', f'{Ns[-1]} 个 path() 的路由表里匹配最后一个的耗时(第一个仅 {pf[Ns[-1]][0]:.1f} µs)')],
    body=[
        sec('顺序与转换器', '', term('', blk('d15', 1)), '<p>同一个 URL 可能符合多个模式,顺序决定结果:把具体的(<code>a/new/</code>)放在通用的(<code>a/&lt;str:s&gt;/</code>)之前。转换器既限定匹配范围,也决定 kwargs 里的类型。</p>'),
        sec('ResolverMatch 与命名空间', '', term('', blk('d15', 2)), '<p><code>resolve()</code> 返回的 <code>ResolverMatch</code> 记录了完整的 <code>route</code>(所有 include 前缀累加后的样子)、<code>url_name</code>、<code>namespace</code>、<code>app_names</code>。</p>'),
        sec('结尾斜杠', '', term('', blk('d15', 3)), '<p><code>CommonMiddleware</code> 在响应阶段发现 404 且 <code>APPEND_SLASH=True</code>、补一个斜杠就能匹配时,返回 301。GET 没问题;POST 的请求体在重定向中丢失——DEBUG=True 时 Django 用一个 <code>RuntimeError</code> 提醒你,DEBUG=False 时不提醒。</p>'),
        sec('匹配的代价', '', term('', blk('d15', 4)), '<p>每种规模量最快的一次(5 轮取最小值)。第一个模式的耗时和总数无关(≈4 µs),越靠后越慢,404 与匹配最后一个几乎一样——因为都要把整张表扫完。对大多数项目这不是瓶颈,但路由表上千条、并且热点路由排在后面时值得调整。(这里是 <code>path()</code> 且没有 <code>include()</code> 分层;分层会缩短每次要扫描的范围,本文没有测。)</p>'),
        sec('分步演示:路由匹配', '', demo('URL Resolver', [('t', 'term', '结果'), ('n', 'flow', '请求'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。计时是进程内调用 django.urls.resolve(不含网络与中间件);取 5 轮里最小的一轮', '没有验证:include() 分层对匹配耗时的影响、re_path 的性能与 path 的对比、i18n_patterns / 国际化 URL、404 页面(DEBUG=True)列出已尝试模式的行为'],
)

from lib import *
S = SS('f25')
R = J('f25')
steps = [
    step("endpoint 冲突:两个同名函数都被 @app.route 注册,第二个抛 AssertionError「View function mapping is overwriting an existing endpoint function: page」。同一个函数对象用同一个 endpoint 注册第二个 URL 是允许的。", t=tl(S(1)), mark=lidx(S(1), 'AssertionError'), done=lidx(S(1), '同一个函数对象'), kv=KV([['两个不同函数同名', 'AssertionError'], ['同一函数多个 URL', '允许']], ['两个不同函数同名'])),
    step("规则冲突:同一个 URL /x 被两个不同端点 first、second 注册,没有任何报错;GET /x 总是 first,规则列表里两条都在 [('/x', 'first'), ('/x', 'second')]。先注册的永远赢,第二条是死代码。", t=tl(S(2)), mark=lidx(S(2), 'GET /x → first'), kv=KV([['注册', '两条都成功,无报错'], ['GET /x', 'first(先注册的)']], ['GET /x'])),
    step("应用路由与蓝图路由重名:先注册应用路由、后注册蓝图,GET /hello 得到「from app」;反过来先注册蓝图再注册应用路由,得到「from bp」。同样是谁先注册谁生效,与它们是应用还是蓝图无关。", t=tl(S(3)), done=lidx(S(3), '先注册应用路由', '先注册蓝图'), kv=KV([['先应用后蓝图', 'from app'], ['先蓝图后应用', 'from bp']], ['先蓝图后应用'])),
    step("同一个蓝图用两个前缀注册两次:第二次抛 ValueError「The name 'multi' is already registered for this blueprint. Use 'name=' to provide a unique name.」;给第二次加 name='multi_v2' 后 /v1/ping 与 /v2/ping 都是 200,endpoint 是 multi.ping 与 multi_v2.ping。", t=tl(S(4)), mark=lidx(S(4), 'ValueError'), done=lidx(S(4), '加 name='), kv=KV([['同名蓝图再注册', 'ValueError'], ['加 name=', 'multi.ping 与 multi_v2.ping']], ['同名蓝图再注册'])),
    step("通配路由 /<path:p> 不会吃掉更具体的路由:/about 与 /api/users 仍然进入各自的视图(about、users),/api/x 与 /zzz/yyy 才被通配路由接住(catch:api/x、catch:zzz/yyy)。与注册顺序无关,见第 17 篇。", t=tl(S(5)), done=lidx(S(5), "'/about': 'about'"), kv=KV([['/about、/api/users', '具体路由'], ['/api/x、/zzz/yyy', '通配路由']], ['/api/x、/zzz/yyy'])),
    step("启动时检查冲突的小脚本:遍历 url_map,把参数名归一化后按(模式,方法)分组,发现 x1 与 x3 都是 GET /x → 报告 ('/x', 'GET', 'x1', 'x3');POST 的 x2 没有冲突。局限:/u/<int:i> 与 /u/<name> 因参数名不同归一化后模式不同,没有被报出来,所以这个脚本只能找「模式与方法完全相同」的冲突。", t=tl(S(6)), mark=lidx(S(6), '冲突检查结果'), kv=KV([['发现', "('/x', 'GET', 'x1', 'x3')"], ['局限', '只能找模式与方法完全相同的']], ['局限'])),
    step("flask routes --sort 可以排序:--sort endpoint 的端点顺序是 alpha、alpha_post、static、zeta(按端点名);--sort rule 是 alpha、alpha_post、zeta、static(按规则字符串 /a、/a、/b、/static/…);--sort methods 是 static、zeta、alpha、alpha_post。把路由列表排序后重复的 URL 会挨在一起,便于肉眼检查。", t=tl(S(7)), done=lidx(S(7), '--sort endpoint', '--sort rule', '--sort methods'), kv=KV([['--sort endpoint', '按端点名'], ['--sort rule', '按 URL 规则']], ['--sort rule'])),
]
A = mkartf('f25', 25, 'Flask,路由冲突,endpoint,蓝图,真实验证,动画演示',
    '实测 Flask 路由冲突:同名 endpoint 会 AssertionError;同一 URL 被不同端点注册不会报错、先注册的赢(应用与蓝图也一样);同蓝图多次注册要 name=;通配路由不吃具体路由;一个检查重复(模式+方法)的脚本;flask routes --sort。',
    '两个路由的 URL 一样会怎样?endpoint 重名会怎样?应用和蓝图抢同一个地址谁赢?这篇把几种冲突都造出来,并给出启动时检查的办法。',
    [('先注册赢', '同一 URL 被不同端点注册时的结果(应用或蓝图都一样)'), ('AssertionError', '不同函数同 endpoint 时的报错'), ('ValueError', '同一蓝图不加 name= 注册两次时的报错')],
    [('endpoint 冲突', '<p>上一篇:<a href="flask-options-head-auto.html">OPTIONS 与 HEAD 自动处理</a>;下一篇:<a href="flask-blueprint-routes.html">Blueprint 路由注册</a>;匹配优先级:<a href="flask-url-rule-matching-order.html">URL Rule 与路由匹配顺序</a>。</p>'), ('规则冲突', None), ('应用与蓝图', None), ('同一蓝图注册两次', None), ('通配路由', None), ('启动时检查', None), ('flask routes --sort', None)],
    steps, [ENV_F, '没有验证:subdomain / host_matching 下的冲突、方法集合部分重叠(如一条 GET、一条 GET+POST)时的优先、第三方扩展(如 Flask-RESTful)注册路由时的冲突提示', '启动时检查的脚本是本篇自己写的简化版,不是 Flask 内置功能'], '路由冲突')

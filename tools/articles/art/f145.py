from lib import *
S = SS('f145')
R = J('f145'); tk = R['token']; nop, pre = tk['不加 --preload'], tk['--preload']
steps = [
    step(f"gunicorn 起 4 个 worker 进程,每个进程有自己的一份模块级全局变量。发 40 次 POST /inc(每次把进程内的 COUNT 加 1,同时给 redis 的计数 INCR),请求落在各进程的次数是 {R['inc_dist']}(分布不均匀,4 个进程都有请求)。再读 20 次 /count:读到的进程内计数只有 {R['local_values']} 这几种值(各进程各自的计数,谁也不等于 40);而 redis 里共享的计数始终是 {R['shared']}。同一个接口连续请求,返回值取决于落到哪个进程。", b=bars([['进程内计数(某进程)', R['local_values'][0], str(R['local_values'][0])], ['进程内计数(另一进程)', R['local_values'][-1], str(R['local_values'][-1])], ['redis 共享计数', R['shared'][0], str(R['shared'][0])]], 40, mark=[0, 1], done=[2]), t=tl(S(1)), mark=lidx(S(1), '全局计数'), done=lidx(S(1), '共享的计数'), kv=KV([['进程内全局变量', '每个进程一份,互不可见'], ['redis 计数', '所有进程共享,总是 40']], ['进程内全局变量'])),
    step(f"模块导入时算一次的值(随机数 STARTUP_TOKEN):默认每个 worker 各自导入应用,看到 {nop[0]} 个进程,{nop[1]} 个不同的值;加 --preload 让 master 在 fork 之前先导入一次,{pre[0]} 个进程看到 {pre[1]} 个值(fork 出来的子进程继承同一份)。--preload 能省启动时间与内存(写时复制),但在 fork 之前建立的连接、线程、随机数种子会被所有 worker 共享,要放到 worker 启动之后(post_fork)初始化。", t=tl(S(2)), mark=lidx(S(2), '不加 --preload'), done=lidx(S(2), '--preload    '), kv=KV([['不加 --preload', '每个 worker 各自导入,值各不相同'], ['--preload', 'fork 前导入一次,值相同']], ['--preload'])),
    step(f"进程内缓存:同一个 key 请求 40 次,「现算」了 {R['cache']} 次——每个进程第一次碰到这个 key 各算一次,期望只算 1 次。进程内的 dict 缓存在多进程部署下命中率比想象的低,而且各进程缓存的内容在更新时不会同步(失效要通知所有进程),需要共享缓存(第 75 篇的 RedisCache)。", t=tl(S(3)), done=lidx(S(3), '现算'), kv=KV([['进程内缓存', f"{R['cache']} 个进程各算一次"], ['对策', '共享缓存(redis)']], ['进程内缓存'])),
    step("要让所有进程一致,把状态放到进程外面:redis 的 INCR 是原子的,4 个进程各自 INCR,读到的是同一个总数 40(第一节里 redis 共享计数始终等于 40)。数据库、redis、文件锁都可以;进程内的 threading.Lock 只在本进程内有效(第 143 篇),挡不住别的进程。", t=tl(S(4)), done=lidx(S(4), 'redis'), kv=KV([['进程外的状态', 'redis / 数据库'], ['threading.Lock', '只在一个进程内有效']], ['进程外的状态'])),
]
A = mkartf('f145', 145, 'Flask,多进程,全局变量,gunicorn,preload,真实验证,动画演示',
    f'实测多进程下的全局变量:4 个 worker 各有一份模块级计数(读到的值取决于落到哪个进程)而 redis 计数始终是 40、--preload 让导入时算的随机值从 {nop[1]} 个变成 {pre[1]} 个、进程内缓存同一个 key 被 {R["cache"]} 个进程各算一次。',
    'Flask 部署成多个进程之后,模块里的全局变量还可靠吗?--preload 改变了什么?进程内缓存的命中率会怎样?这篇用 4 个 gunicorn worker 与自己起的 redis,把每种现象量出来。',
    [(f'{R["local_values"][0]}、{R["local_values"][-1]} 对 40', '读到的进程内计数与真实总数(redis 里是 40)'), (f'{nop[1]} → {pre[1]}', '--preload 前后,模块导入时算出的随机值的不同个数(4 个进程)'), (f'{R["cache"]} 次', '同一个 key 的进程内缓存被「现算」的次数(期望 1 次)')],
    [('每个进程一份全局变量', '<p>上一篇:<a href="flask-gunicorn-worker-types.html">Gunicorn Worker 类型</a>;下一篇:<a href="flask-background-thread-app-context.html">后台线程与 Application Context</a>。</p><p>redis 是自己在非默认端口起的临时实例,验证完就关闭了。</p>'), ('导入时算的值与 --preload', None), ('进程内缓存', None), ('放到进程外面', None)],
    steps, [ENV_F + '。gunicorn sync worker、redis-py 8.1.0、自己起的 redis', '没有验证:uwsgi 的 lazy-apps、preload 下数据库连接在 fork 之后的问题(第 91 篇的连接池)、multiprocessing 共享内存、文件锁、更多 worker 数量下的分布'], '多进程下的全局变量')

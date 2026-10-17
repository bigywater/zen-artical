from lib import *
R = J('d14'); rs = R['runserver']; rq = R['ready_query']; cm = R['cmds']
rsd = rs['runserver(默认,自动重载)']; rsn = rs['runserver --noreload']
steps = [
    step("ready() 按 INSTALLED_APPS 的顺序逐个调用:a.ready() 先于 b.ready(),而 a.ready() 被调用时 b 的模型已经加载(models_ready = True),但整个注册表的 apps.ready 还是 False。", t=tl([l.split(' ', 1)[1] for l in R['order']], cur=[0, 1]), kv=KV([['调用顺序', 'INSTALLED_APPS 顺序'], ['调用时', '所有模型已加载']], ['调用顺序'])),
    step(f"每个 manage.py 命令都会走到 ready():check、showmigrations、makemigrations、test、help 各触发 {sorted(set(cm.values()))[0]} 次。所以 ready() 里的代码在任何命令下都会执行,包括你只想看 --help 的时候。", b=bars([[k, v, str(v)] for k, v in cm.items()], 2, done=list(range(len(cm)))), kv=KV([['命令', '都会触发 ready() 一次']], ['命令'])),
    step(f"runserver 默认带自动重载,会启动两个进程:ready() 被调用 {rsd['ready']} 次、来自 {rsd['pids']} 个不同的进程;urls 只在处理请求的子进程里导入 {rsd['urls']} 次。--noreload 时只有 {rsn['ready']} 次、{rsn['pids']} 个进程。", b=bars([['runserver 默认', rsd['ready'], str(rsd['ready'])], ['runserver --noreload', rsn['ready'], str(rsn['ready'])]], 2, mark=[0], done=[1]), kv=KV([['runserver 默认', f"ready() {rsd['ready']} 次 / {rsd['pids']} 个进程"], ['--noreload', f"{rsn['ready']} 次"]], ['runserver 默认'])),
    step("在 ready() 里查数据库,而表还不存在:全新数据库上 python manage.py migrate 直接失败,check 也失败,报 " + rq['last'].split(': ', 1)[1] + "——因为 migrate 命令本身就要先走 ready(),而表要靠 migrate 建。", n=fl([['python manage.py migrate', 'setup() → ready()'], ['ready() 里 Item.objects.count()', 'no such table'], ['migrate', '还没来得及建表']], mark=[1]), kv=KV([['结果', rq['last'][-40:]]], ['结果'])),
]
A = dict(
    n=14, series='django', tags='Django,AppConfig,ready,真实验证,动画演示',
    desc=f'实测 AppConfig.ready():按 INSTALLED_APPS 顺序调用、调用时所有模型已加载;所有 manage.py 命令都会触发;runserver 默认自动重载会调用 {rsd["ready"]} 次(来自 {rsd["pids"]} 个进程);在 ready() 里查还不存在的表会让 migrate 自己失败。',
    lead='ready() 是放信号注册、启动检查的标准位置,但它被调用的时机比想象中多:每条管理命令、runserver 的两个进程。这篇把这些情形逐个数出来,并复现最常见的坑——在 ready() 里查数据库。',
    facts=[('顺序', '按 INSTALLED_APPS 顺序调用;调用时所有 app 的模型都已加载'), (f'{rsd["ready"]} 次', f'runserver 默认(自动重载)下 ready() 的调用次数,来自 {rsd["pids"]} 个进程'), ('migrate 也会失败', 'ready() 里查还没建的表,连 migrate 自己都跑不起来')],
    body=[
        sec('调用的时机与顺序', '', term('', blk('d14', 1)), '<p>两个 app a、b,各自的 <code>ready()</code> 打点。a 先、b 后;a 的 <code>ready()</code> 里 b 的模型已经加载。<code>apps.ready</code> 要等所有 <code>ready()</code> 都跑完才变 True。</p>'),
        sec('哪些命令会触发', '', term('', blk('d14', 2)), '<p>每个命令启动时都会 <code>django.setup()</code>,所以 <code>ready()</code> 里的耗时或副作用在任何命令下都发生。</p>'),
        sec('runserver 为什么执行两次', '', term('', blk('d14', 3)), f'<p>默认的自动重载让 <code>runserver</code> 启动一个监视进程和一个真正服务的子进程,两个进程都会 <code>django.setup()</code>,所以 <code>ready()</code> 里的一次性逻辑(比如启动后台线程、发通知)会执行 {rsd["ready"]} 次。<code>--noreload</code> 只有一次。用 gunicorn 多个 worker 时每个 worker 进程各一次(本文没有测)。</p>'),
        sec('在 ready() 里查数据库', '', term('', blk('d14', 4)), '<p>这是最常见的坑:<code>ready()</code> 里 <code>Item.objects.count()</code> 在全新数据库上会让 <code>migrate</code> 报错。ready() 里应避免访问数据库;确实需要,放到信号、第一次请求、或独立的管理命令里。</p>'),
        sec('分步演示:ready() 何时被调用', '', demo('AppConfig.ready()', [('t', 'term', '事件'), ('b', 'bars', '次数'), ('n', 'flow', '过程'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。runserver 的次数通过在 ready() 里向日志文件追加 pid 统计', '没有验证:gunicorn / uvicorn 多 worker 下的次数、ready() 里访问数据库时 Django 6.1 是否还会给出运行时警告(这次实验只看到了报错)、ready() 抛异常时各命令的行为'],
)

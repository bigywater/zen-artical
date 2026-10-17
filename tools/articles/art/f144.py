from lib import *
S = SS('f144')
R = J('f144'); b = R['bench']; sl = R['slow']
k = list(b); sy, gt, ge = b[k[0]], b[k[1]], b[k[2]]
ks = list(sl)
steps = [
    step(f"三种 worker 类型,总共 4 个「槽位」的大致对等配置(sync×4;gthread 2 个 worker × 8 线程;gevent 2 个 worker),ApacheBench 本机压测(每项只测一次,压测工具同机运行)。空闲内存:sync×4 {sy['mem']:.0f} MB({sy['nproc']} 个进程含 master)、gthread {gt['mem']:.0f} MB({gt['nproc']} 个)、gevent {ge['mem']:.0f} MB({ge['nproc']} 个)。/hello 32 并发:{sy['hello']:.0f}、{gt['hello']:.0f}、{ge['hello']:.0f} 请求/秒,轻量请求上差别不大。/wait(每个请求等 0.5 秒,128 个、64 并发):{sy['wait']:.0f}、{gt['wait']:.0f}、{ge['wait']:.0f} 请求/秒——等待型负载上并发度决定一切:sync 只有 4 个并发,gthread 16 个,gevent 受连接数限制(这里 83)。keep-alive:sync 不支持(keep-alive 请求数 {sy['keepalive']}),gthread 与 gevent 都支持({gt['keepalive']}、{ge['keepalive']})。", b=bars([['sync×4', sy['wait'], f"{sy['wait']:.0f}"], ['gthread 2×8', gt['wait'], f"{gt['wait']:.0f}"], ['gevent×2', ge['wait'], f"{ge['wait']:.0f}"]], ge['wait'], mark=[0], done=[1, 2]), t=tl(S(1)), done=lidx(S(1), 'gthread', 'gevent'), mark=lidx(S(1), 'sync × 4'), kv=KV([['/hello', f"{sy['hello']:.0f} / {gt['hello']:.0f} / {ge['hello']:.0f} 请求/秒"], ['/wait 0.5 秒', f"{sy['wait']:.0f} / {gt['wait']:.0f} / {ge['wait']:.0f} 请求/秒"], ['keep-alive', 'sync 不支持']], ['/wait 0.5 秒'])),
    step(f"慢客户端:一个连接把请求头发到一半就不动了(没有发完)。每种只开 1 个 worker 看最清楚:sync 的这个 worker 被那个半截连接占住,另一个正常请求等了 10 秒超时(TimeoutError);gthread(8 线程)与 gevent 里,同样的正常请求只用 {sl[ks[1]].split('用时 ')[1]} 与 {sl[ks[2]].split('用时 ')[1]}。这就是 sync worker 前面必须放 nginx 之类反向代理(它会缓冲完整请求再转发)的原因,也是直接把 sync worker 暴露在公网上的风险。", t=tl(S(2)), mark=lidx(S(2), 'sync × 1'), done=lidx(S(2), 'gthread', 'gevent'), kv=KV([['sync', '慢客户端会占住 worker'], ['gthread / gevent', '只占一个线程或 greenlet']], ['sync'])),
]
A = mkartf('f144', 144, 'Flask,gunicorn,worker,sync,gthread,gevent,真实验证,动画演示',
    f'实测 gunicorn 的三种 worker 类型:总共 4 个槽位的配置下 /wait 等待型负载 sync {sy["wait"]:.0f}、gthread {gt["wait"]:.0f}、gevent {ge["wait"]:.0f} 请求/秒,空闲内存、keep-alive 支持情况,以及一个发了一半请求头的慢客户端会让 sync worker 完全卡住而其它两种不受影响。',
    'gunicorn 的 sync、gthread、gevent 到底怎么选?等待型与轻量请求的差别有多大?为什么 sync worker 前面一定要有反向代理?这篇在同样的槽位数下把三种类型的并发、内存与慢客户端的表现对照出来。',
    [(f'{sy["wait"]:.0f} / {gt["wait"]:.0f} / {ge["wait"]:.0f}', '/wait 等待型负载的请求/秒:sync×4、gthread 2×8、gevent×2'), ('10 秒超时', '一个卡着的慢连接让 sync 单 worker 无法处理其它请求'), ('keep-alive', 'sync worker 不支持,gthread 与 gevent 支持')],
    [('三种类型的对比', '<p>上一篇:<a href="flask-thread-local-isolation.html">Thread Local 与请求隔离</a>;下一篇:<a href="flask-multiprocess-globals.html">多进程下的全局变量</a>。</p><p>压测用系统自带的 ApacheBench,与被测服务同机运行,每个数字只测一次,只看相对关系。进程数包含 master 进程。</p>'), ('慢客户端', None)],
    steps, [ENV_F + '。gunicorn sync、gthread、gevent worker、ApacheBench', '没有验证:uvicorn-worker 与 eventlet worker、多次重复测量的方差、worker 的 max_requests 与 preload 的效果、--timeout 对慢客户端的处理、真实 nginx 在前面时 sync worker 的表现'], 'Gunicorn Worker 类型', panels=[('t', 'term', '实验输出'), ('b', 'bars', '请求/秒'), ('kv', 'kv', '要点')])

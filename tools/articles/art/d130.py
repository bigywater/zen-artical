from lib import *
R = J('d130'); c = R['conc']; tc = R['timeout_client']; g = R['graceful']; mr = R['maxreq']
def S(k): return [l for l in out('d130').split('== ')[k].splitlines()[1:] if l.strip()]
k1, k2 = list(c.keys())[0], list(c.keys())[3]
steps = [
    step("gunicorn(26.2.0)的默认值:workers=1、worker_class=sync、threads=1、timeout=30 秒、graceful_timeout=30 秒、keepalive=2 秒、max_requests=0(不回收)。默认是一个同步 worker——一次只处理一个请求。", t=tl(S(1)), done=[1], kv=KV([['workers', '1'], ['worker_class', 'sync'], ['timeout', '30 s']], ['workers'])),
    step(f"20 个并发请求、视图里 time.sleep(0.3):sync × 1 总耗时 {c['sync × 1(默认)']:.0f} ms(20 × 0.3 s 排队);sync × 4 {c['sync × 4']:.0f} ms;gthread 1 进程 × 8 线程 {c['gthread × 1 进程 × 8 线程']:.0f} ms;gthread 2 进程 × 8 线程 {c['gthread × 2 进程 × 8 线程']:.0f} ms。线程 worker 对「等 I/O」的请求收益很大。", t=tl(S(2)), b=bars([[k.split('(')[0], v, f'{v:.0f} ms'] for k, v in c.items()], 6200, mark=[0], done=[1, 2, 3]), kv=KV([['sync × 1', f"{c['sync × 1(默认)']:.0f} ms"], ['gthread 2 × 8', f"{c['gthread × 2 进程 × 8 线程']:.0f} ms"]], ['gthread 2 × 8'])),
    step(f"--timeout 2、视图 sleep 5 秒:日志出现 WORKER TIMEOUT,worker 被杀掉并换上新的;这个请求的客户端在约 {tc['ms']:.0f} ms 时收到 {tc['res']};之后的请求是 200(新 worker 已接手)。timeout 杀的是 worker 进程,不是那个请求。", t=tl(S(3)), mark=[0, 1], done=[2], kv=KV([['WORKER TIMEOUT', 'worker 被杀,重启'], ['客户端', tc['res']]], ['WORKER TIMEOUT'])),
    step(f"--max-requests 5:13 个串行请求里 worker pid 的序列是 {' → '.join(dict.fromkeys(mr['pids']))}(每 5 个请求换一个 worker,13 = 5 + 5 + 3),共 {mr['distinct']} 个不同的 worker 进程。用来定期回收有内存泄漏的 worker。", t=tl(S(4)), done=[0], kv=KV([['max_requests', '处理 N 个请求后回收 worker']], ['max_requests'])),
    step(f"优雅停止:视图还在处理一个 2 秒的请求时给主进程发 SIGTERM:这个在途请求仍然返回 {g['status']},主进程在 SIGTERM 之后约 {g['ms']:.0f} ms 退出,之后新连接被拒绝(ConnectionRefusedError)。", t=tl(S(5)), done=[0, 1], kv=KV([['SIGTERM', '等在途请求完成再退出'], ['之后', '拒绝新连接']], ['SIGTERM'])),
]
A = dict(
    n=130, series='django', tags='Django,gunicorn,WSGI,部署,worker,真实验证,动画演示',
    desc=f'gunicorn 26.2.0 默认 1 个 sync worker;20 个 0.3 s 的并发请求:sync×1 {c["sync × 1(默认)"]:.0f} ms、sync×4 {c["sync × 4"]:.0f} ms、gthread 2 进程×8 线程 {c["gthread × 2 进程 × 8 线程"]:.0f} ms;timeout 杀 worker(客户端收到 {tc["res"]});max-requests 按计数回收 worker;SIGTERM 会等在途请求完成。',
    lead='Django 上生产,最常见的 WSGI 服务器是 gunicorn。它的默认配置是什么?换 worker 类型、加进程能带来多大变化?timeout 与 max-requests 到底杀掉了什么?这篇起真实的 gunicorn 进程逐项量出来。',
    facts=[('默认 1 个 sync worker', f'20 个 0.3 s 的请求要 {c["sync × 1(默认)"]:.0f} ms'), (f'{c["gthread × 2 进程 × 8 线程"]:.0f} ms', '同样的请求,gthread 2 进程 × 8 线程'), ('SIGTERM', '等在途请求完成才退出,之后拒绝新连接')],
    body=[
        sec('默认值', '', term('', blk('d130', 1))),
        sec('worker 配置与并发', '', term('', blk('d130', 2)), '<p>视图里是 <code>time.sleep</code>(模拟等待数据库或外部接口)。如果视图是 CPU 密集的,线程并不会更快(受 GIL 限制,本文没有测)。本机 10 个 CPU 核;worker 数与核数的经验公式本文没有验证。</p>'),
        sec('timeout 杀的是什么', '', term('', blk('d130', 3)), '<p>worker 超过 <code>--timeout</code> 没有响应会被主进程杀掉重启,正在处理的请求随之失败。所以需要长耗时请求时,应该改成后台任务,而不是把 timeout 调得很大。</p>'),
        sec('max-requests', '', term('', blk('d130', 4))),
        sec('优雅停止', '', term('', blk('d130', 5)), '<p>部署时给 gunicorn 主进程发 SIGTERM,在途请求有 <code>graceful_timeout</code> 时间完成;本文只验证了「在途请求完成」,没有验证超过 graceful_timeout 时的强杀。</p>'),
        sec('分步演示', '', demo('gunicorn 的行为', [('t', 'term', '输出'), ('b', 'bars', '总耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。gunicorn 26.2.0(当前安装版本);视图里 time.sleep 模拟等待;并发请求由本机线程发出;各配置只测一次', '没有验证:gevent / uvicorn worker(见第 131 篇)、--preload 的内存共享、HUP 热重载、CPU 密集型视图、Unix socket、nginx 之后的 keepalive 配合、生产级别的压测'],
)

from lib import *
S = SS('f146')
R = J('f146'); st = R['stop']; dm, nd = st['daemon'], st['nondaemon']
steps = [
    step("新线程里没有应用上下文:读 current_app.name 与 db.session.execute 都抛 RuntimeError「Working outside of application context.」。线程是新的执行上下文,请求线程的上下文不会自动带过去。", t=tl(S(1)), mark=lidx(S(1), 'current_app.name', 'db.session.execute'), kv=KV([['新线程', '没有应用上下文']], ['新线程'])),
    step("在线程里自己 with app.app_context():读到 current_app.name = bg,数据库查询成功(1),has_app_context 在 with 里是 True、退出后是 False。线程里的 db.session 与请求线程里的不是同一个对象(各有各的 session,在各自的应用上下文结束时清理)。传给线程的必须是真实的 Flask 对象 current_app._get_current_object(),不能传 current_app 这个代理——代理到了线程里仍然找不到上下文。", t=tl(S(2)), done=lidx(S(2), 'current_app.name', 'query', 'has_app_context', 'after_exit', '不是同一个', '_get_current_object'), kv=KV([['with app.app_context()', '线程自己推入上下文'], ['db.session', '线程里独立的 session'], ['传参', '传真实对象,不传代理']], ['with app.app_context()'])),
    step("线程里的异常:POST /fail 启动一个会抛 ValueError 的后台线程并立即返回,响应是 200 {ok: true};异常没有经过 Flask 的错误处理器(即使注册了 errorhandler(Exception)),只在服务器日志里出现「Exception in thread Thread-1 (failing):」加堆栈。后台任务的失败要在线程函数里自己捕获并记录,否则调用方永远不知道。", t=tl(S(3)), done=lidx(S(3), 'POST /fail', '响应是 200'), kv=KV([['线程里抛异常', '只在服务器日志里,不经过 errorhandler']], ['线程里抛异常'])),
    step(f"worker 被优雅停止时:任务要 3 秒,启动 1 秒后给 gunicorn master 发 SIGTERM(--graceful-timeout 10)。daemon 线程:master 在 SIGTERM 后 {dm[0]:.1f} 秒就退出,任务没有做完(False);非 daemon 线程:master 等了 {nd[0]:.1f} 秒,任务做完了(True)。每次发布、重启或 --max-requests 回收 worker,都会遇到这种情况:daemon 线程里的任务会被直接丢掉,非 daemon 线程会拖长关停时间(超过 graceful-timeout 就会被强杀)。需要可靠执行的任务不要放在 worker 里的线程,放到任务队列(见任务队列相关内容)。", b=bars([['daemon 线程', dm[0], f'{dm[0]:.1f} s,未完成'], ['非 daemon 线程', nd[0], f'{nd[0]:.1f} s,完成']], 3, mark=[0], done=[1]), t=tl(S(4)), mark=lidx(S(4), 'daemon     线程'), done=lidx(S(4), 'nondaemon'), kv=KV([['daemon', f'{dm[0]:.1f} 秒退出,任务丢失'], ['非 daemon', f'等到任务完成({nd[0]:.1f} 秒)']], ['daemon'])),
]
A = mkartf('f146', 146, 'Flask,后台线程,application context,gunicorn,真实验证,动画演示',
    f'实测后台线程与应用上下文:新线程里读 current_app 与查数据库抛 RuntimeError、在线程里推入应用上下文并传真实的 Flask 对象、线程里的异常只在日志里不经过 errorhandler、worker 优雅停止时 daemon 线程的任务被丢弃({dm[0]:.1f} 秒退出)而非 daemon 线程要等到完成({nd[0]:.1f} 秒)。',
    '在视图里起一个线程做后台工作,要注意什么?为什么读不到 current_app?线程里出错了谁知道?重启服务时线程里的任务会怎样?这篇用真实的 gunicorn 与 SIGTERM 把每个问题量出来。',
    [('RuntimeError', '新线程里访问 current_app 或 db.session 的结果'), (f'{dm[0]:.1f} / {nd[0]:.1f} 秒', 'SIGTERM 之后 master 退出的时间:daemon 线程与非 daemon 线程'), ('日志里', '后台线程抛出的异常出现的位置,不经过 errorhandler')],
    [('没有上下文的线程', '<p>上一篇:<a href="flask-multiprocess-globals.html">多进程下的全局变量</a>;下一篇:<a href="flask-request-timeout.html">请求超时</a>。</p>'), ('推入应用上下文', None), ('线程里的异常', None), ('停止 worker 时的线程', '<p>用 gunicorn gthread worker,SIGTERM 发给 master 进程,--graceful-timeout 设为 10 秒。</p>')],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、gunicorn gthread', '没有验证:Celery 等任务队列的上下文处理、线程池 ThreadPoolExecutor 的行为、--max-requests 回收 worker 时的线程、超过 graceful-timeout 后被强杀的表现、数据库连接在线程结束时的归还'], '后台线程与 Application Context')

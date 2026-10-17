from lib import *
S = SS('c68')
steps = [
    step("Python 脚本每秒 print 一行共 5 行,再睡 5 秒才退出(总共约 10 秒)。默认(stdout 是管道,不是 TTY):docker logs 里第一行在 10.3 秒才出现,第 3 秒时看到 0 行——print 的内容被缓冲到进程退出才写出;python -u 第 0.2 秒就出现、第 3 秒看到 4 行;PYTHONUNBUFFERED=1 在 0.1 秒、4 行;print(…, flush=True) 在 0.2 秒、4 行;docker run -t 分配 TTY 后在 0.1 秒、4 行。", t=tl(S(1)), done=lidx(S(1), 'python -u', 'PYTHONUNBUFFERED=1', 'flush=True', 'docker run -t'), mark=lidx(S(1), '默认(不是 TTY)'), b=bars([['默认:第一行出现 (秒)', 10.3, '10.3'], ['python -u (秒)', 0.2, '0.2'], ['PYTHONUNBUFFERED=1 (秒)', 0.1, '0.1'], ['docker run -t (秒)', 0.1, '0.1']], 10.3, done=[1, 2, 3], mark=[0]), kv=KV([['默认(管道)', '块缓冲,10.3 秒后才看到'], ['-u / PYTHONUNBUFFERED / flush=True', '立刻看到'], ['-t(TTY)', '行缓冲,立刻看到']], ['默认(管道)'])),
    step("stderr 默认不缓冲:往 sys.stderr 每秒 print 一行,docker logs 在 0.1 秒就看到第一行,第 3 秒看到 3 行。", t=tl(S(2)), done=lidx(S(2), 'print 到 sys.stderr'), kv=KV([['stderr', '不缓冲,立刻出现']], ['stderr'])),
    step("缓冲区多大:每 0.02 秒 print 一行 100 字节(每秒约 5000 字节),不 flush:第一次在 docker logs 里看到输出是 1.7 秒时,当时已有 8100 字节——81 行写完,再来一行就超过 8192 字节,于是整块写出。", t=tl(S(3)), done=lidx(S(3), '8100 字节'), b=bars([['第一次出现时的字节数', 8100, '8100'], ['Python 缓冲区 (字节)', 8192, '8192']], 8192, done=[0], mark=[1]), kv=KV([['出现时机', '约 1.7 秒,累计 8100 字节'], ['缓冲区', '约 8192 字节']], ['出现时机'])),
    step("同样的输出用 sh 的 echo 来写:第一行 0.1 秒就出现在 docker logs 里——每次 echo 直接 write,没有用户态缓冲。", t=tl(S(4)), done=lidx(S(4), 'sh 的 echo'), kv=KV([['sh 的 echo', '0.1 秒,立刻出现']], ['sh 的 echo'])),
]
A = mkartc('c68', 68, 'Docker,stdout缓冲,Python,docker logs,PYTHONUNBUFFERED,TTY,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测日志延迟:Python 的 print 写到管道时块缓冲,docker logs 里第一行 10.3 秒(进程退出时)才出现;python -u、PYTHONUNBUFFERED=1、flush=True、docker run -t 都在 0.1~0.2 秒内出现;stderr 不缓冲;不 flush 时第一批在累计 8100 字节(约 8 KiB 缓冲区)时出现。',
    '容器明明在跑,docker logs 却是空的?多半是 stdout 被缓冲了。这篇用一个每秒 print 一次的 Python 脚本,量出不同写法下日志出现的时间,并测出缓冲区大约多大。',
    [('10.3 秒', '默认 print 到管道时,docker logs 里第一行出现的时间(脚本约 10 秒后退出)'), ('0.1~0.2 秒', '加了 -u、PYTHONUNBUFFERED=1、flush=True 或 -t 之后第一行出现的时间'), ('8100 字节', '不 flush 时,第一批输出被写出时的累计字节数(缓冲区约 8 KiB)')],
    [('现象', '<p>stdout 接的是管道(docker 的日志管道)而不是终端时,Python 默认把输出攒在 8 KiB 左右的缓冲区里。短脚本退出时才一起写出,长期运行的服务可能很久看不到日志。</p>'),
     ('解决办法', '<p><code>python -u</code>、环境变量 <code>PYTHONUNBUFFERED=1</code>、<code>print(…, flush=True)</code> 都有效。<code>docker run -t</code> 也能让它行缓冲,但会改变其它行为(比如合并 stdout 和 stderr),别随便为此加 -t。</p>'),
     ('stderr 与缓冲区', '<p>stderr 默认不缓冲,所以错误信息常常比普通输出先出现。缓冲区大小我是从数据反推的:累计 8100 字节(81 行)时整块写出,与 8192 字节吻合。</p>'),
     ('对照', '<p>sh 的 <code>echo</code> 每次直接 write,没有这个问题。别的语言(Node、Java、C 的 stdio、Ruby)是否缓冲,我没有测。</p>')],
    steps,
    [ENV_C + '。脚本是 python:3.12-alpine 里的 python -c;第一行出现的时间由 Python 每 0.2 秒(第三节 0.02 秒)轮询 docker logs 得到,误差约 ±0.3 秒;每种情形运行一次;实验后已删除容器',
     '没有验证:Node / Java / Go / Ruby 的缓冲行为、C 程序的 stdio 缓冲与 stdbuf、管道里多个进程串联时的缓冲、Python 3.12 以外的版本、TTY 下的完整行为差异'],
    'stdout 缓冲')

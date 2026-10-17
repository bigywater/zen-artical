from lib import *
R = J('d25'); py_ = R['py']; tp = R['tpl']; lo = min(x[0] for x in py_); hi = max(x[0] for x in py_)
steps = [
    step("runserver 的启动输出第一行:Watching for file changes with StatReloader——本机默认使用的是基于轮询文件修改时间(stat)的重载器。", t=tl(R['banner'][:6], cur=[0]), kv=KV([['reloader', 'StatReloader']], ['reloader'])),
    step(f"修改一个被导入的 .py(lab/views.py,连续 3 次):新代码生效用时 {'、'.join(f'{x[0]:.2f}' for x in py_)} s,每次都新增 1 个进程(整个 Django 进程被重启);runserver 输出「…/lab/views.py changed, reloading.」。", b=bars([[f'第 {i+1} 次生效用时(s)', x[0], f"{x[0]:.2f}"] for i, x in enumerate(py_)], 1.2, done=[0, 1, 2]), kv=KV([['改 .py', f'重启进程,{lo:.1f}–{hi:.1f} s 生效']], ['改 .py'])),
    step(f"改模板文件:不重启(新增进程 {sum(x[2] for x in tp)} 个),下一次请求就看到新内容——缓存过的模板约 {tp[1][0]:.1f} s 内刷新(期间读到旧内容的次数:{'/'.join(str(x[1]) for x in tp)};第一次生效特别快,原因没有查明)。", b=bars([[f'第 {i+1} 次模板生效用时(s)', x[0], f"{x[0]:.2f}"] for i, x in enumerate(tp)], 1.2, mark=[1, 2], done=[0]), kv=KV([['改模板', '不重启,缓存被重置']], ['改模板'])),
    step(f"没有被任何模块导入的 .py(lab/other.py)和非 .py 文件(notes.txt)被修改后,3 秒内新增进程 {R['unimported']} 个 / {R['txt']} 个——不会重启。重载器只关心被导入的模块和它注册的文件(模板目录)。", n=fl([['改被导入的 views.py', '重启'], ['改模板', '不重启,刷新缓存'], ['改没被导入的 other.py', '不重启'], ['改 notes.txt', '不重启']], mark=[0], done=[1, 2, 3]), kv=KV([['重载范围', '被导入的模块 + 模板']], ['重载范围'])),
]
A = dict(
    n=25, series='django', tags='Django,runserver,自动重载,真实验证,动画演示',
    desc=f'实测 runserver 自动重载:默认 StatReloader;修改被导入的 .py 后 {lo:.1f}–{hi:.1f} s 内新代码生效且进程被重启;修改模板不重启、缓存约 {tp[1][0]:.1f} s 内刷新;没被导入的 .py 和非 .py 文件不触发重启。',
    lead='改了一行代码,runserver 是怎么知道的?是全盘监听吗?改模板要不要重启?这篇启动真实的 runserver,改文件、计时、数进程,把重载的边界摸清。',
    facts=[('StatReloader', '本机默认用轮询 stat 的重载器(输出:Watching for file changes with StatReloader)'), (f'{lo:.1f}–{hi:.1f} s', '修改被导入的 .py 到新代码生效的用时(3 次),期间进程被重启'), ('模板不重启', '改模板只重置模板缓存,不重启进程')],
    body=[
        sec('用的是哪种 reloader', '', term('', blk('d25', 1)), '<p>本机没有安装 <code>pywatchman</code>,所以用的是 StatReloader:定期检查已知文件的修改时间。(装了 watchman 后是否自动换用没有测。)</p>'),
        sec('改 .py 文件', '', term('', blk('d25', 2)), '<p>重载器发现被监视的文件变化后,让子进程退出、由父进程拉起新的子进程——所以每次改动进程 id 都变、<code>ready()</code> 重新执行(第 14 篇)。</p>'),
        sec('改模板与其它文件', '', term('', blk('d25', 3)), '<p>被监视的是「已导入模块的文件 + 注册的额外路径(如模板目录)」。改一个没有被导入的 .py 或一个文本文件,不会有反应。改模板时 Django 只重置模板加载器的缓存。</p>'),
        sec('分步演示:重载的边界', '', demo('runserver 自动重载', [('t', 'term', '启动输出'), ('b', 'bars', '生效用时'), ('n', 'flow', '边界'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。每种改动重复 3 次;生效用时是「写文件」到「请求返回新内容」的时间,轮询间隔 20 ms', '没有验证:WatchmanReloader、大项目里 StatReloader 的 CPU 占用与轮询间隔、改 settings.py 的重启行为、新增文件(未被导入)后 import 它的情形、在 Docker 卷或网络文件系统上的 mtime 精度问题'],
)

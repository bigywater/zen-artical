import json
from lib import *
txt = out('110').split('\n\n')
R = json.load(open('out/110.json'))
by = {r['mode']: r for r in R}
def sect(mode):
    for c in txt:
        if c.strip().startswith(f'== {mode}:'):
            lines = c.strip().splitlines(); return '\n'.join(lines[1:]).rstrip()
    raise KeyError(mode)
def rcs(r): return f"退出码 {r['rc']}" if r['rc'] >= 0 else f"被信号 {-r['rc']} 终止"
d, fl, en, ed, fs, fw = (by[m] for m in ('default', 'flag', 'exit_nondaemon', 'exit_daemon', 'flag_stuck', 'flag_watchdog_stuck'))
def n_done(r): return sum(1 for l in r['log'] if '完成' in l and 'job' in l)
FL = lambda cur, done=(): {'nodes': [['SIGTERM 到达', '在 job 3 执行中'], ['处理方式', ''], ['进程如何结束', ''], ['收尾', 'cleanup 是否执行']], 'cur': cur, 'done': list(done)}
def T(r): return {'lines': [l.strip() for l in r['log']], 'cur': [len(r['log']) - 1]}
steps = [
    step("服务:一个工作线程依次处理 20 个任务,每个 0.3 秒。父进程在 0.75 秒时(正在处理第 3 个任务)发出 SIGTERM。看六种处理方式各自会怎样。", fl=FL([0]), lg={'lines': ['0.000 job 1 开始', '0.305 job 1 完成', '0.306 job 2 开始', '0.610 job 2 完成', '0.610 job 3 开始', '0.75x ← SIGTERM'], 'cur': [5]}, kv={'items': [['任务', '20 个,每个 0.3 s'], ['SIGTERM', '0.75 s,job 3 执行中']], 'hl': []}),
    step(f"① 不写处理函数:SIGTERM 的默认处置直接终止进程({rcs(d)})。job 3 只有「开始」,没有「完成」;cleanup 没有执行。SIGTERM 发出 {d['took']:.2f} 秒后就没了。", fl=FL([2], [0]), lg=T(d), kv={'items': [['结局', rcs(d)], ['job 3', '中途丢失'], ['cleanup', '未执行']], 'hl': ['cleanup']}),
    step(f"② 处理函数只设置「停止标志」:工作线程做完手头的 job 3(0.914 s 完成),循环检查到标志就退出,main 返回,atexit 里的 cleanup 执行。SIGTERM 发出 {fl['took']:.2f} 秒后进程自己退出({rcs(fl)}),已完成 3 个,队列里 17 个留待下次。", fl=FL([1, 3], [0, 2]), lg=T(fl), kv={'items': [['结局', f"{rcs(fl)}(自己退出,{fl['took']:.2f} s)"], ['job 3', '完成'], ['cleanup', '执行']], 'hl': ['结局']}),
    step("③ 处理函数里直接 sys.exit(0),工作线程是普通线程:main 线程的 SystemExit 只让主线程结束——解释器会等所有非守护线程,而工作线程还在一个接一个地处理任务。SIGTERM 之后它继续处理了 job 4、5、6……", fl=FL([1, 2], [0]), lg={'lines': [l.strip() for l in en['log'][5:14]], 'cur': [0]}, kv={'items': [['SIGTERM 之后', '工作线程仍在继续处理新任务'], ['sys.exit(0)', '没有让进程退出']], 'hl': ['sys.exit(0)']}),
    step(f"这个「退不出去」的进程最后由父进程发 SIGKILL 才结束({en['took']:.1f} 秒后,{rcs(en)});cleanup 从未执行——业务任务 job 13 中途被杀。", fl=FL([2, 3], [0, 1]), lg={'lines': [l.strip() for l in en['log'][-4:]], 'cur': [3]}, kv={'items': [['结局', f"{rcs(en)},等了 {en['took']:.1f} 秒"], ['cleanup', '未执行']], 'hl': ['结局']}),
    step(f"④ 处理函数里 sys.exit(0),但工作线程是守护线程:进程 {ed['took']:.2f} 秒内就退出了、退出码 0、cleanup 也执行了——但 job 3 被丢弃(只有开始,没有完成),cleanup 里显示「已完成 2 个」。「退出得快」是以正在做的任务为代价。", fl=FL([1, 2, 3], [0]), lg=T(ed), kv={'items': [['结局', f"{rcs(ed)}({ed['took']:.2f} s)"], ['job 3', '被丢弃'], ['cleanup', '执行']], 'hl': ['job 3']}),
    step(f"⑤ 设置停止标志,但 job 3 卡死(下游永不返回):标志设了却没人检查——工作线程卡在 job 3 里。进程一直不退出,直到父进程 {fs['took']:.1f} 秒后 SIGKILL({rcs(fs)}),cleanup 未执行。", fl=FL([2], [0, 1]), lg=T(fs), kv={'items': [['结局', f"{rcs(fs)},等了 {fs['took']:.1f} 秒"], ['cleanup', '未执行']], 'hl': ['结局']}),
    step(f"⑥ 停止标志 + 1 秒看门狗(threading.Timer 到时 os._exit(1)):{fw['took']:.2f} 秒后强制退出、{rcs(fw)}——不会无限等,退出状态也能让调度系统知道这是「超时强退」。(代价:os._exit 不执行 cleanup,如图。)", fl=FL([1, 2], [0]), lg=T(fw), kv={'items': [['结局', f"{rcs(fw)}({fw['took']:.2f} s)"], ['cleanup', '未执行(os._exit)']], 'hl': ['结局']}),
]
A = dict(
    n=110,
    tags='Python,可靠性,信号,进程,真实验证,动画演示',
    desc=f'本机真实用 6 种方式处理正在执行第 3 个任务时收到的 SIGTERM:默认处置立刻被杀(丢失任务、cleanup 不执行);只设停止标志在 {fl["took"]:.2f} s 内做完手头任务并干净退出(退出码 0);处理函数里 sys.exit(0) 遇到普通工作线程根本退不出去(父进程等了 {en["took"]:.0f} s 只能 SIGKILL),遇到守护线程则秒退但丢弃在途任务;任务卡死时只设标志会永远等下去,加 1 秒看门狗则 {fw["took"]:.2f} s 强退。',
    lead='容器被停止、服务被重启,收到的第一个信号通常是 SIGTERM。第 90 篇讲了「哪些退出方式不会清理」;这篇更进一步:一个真的在处理任务的服务,收到 SIGTERM 之后到底该怎么做,才能既不丢在途任务、又不会「怎么也停不下来」?六种做法各跑一遍,把结局摆在一起。',
    facts=[(f'{fl["took"]:.2f} s', '只设停止标志:从 SIGTERM 到干净退出(退出码 0,在途任务做完)'), (f'{en["took"]:.0f} s 退不出去', '处理函数里 sys.exit(0) + 普通工作线程:被父进程 SIGKILL 才结束'), (f'{fw["took"]:.2f} s', '任务卡死时,1 秒看门狗把「永远等下去」变成有界的强制退出')],
    body=[
        sec('做的事:一个真的在干活的服务', '', src('svc.py(核心)', '''def worker():
    while not stop.is_set():                # 每做完一个任务检查一次停止标志
        try: i = jobs.get(timeout=0.05)
        except queue.Empty: return
        work(i)                             # 每个 0.3 秒

atexit.register(cleanup)                    # 关闭连接 / 刷盘

# 六种模式对 SIGTERM 的处理:
#   default        不注册处理函数
#   flag           handler 里 stop.set()
#   exit_nondaemon handler 里 sys.exit(0),工作线程是普通线程
#   exit_daemon    handler 里 sys.exit(0),工作线程是守护线程
#   flag_stuck     handler 里 stop.set(),但 job 3 永远卡住
#   flag_watchdog  handler 里 stop.set() + Timer(1.0, os._exit(1))'''),
            '<p>父进程在服务处理 job 3 的时候(0.75 秒)发出 SIGTERM,记录进程什么时候、以什么状态结束,以及日志里留下了什么。日志由服务自己用 <code>os.write</code> 直接写文件(不经缓冲),时间是相对服务启动的秒数。</p>'),
        sec('验证一:默认处置——立刻被杀', '', term('', sect('default')),
            f'<p>没有注册任何处理函数时,SIGTERM 直接终止进程({rcs(d)}):job 3 只有「开始」没有「完成」,<code>cleanup</code> 没有执行(见第 90 篇)。服务什么都来不及做。</p>'),
        sec('验证二:处理函数只设置停止标志——干净退出', '', term('', sect('flag')),
            f'<p>信号处理函数里<b>只做一件最小的事</b>:设置一个 <code>threading.Event</code>。工作线程做完 job 3(0.914 秒完成),下一轮循环检查到标志就退出;main 返回,<code>atexit</code> 里的 <code>cleanup</code> 执行,进程以 {rcs(fl)} 退出,从收到信号到退出 {fl["took"]:.2f} 秒。已完成的 3 个任务是完整的,队列里剩下的 17 个可以在下次启动时继续。注意:信号处理函数只在主线程执行,所以工作线程要靠共享的 Event 得知要停。</p>'),
        sec('验证三:处理函数里 sys.exit(0)——退不出去', '', term('', sect('exit_nondaemon')),
            f'<p>一种看起来很自然的写法:在 handler 里直接 <code>sys.exit(0)</code>。但 <code>SystemExit</code> 只在主线程里抛出;解释器退出时要等待所有<b>非守护线程</b>结束,而工作线程完全不知道要停,继续处理 job 4、5、6……。日志显示 SIGTERM 之后它一直在干活;最后是父进程等了 {en["took"]:.1f} 秒后发 SIGKILL 才终结它({rcs(en)}),<code>cleanup</code> 没有执行,job 13 被中途杀掉。这就是很多服务「stop 之后还得等超时被强杀」的原因之一。</p>'),
        sec('验证四:守护线程——退得快,但丢在途任务', '', term('', sect('exit_daemon')),
            f'<p>把工作线程设成守护线程后,同样的 <code>sys.exit(0)</code> 让进程在 {ed["took"]:.2f} 秒内退出、退出码 0,<code>cleanup</code> 也执行了——但 job 3 被丢弃(只有「开始」),<code>cleanup</code> 里的「已完成 2 个」也能印证。守护线程在解释器退出时被直接丢掉,不会有机会做完手头的事。</p>'),
        sec('验证五:任务卡死时,只设标志会永远等下去', '', term('', sect('flag_stuck')),
            f'<p>标志设置了,但 job 3 卡在下游调用里(这里用 <code>sleep(60)</code> 模拟),工作线程根本走不到「检查标志」那一步。进程一直不退出,直到父进程等了 {fs["took"]:.1f} 秒后发 SIGKILL({rcs(fs)}),<code>cleanup</code> 没有执行。优雅关闭不能只靠对方的配合。</p>'),
        sec('验证六:加一个有时限的看门狗', '', term('', sect('flag_watchdog_stuck')),
            f'<p>在 handler 里除了设置标志,再启动一个 <code>threading.Timer(1.0, os._exit(1))</code>:在这 1 秒的宽限期里,能做完的任务会做完;卡死的话,宽限期一到就强制退出——SIGTERM 发出 {fw["took"]:.2f} 秒后进程结束,退出码 1(表明「不是正常收尾」),而不是等到编排系统的 SIGKILL。代价是 <code>os._exit</code> 不会执行 <code>cleanup</code>;要在强退前做最关键的收尾,得在 Timer 的回调里显式写。宽限期应当小于编排系统的强杀等待时间——这一点我没有验证具体的编排系统默认值。</p>'),
        sec('总结:一个可靠的关闭流程', '',
            '<ol><li>信号处理函数里只<b>设置标志</b>(<code>Event</code>),不要在里面做重活,也不要直接 <code>sys.exit</code>。</li>'
            '<li>工作循环每做完一个任务检查标志;长任务内部也要有可以中断的检查点或超时。</li>'
            '<li>给关闭加一个<b>有时限的看门狗</b>,别指望每个任务都会配合。</li>'
            '<li>清理逻辑放在 <code>atexit</code>/<code>finally</code>,并且要知道 <code>os._exit</code> 和 SIGKILL 会跳过它们。</li></ol>'),
        sec('分步演示:同一个 SIGTERM,六种结局', '日志与耗时取自上面的真实运行',
            demo('优雅关闭', [('fl', 'flow', '过程'), ('lg', 'term', '服务日志'), ('kv', 'kv', '结局')], steps, '当前结局 / 最后一条日志')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>signal</code>、<code>threading</code>、<code>atexit</code>、<code>subprocess</code>;所有时间取自服务自己的 <code>time.perf_counter</code>,数字每次略有不同',
          '没有验证:asyncio 下的 <code>loop.add_signal_handler</code>、多进程 worker 的信号传递、Docker / Kubernetes 的宽限期默认值与发送信号的具体行为、SIGINT 与 SIGTERM 同时处理'],
)

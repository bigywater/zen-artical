import json
from lib import *
txt = out('90'); R = json.load(open('out/90.json'))
def rc(r): return str(r['rc']) if r['rc'] >= 0 else f"信号 {-r['rc']}"
yn = lambda x: '✓' if x else '✗'
head = ['退出方式', '退出码', 'atexit', 'finally', '__del__', '缓冲输出']
note = {
    "正常执行到末尾": "正常返回:三样清理都执行,缓冲的 print 也在退出时刷出。",
    "未捕获的异常": "异常一路冒出:finally 先执行,回溯打印,然后 atexit、对象销毁、刷新缓冲照常进行,退出码 1。",
    "sys.exit(3)": "sys.exit 只是抛 SystemExit,走的是正常退出路径,退出码是你给的 3。",
    "os._exit(4)": "os._exit 直接调用系统的 _exit:什么都不做就走,四样全部跳过。",
    "os.abort()": "abort 让进程被 SIGABRT 杀掉,解释器没有任何机会清理。",
    "子线程里未捕获的异常": "子线程异常只影响那个线程(打印回溯),主线程正常结束,所以退出码是 0,三样清理照常执行。",
    "收到 SIGINT(Ctrl+C)": "SIGINT 默认被 Python 转成 KeyboardInterrupt 异常,走正常清理;最后进程是以「被信号 2 终止」的状态结束的。",
    "收到 SIGTERM(默认处理)": "SIGTERM 的默认处理是直接终止进程,Python 没有转成异常:atexit、finally、缓冲全丢。",
    "收到 SIGTERM, 自己注册了 handler → sys.exit": "自己注册 handler 并调用 sys.exit,把 SIGTERM 变成正常退出:清理全部执行,退出码 0。",
    "收到 SIGKILL": "SIGKILL 不能被捕获,内核直接杀掉进程:什么都不会执行。",
}
steps = []
vals = [head]
for i, r in enumerate(R):
    name = r['name']
    if len(name) > 22: name = name.replace('收到 SIGTERM, 自己注册了 handler → sys.exit', '收到 SIGTERM + 自定义 handler')
    row = [name, rc(r), yn(r['atexit']), yn(r['finally']), yn(r['del']), yn(r['out'])]
    vals = vals + [row]
    ok = r['atexit'] and r['finally']
    steps.append(step(note[r['name']], m={'values': [list(x) for x in vals], 'cur': [[i + 1, c] for c in range(6)], 'mark': [] if ok else [[i + 1, c] for c in (2, 3, 4, 5)], 'done': [[i + 1, c] for c in (2, 3, 4, 5)] if ok else []}))
alltab = table(head, [[r['name'], rc(r), yn(r['atexit']), yn(r['finally']), yn(r['del']), yn(r['out'])] for r in R], mono=False)
A = dict(
    n=90,
    tags='Python,CPython,进程,信号,真实验证,动画演示',
    desc='本机真实用 10 种方式结束一个 Python 进程,记录 atexit、finally、__del__ 和缓冲 print 是否执行:正常返回、异常、sys.exit、子线程异常、SIGINT、带 handler 的 SIGTERM 都执行,而 os._exit、os.abort、默认 SIGTERM、SIGKILL 全部不执行;SIGINT 的进程最终以信号 2 而不是退出码结束。',
    lead='「程序结束时会做清理」这句话在很多退出方式下并不成立。这篇用 10 种方式真的把进程结束掉,每次都检查四件事有没有发生:<code>atexit</code> 回调、<code>finally</code>、对象的 <code>__del__</code>、以及缓冲区里还没刷出去的 <code>print</code>。',
    facts=[('4 种不清理', 'os._exit、os.abort、默认 SIGTERM、SIGKILL 下四样全部丢失'), ('SIGTERM 默认', '不会转成异常:atexit / finally / 缓冲输出全没了'), ('SIGINT ≠ SIGTERM', 'Ctrl+C 走正常清理,同样的 kill 却不会')],
    body=[
        sec('做的事:同一个脚本,十种结束方式', '', src('t.py(节选)', '''atexit.register(lambda: mark("atexit"))
class Res:
    def __del__(self): mark("__del__")
r = Res()                                          # 模块级对象
print("缓冲区里的一行 print (没有 flush)", end="")   # stdout 是管道: 块缓冲
try:
    ...  # 按参数:正常结束 / 抛异常 / sys.exit / os._exit / os.abort / 睡眠等信号
finally:
    mark("finally")'''),
            '<p><code>mark()</code> 直接用 <code>os.write</code> 往文件里写一行(不经过缓冲),这样能可靠判断清理代码有没有跑。信号类的场景由父进程等脚本睡起来之后再发信号。「缓冲输出」列看的是父进程有没有收到那行没 flush 的 print。</p>'),
        sec('验证:十种退出方式的结果', '', term('', txt.split('\n\n  各行的 stderr')[0].replace('== 每种退出方式下:atexit / finally / __del__ / 缓冲 print 是否执行 ==\n', '')),
            alltab,
            '<p>列表按「能不能干净收尾」可以分成两类:</p>'
            '<ul><li><b>走了正常清理:</b>正常返回、未捕获异常、<code>sys.exit</code>、子线程异常、<code>SIGINT</code>、被 handler 接住的 <code>SIGTERM</code>。它们最终都经过 Python 的解释器关闭流程,<code>atexit</code>、<code>finally</code>、<code>__del__</code> 和缓冲区刷新都发生了。</li>'
            '<li><b>什么都没做:</b><code>os._exit</code>、<code>os.abort</code>、默认处理的 <code>SIGTERM</code>、<code>SIGKILL</code>。进程被系统直接终结,连那一行缓冲的 print 也丢了。</li></ul>'),
        sec('几个值得单独说的观察', '',
            callout('<b>SIGTERM 与 SIGINT 的处理不对称。</b>同样是「请进程退出」,Ctrl+C 会被 Python 转成 <code>KeyboardInterrupt</code> 而走完清理;但 <code>kill 进程号</code>(默认发的就是 SIGTERM)不会——它直接终止进程,<code>finally</code> 和 <code>atexit</code> 都不执行。所以想在服务被 <code>kill</code> 时收尾,必须自己 <code>signal.signal(SIGTERM, ...)</code> 并调用 <code>sys.exit</code>——本次「带 handler」那一行证明这样做后清理全部恢复。'),
            '<p><b>子线程的异常不会让进程失败。</b>一个线程里除零,回溯被打印,但主线程继续、进程退出码是 <code>0</code>——依赖退出码判断成败的调度系统会被骗过。</p>'
            '<p><b>SIGINT 的退出状态。</b>清理都执行了,但进程最终是「被信号 2 终止」的(退出状态 -2),而不是普通的退出码——subprocess 报告的返回码是 -2,即「被信号 2 终止」。</p>'),
        sec('分步演示:逐种退出方式,谁被跳过了', '表格里 ✓ 是执行了,✗ 是被跳过;数据全部是上面的实测',
            demo('十种退出方式', [('m', 'matrix', '清理是否执行')], steps, '正在看的那一行')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>atexit</code>、<code>signal</code>、<code>os</code>、<code>subprocess</code>',
          '没有验证:Linux 上的相同结果、<code>SIGHUP</code> / <code>SIGQUIT</code>、多线程非守护线程运行时收到信号、被 OOM killer 杀掉(与 SIGKILL 同类,没有单独测)'],
)

from lib import *
raw = out('79')
parts = {}
for chunk in raw.split('### ')[1:]:
    name, _, body = chunk.partition('\n'); parts[name.strip()] = body.rstrip()
def code(n): return open(f'exp/w79/{n}.py').read().strip()

FL = lambda cur, done=(): {'nodes': [['main 返回', ''], ['等非守护线程', 'threading._shutdown'], ['atexit 回调', '后进先出'], ['解释器清理', '']], 'cur': cur, 'done': list(done), 'noarrow': False}
steps = [
    step("脚本主体执行完,main 返回(0.00 s)。此时还有一个非守护线程在 sleep,一个守护线程在循环。", fl=FL([0]),
         kv={'items': [['0.00 s', 'main 函数返回'], ['非守护线程', '还在跑(要 0.6 s)'], ['守护线程', '还在跑']], 'hl': ['0.00 s']}),
    step("解释器先等所有非守护线程结束:0.61 s 时它干完活,atexit 才开始——不是 main 一返回就执行。", fl=FL([1], [0]),
         kv={'items': [['0.61 s', '非守护线程 干完活'], ['0.61 s', 'atexit handler 执行']], 'hl': ['0.61 s']}),
    step("守护线程被直接丢弃:它的「干完活」那行日志永远没有出现(输出里只有三行)。", fl=FL([1], [0]),
         kv={'items': [['守护线程', '没有打印任何东西,被静默终止'], ['输出行数', '3 行']], 'hl': ['守护线程']}),
    step("注册了 h1、h2、decorated 三个回调,执行顺序反过来:decorated → h2 → h1(后进先出)。参数也照常传入。", fl=FL([2], [0, 1]),
         kv={'items': [['1', 'decorated'], ['2', 'h2  参数=(\'x\',) {\'k\': 1}'], ['3', 'h1']], 'hl': ['1', '2', '3']}),
    step("回调 boom 抛了异常:打印 “Exception ignored in atexit callback” 和回溯,但其余回调(c、a)照常执行,退出码仍是 0。", fl=FL([2], [0, 1]),
         kv={'items': [['c', '执行'], ['boom', '抛 RuntimeError → 被忽略并打印'], ['a', '执行'], ['退出码', '0']], 'hl': ['boom']}),
    step("在回调里再注册新回调:late 没有执行——退出阶段注册的回调不会再被调用。", fl=FL([2], [0, 1]),
         kv={'items': [['first', '执行,并注册了 late'], ['late', '没有执行']], 'hl': ['late']}),
]
A = dict(
    n=79,
    tags='Python,标准库,进程退出,真实验证,动画演示',
    desc='用 6 个独立子进程真实验证 atexit:回调按注册的相反顺序执行、回调抛异常被打印并忽略且其余回调照常执行、在退出阶段再注册的回调不会执行、非守护线程会先被等完而守护线程被静默丢弃,unregister 会移除同一函数的所有注册。',
    lead='<code>atexit.register</code> 看上去只是「程序结束时调用一下」。但它到底在什么时刻跑、跑几个、出错了怎么办、线程算不算数——这篇用六个小脚本一个一个跑出来。',
    facts=[('后进先出', '3 个回调的执行顺序与注册顺序相反'), ('0.61 s', 'atexit 等到非守护线程结束之后才开始'), ('late 没跑', '在退出阶段里新注册的回调不会执行')],
    body=[
        sec('做的事:每个问题一个独立脚本', '每次都在新的子进程里执行,输出是它们的原样标准输出 / 标准错误',
            '<p>下面每一节对应一个脚本(<code>s1.py</code>…<code>s6.py</code>),脚本内容在每节里给出。命令后面的「退出码」是 shell 拿到的进程退出码。</p>'),
        sec('验证一:顺序是后进先出', '', src('s1.py', code('s1')), term('python3 s1.py', parts['s1'].replace('  (退出码 0)', '(退出码 0)') if False else parts['s1']),
            '<p>注册顺序是 h1、h2、decorated,执行顺序正好相反。参数照常传入。这和 <code>with</code>/<code>ExitStack</code> 的「先进后出」逻辑一致:后注册的清理通常依赖先注册的资源,所以要先清理它。</p>'),
        sec('验证二:一个回调抛异常,其它回调还会执行吗', '', src('s2.py', code('s2')), term('python3 s2.py', parts['s2']),
            '<p>会。异常被打印为 <code>Exception ignored in atexit callback</code> 加完整回溯,其余回调(c 和 a)都执行了,进程退出码仍然是 0。含义是:清理函数里的错误不会让整个进程「以失败结束」,监控如果靠退出码判断,是发现不了的——需要看日志。</p>'),
        sec('验证三:在退出阶段再注册的回调不执行', '', src('s3.py', code('s3')), term('python3 s3.py', parts['s3']),
            '<p><code>first</code> 在执行时又注册了 <code>late</code>,但输出里没有 late 那一行。所以别指望在回调里「追加一个更晚的清理」。</p>'),
        sec('验证四:线程与 atexit 的先后', '非守护线程先被等完,守护线程被静默丢弃', src('s4.py', code('s4')), term('python3 s4.py', parts['s4']),
            '<p>main 函数在 0.00 s 就返回了,可是 atexit 回调直到 0.61 s 才执行——解释器先等非守护线程结束。守护线程要循环约 3 秒才会打印那一行,这行始终没出现:进程结束时它被直接丢弃,它手里的清理逻辑(关文件、刷缓冲)也一并没有机会执行。</p>'),
        sec('验证五:unregister', '', src('s5.py', code('s5')), term('python3 s5.py', parts['s5']),
            '<p>同一个函数注册了两次,<code>unregister(f)</code> 一次就把两次都移除了,最后只剩 g 执行。(<code>atexit._ncallbacks()</code> 是带下划线的内部接口,这里只用来观察数量。)</p>'),
        sec('验证六:sys.exit 与 atexit', '', src('s6.py', code('s6')), term('python3 s6.py', parts['s6']),
            '<p><code>sys.exit(3)</code> 之后回调照样执行,进程最终的退出码是 3——atexit 不会改变退出码。其他退出方式(异常、信号、<code>os._exit</code>)下 atexit 是否执行,见第 90 篇《Python 进程退出:正常返回、异常和强制终止有什么区别》。</p>'),
        sec('分步演示:一次退出里,谁先谁后', '每一步的内容都是上面脚本的真实输出',
            demo('atexit 在退出流程里的位置', [('fl', 'flow', '退出流程'), ('kv', 'kv', '真实观察')], steps, '此刻的阶段 / 观察')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>atexit</code>、<code>threading</code>',
          '没有验证:多线程同时注册的线程安全性、子解释器里的 atexit、被信号杀死时的行为(见第 90 篇 <code>atexit-shutdown</code>)'],
)

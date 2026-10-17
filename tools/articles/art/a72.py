import json
from lib import *

txt = out('72').splitlines()
R = json.load(open('out/72.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i:j] if l.strip())

# ---- 演示:每一轮 select() 返回了谁 ----
names = ['c0', 'c1', 'c2', 'c3', 'c4']
explain = [
    "c1、c3 各发了一段数据。一个线程,一次 select(),同时知道这两个连接都有数据可读——用时约 0 ms。",
    "谁都没发。select(0.3) 一直阻塞到超时才返回空列表——线程在这段时间里不占 CPU。",
    "c0 发了数据,c4 直接关闭。c4 也算「可读」,读到的是 b''——这才是发现对端关闭的方式。",
    "c2 发了数据但服务端故意不读。select() 立刻返回 c2。",
    "还是不读:select() 又立刻返回 c2——水平触发,只要缓冲区里还有数据就一直通知。",
    "第三次,仍然是 c2。忘记读的连接会让循环空转。",
    "这次读走了 b'unread'。",
    "读走以后再 select:没有就绪的了,阻塞到 0.2 s 超时。",
]
closed = set(); steps = []
for i, r in enumerate(R['rounds']):
    ready = set(r['ready'])
    if i == 2: closed.add('c4')
    vals = [[n, ('已关闭' if n in closed and n not in ready else ('就绪' if n in ready else '空闲'))] for n in names]
    steps.append(step(explain[i],
        conns={'values': vals, 'cur': [k for k, n in enumerate(names) if n in ready and n != 'c4' or (n in ready and n == 'c4')], 'dim': [k for k, n in enumerate(names) if n in closed and n not in ready]},
        sel={'lines': [f"{r['label'].strip()}: select() 用时 {r['ms']} ms → {len(r['ready'])} 个就绪"] + (['  ' + x for x in r['items']] if r['items'] else ['  (空列表)']), 'cur': [0]}))

sel_ms, sel_thr = R['sel'][0]*1000, R['thr'][0]*1000

A = dict(
    n=72,
    tags='Python,标准库,网络,I/O多路复用,真实验证,动画演示',
    desc='本机用 selectors(macOS 下默认是 KqueueSelector)让一个线程同时监听 5 个 socket,逐轮记录 select() 的返回;验证水平触发下不读数据会被重复通知、写事件与内核发送缓冲区(本机 626168 字节)的关系,并对比 200 个连接一个线程和 201 个线程的 echo 耗时。',
    lead='一个线程怎么管几百个连接?答案不是轮询,而是向内核问「这一批 socket 里,现在谁有事」。这篇用真实的 5 个连接、4 类场景,把 <code>selectors</code> 每一轮 <code>select()</code> 的返回都记下来。',
    facts=[('KqueueSelector', '本机 DefaultSelector 自动选的实现(macOS)'), ('626168 字节', '对端不读时,send 写满内核发送缓冲区抛 BlockingIOError 的位置'), (f'{sel_ms:.0f} vs {sel_thr:.0f} ms', '200 连接×20 轮 echo:1 个线程 selectors / 201 个线程')],
    body=[
        sec('做的事:5 个连接,1 个线程', '所有服务端 socket 设为非阻塞,一起注册到 DefaultSelector',
            src('实验脚本(节选)', '''sel = selectors.DefaultSelector()
for i in range(5):
    c = socket.create_connection(("127.0.0.1", port)); s, _ = lsn.accept()
    s.setblocking(False)
    sel.register(s, selectors.EVENT_READ, data=f"c{i}")

for key, mask in sel.select(timeout=1):   # 返回「此刻就绪」的那几个
    data = key.fileobj.recv(100)'''),
            term('', txt[0]),
            '<p><code>DefaultSelector</code> 是个别名,由标准库按平台挑最合适的实现:这台 Mac 上是 kqueue,Linux 上会是 epoll。三种实现(select/poll/kqueue)在本机都能用,但接口一致——业务代码只面对 <code>register</code> / <code>select</code>。</p>'),
        sec('验证一:select() 只返回「此刻有事」的连接', '一次调用同时知道多个连接的状态',
            term('', block('第1轮', '== 二')),
            '<p>第 1 轮 c1、c3 有数据,<code>select()</code> 一次返回这两个,几乎不花时间;第 2 轮没人发数据,它阻塞了整整 <b>301.0 ms</b>(超时设的是 0.3 s),期间线程不占 CPU;第 3 轮 c0 有数据、c4 关闭,返回的两个里 c4 读到的是 <code>b\'\'</code>——<b>对端关闭也表现为「可读」</b>,读到空字节才知道对方走了,这时必须 <code>unregister</code> 并关闭,否则它会一直就绪。</p>'),
        sec('验证二:水平触发,不读就一直通知', '忘了 recv 的后果',
            term('', block('  不读, 第1次', '== 三')),
            '<p>c2 发了数据、服务端故意不读:连续三次 <code>select()</code> 都立刻返回 c2。<code>selectors</code> 的语义是<b>水平触发</b>——只要内核缓冲区里还有数据,就一直报就绪。好处是不容易漏事件(读一半也不会丢通知);代价是「某个连接就绪却没处理」会让事件循环空转,CPU 空转在监控里很像死循环。读走 b\'unread\' 之后,再 select 才回到阻塞到超时(200.4 ms)。</p>'),
        sec('验证三:EVENT_WRITE 看的是发送缓冲区', '刚建立的连接可写;写满之后不可写',
            term('', block('新连接刚建立', '== 四')),
            f'<p>关注写事件通常是为了做背压:先尝试 <code>send</code>,写不完再注册 <code>EVENT_WRITE</code> 等缓冲区腾出空间。本次对端一直不读,累计写进去 {R["sent"]} 字节后 <code>send</code> 抛出 <code>BlockingIOError</code>,这时 select 的写事件为空;对端读走数据后,写事件马上回来。这个数字是本机、本次的内核缓冲区大小(发送缓冲加上对端接收缓冲的合计),换系统或改 <code>SO_SNDBUF</code> 会变。</p>'),
        sec('验证四:一个线程 vs 一个连接一个线程', '200 个连接,每个 echo 20 次',
            term('', block('selectors:', 'zzzz')),
            f'<p>连续跑了三次:selectors 版 40.7–46.6 ms,线程版 66.6–67.4 ms,峰值线程数 1 对 201。同样是回环地址上的 echo,单线程 selectors 更快,线程数从 201 降到 1。要注意这个测试的连接始终活跃、每次只传 4 字节,是最有利于事件循环的情形;它证明的是「连接数上去之后线程开销很实在」,并不是说 selectors 在任何负载下都更快——处理函数如果里面有 CPU 密集或阻塞调用,单线程事件循环反而会被它拖住。</p>'),
        sec('分步演示:同一个线程,八次 select() 的返回', '每一步的返回值都是上面实验的原始记录',
            demo('一个线程监听 5 个连接',
                 [('conns', 'chips', '5 个连接此刻的状态(蓝色 = 这一轮 select 返回了它)'), ('sel', 'term', 'select() 的返回')],
                 steps, '这一轮被 select() 返回的连接')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>selectors</code>、<code>socket</code>、<code>threading</code>',
          '只测了回环地址和 kqueue;epoll 的边沿触发(EPOLLET)、Windows 上的 select 上限、连接数上万后的表现这里都没有验证'],
)

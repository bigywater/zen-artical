import json
from lib import *

tl = json.load(open('out/71_timeline.json'))
txt = out('71')

def rows_lines(rows):
    ls = [f"{a:>5} → {b:<5} {st}" if b != '*' else f"{a:>5} → *     {st}" for a, b, st in rows]
    return ls or ['(没有这个端口的任何连接)']

# 每个阶段 flow 面板: 高亮哪几个角色
FLOW = ["客户端 socket", "内核 TCP", "监听 socket", "accept 出的 socket"]
active = {
    'S1': ([2], [], "bind 之后内核里已有一个 CLOSED 状态的端口占位"),
    'S2': ([2], [], "listen 把它变成 LISTEN,内核开始替它排队"),
    'S3': ([0, 1], [2], "三次握手由内核完成,accept 队列里排着一个已建立的连接"),
    'S4': ([2, 3], [0, 1], "accept 只是把队首连接取出来,包成新 fd"),
    'S5': ([0, 3], [1], "send/recv 只是读写内核缓冲区,3 次 send 合并成 1 次 recv"),
    'S6': ([0, 1], [3], "客户端 close:FIN 发出,两端进入 FIN_WAIT_2 / CLOSE_WAIT"),
    'S7': ([3, 1], [0], "服务端也 close:主动关闭的一方留下 TIME_WAIT"),
    'S8': ([1], [], "监听 socket 关闭,只剩 TIME_WAIT 在内核里等待过期"),
}
notes = {
    'S1': "bind:内核分配端口 %s,netstat 里能看到它,状态是 CLOSED(只占了端口,还不接客)。",
    'S2': "listen(5):状态变成 LISTEN。",
    'S3': "cli.connect() 返回了——但服务端 Python 代码从没调用过 accept()。两端已经是 ESTABLISHED。",
    'S4': "accept() 返回新 fd=5,服务端多出一个专属这条连接的 socket;监听 fd=3 仍是 LISTEN。",
    'S5': "cli.send 三次(6+6+4 字节),conn.recv(4096) 一次就拿到 b'hello|world|tcp!'。",
    'S6': "cli.close():服务端 conn.recv() 读到 b''(EOF);netstat 显示 CLOSE_WAIT / FIN_WAIT_2。",
    'S7': "conn.close():服务端那条连接消失,客户端一端进入 TIME_WAIT。",
    'S8': "监听 socket 也 close,LISTEN 消失,只剩 TIME_WAIT;之后再 connect 直接 ECONNREFUSED。",
}
steps = []
port = tl[0][1].split('端口 ')[1].split(',')[0]
for code, name, rows in tl:
    cur, done, _ = active[code]
    steps.append(step(notes[code] % port if code == 'S1' else notes[code],
        flow={'nodes': [[n, sub] for n, sub in zip(FLOW, ['fd 4', '握手 / 队列 / 状态机', 'fd 3', 'fd 5'])], 'cur': cur, 'done': done, 'noarrow': True},
        ns={'lines': rows_lines(rows), 'cur': [i for i, r in enumerate(rows) if r[2] not in ('LISTEN', 'CLOSED')]}))

A = dict(
    n=71,
    tags='Python,标准库,网络,真实验证,动画演示',
    desc='本机真实建一条 TCP 连接,每 0.08 秒采样一次 netstat:服务端从没调用 accept(),客户端的 connect() 已经在 0.377 ms 内返回且两端都是 ESTABLISHED;三次 send 被合成一次 recv;并按阶段记录 CLOSE_WAIT / FIN_WAIT_2 / TIME_WAIT 出现的位置。',
    lead='Python 的 <code>socket</code> 只是一层很薄的包装:真正的握手、排队、缓冲和关闭状态都在内核里。这篇用一个脚本在本机真实走完「bind → listen → connect → accept → 收发 → 关闭」,外面另起一个循环不停采样 <code>netstat</code>,看每一步内核里到底变成了什么。',
    facts=[('0.377 ms', 'accept() 从未被调用,connect() 就已返回,两端已是 ESTABLISHED'), ('3 → 1', '三次 send(6+6+4 字节)被一次 recv 合并读出'), ('TIME_WAIT', '先 close 的客户端一端留下,服务端那条连接直接消失')],
    body=[
        sec('做的事:一个脚本走完一条连接的一生', '外面的 shell 循环每 0.08 秒采一次 netstat,脚本在每个阶段打时间戳并停 0.7 秒,让状态稳定下来',
            src('实验脚本(节选)', '''srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(('127.0.0.1', 0))            # 端口 0:让内核挑一个空闲端口
srv.listen(5)
cli = socket.socket()
cli.connect(('127.0.0.1', port))      # 注意:此时服务端还没有 accept
conn, addr = srv.accept()             # 之后才 accept
for m in (b"hello|", b"world|", b"tcp!"):
    cli.send(m)                       # 连发三次
data = conn.recv(4096)                # 一次 recv
cli.close(); conn.close(); srv.close()'''),
            '<p>为什么要在脚本外面采样:Python 自己的子进程里跑 <code>netstat</code> 在这台机器上看不到 TCP 连接(返回里 0 行 tcp4),而直接在 shell 里能看到——所以采样放在了脚本之外,靠时间戳把两边对齐。</p>'),
        sec('验证一:socket() 拿到的是一个内核文件描述符', 'Python 对象只是壳',
            term('', '\n'.join(l for l in txt.splitlines() if l.startswith('srv.fileno') or 'cli.connect' in l or 'srv.accept' in l)),
            '<p>服务端监听 socket 是 fd 3,客户端是 fd 4,<code>accept()</code> 返回的新 socket 是 fd 5——这就是普通的文件描述符编号,0/1/2 被标准输入输出占了,所以第一个 socket 从 3 开始。<code>accept()</code> 之后监听 socket 依然存在,服务端因此同时握着两个 fd:一个负责接新连接,一个专属这条连接。</p>'),
        sec('验证二:服务端不 accept,连接照样建立', '这是整篇最反直觉的一条',
            term('', 'S3' + out('71_timeline').split('S3', 1)[1].split('S4')[0].rstrip()),
            '<p>上面是 <code>cli.connect()</code> 返回、服务端还<strong>没有</strong>调用过 <code>accept()</code> 的那一刻,netstat 看到的三行:一条 LISTEN,以及同一对端口的<strong>两个方向都是 ESTABLISHED</strong>。connect 本身只用了 0.377 ms。</p>',
            callout('三次握手是内核代办的。<code>listen(5)</code> 之后,内核就替这个端口接客:SYN 来了自己回 SYN-ACK,ACK 回来后把「已完成握手的连接」放进 accept 队列。Python 的 <code>accept()</code> 做的只是从队列里取一个出来、包成新 fd。所以「服务端没来得及 accept」和「连接没建立」是两回事——只要队列没满,客户端就已经认为自己连上了,并且可以先把数据 send 出去,数据会躺在内核缓冲区里等着。', True)),
        sec('验证三:TCP 是字节流,消息边界不存在', 'send 三次,recv 一次',
            term('', '\n'.join(l for l in txt.splitlines() if 'cli.send' in l or 'conn.recv(4096)' in l)),
            '<p>三次 <code>send</code> 分别返回 6、6、4,合计 16 字节;服务端一次 <code>recv(4096)</code> 拿到的是 <code>b\'hello|world|tcp!\'</code>——三条「消息」粘在一起。TCP 只保证字节顺序和不丢,并不知道你在应用层是怎么切分的。所以协议要自己带边界:定长头、长度前缀或分隔符(我在示例里手动放了 <code>|</code>,就是为了让粘连看得出来)。反过来同样成立:一次 <code>send</code> 的大块数据也可能被多次 <code>recv</code> 才读完,<code>recv(n)</code> 里的 n 只是「最多」。</p>'),
        sec('验证四:关闭时状态落在哪一端', 'CLOSE_WAIT、FIN_WAIT_2 和 TIME_WAIT',
            term('', 'S6' + out('71_timeline').split('S6', 1)[1].rstrip()),
            '<p>客户端先 <code>close()</code>:客户端一端是 FIN_WAIT_2(自己的 FIN 已被确认,等对方的 FIN),服务端一端是 CLOSE_WAIT(收到了对方的 FIN,但自己的 socket 还没关)。服务端 <code>conn.recv()</code> 此时返回 <code>b\'\'</code>,这就是「对方已关闭」的信号。等服务端也 <code>close()</code>,这条连接在服务端一侧消失,而<strong>先关闭的客户端一端</strong>留下了 TIME_WAIT,即使把监听 socket 也关掉它仍在。</p>',
            callout('CLOSE_WAIT 是「我的程序没有 close」造成的:如果服务端代码读到 <code>b\'\'</code> 之后忘了关闭 conn,netstat 里就会一直挂着 CLOSE_WAIT。TIME_WAIT 则是「先关闭的一方」付出的代价——本次是客户端。')),
        sec('验证五:没人监听时,connect 直接被拒', '',
            term('', '\n'.join(l for l in txt.splitlines() if '无人监听' in l)),
            '<p>服务端的监听 socket 关掉后再 <code>connect</code> 同一个端口,得到 <code>ConnectionRefusedError</code>。本机 macOS 上 errno 是 61;errno 的数字随系统不同,代码里应该用 <code>errno.ECONNREFUSED</code> 或直接捕获 <code>ConnectionRefusedError</code>,不要写死数字。</p>'),
        sec('验证六:Python 层能看到的只有一小部分', '用 sys.addaudithook 记录脚本里全部 socket 事件',
            term('', '\n'.join(txt.split('--- 审计钩子看到的 socket 事件 ---\n', 1)[1].splitlines())),
            '<p>审计钩子只看到 <code>socket.__new__</code>、<code>bind</code>、<code>connect</code>、<code>getaddrinfo</code>;<code>listen</code>、<code>accept</code>、<code>send</code>、<code>recv</code> 这次都没有对应事件。所以想靠审计钩子完整还原网络行为是不够的;真要看系统调用,得靠系统层工具。另外注意最后两条:<code>socket.create_connection</code> 内部先 <code>getaddrinfo</code> 解析地址,再新建 socket(第四个参数 6 就是 TCP 协议号)并 connect,这是它比手写 <code>socket()+connect()</code> 多做的一步。</p>'),
        sec('分步演示:同一条连接,八个时刻内核里的状态', '每一步的 netstat 行都是上面实验采样到的原始结果',
            demo('一条 TCP 连接的一生(本机真实采样)',
                 [('flow', 'flow', '谁在动'), ('ns', 'term', 'netstat 看到的这个端口(本地端口 → 对端端口 状态)')],
                 steps, '当前被触发的角色 / 已建立的连接行')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>socket</code>、<code>sys.addaudithook</code>;状态采样用系统自带 <code>netstat -an</code>,每 0.08 秒一次',
          '只测了回环地址 127.0.0.1;没有涉及跨主机网络、SO_REUSEADDR、accept 队列被打满时的行为,也没有测其他操作系统的 errno 与状态命名'],
)

from lib import *
import re
S = SS('u141')
R = J('u141')
tk = re.search(r'用时 (\d+) ms;其中 1000 个各做一次回显往返用时 (\d+) ms,(\d+) 个正确', R['tokio']); tt = re.search(r'线程数 (\d+) → (\d+).*RSS (\d+) MB → (\d+) MB', R['tokio'])
th = re.search(r'建立 (\d+) 个连接用时 (\d+) ms', R['thread']); thf = re.search(r'第 (\d+) 个失败:(.*)', R['thread']); tht = re.search(r'线程数 (\d+) → (\d+),RSS (\d+) MB → (\d+) MB', R['thread'])
lt = re.search(r'tokio 服务端\s+平均往返 ([\d.]+) µs.*\n.*线程服务端\s+平均往返 ([\d.]+) µs', R['lat'])
steps = [
    step("最小的 tokio 回显服务:TcpListener::bind 之后 loop { accept().await },每个连接 tokio::spawn 一个任务,用 tokio::io::copy 把读到的内容写回去。客户端发 \"hello\" 收到 \"hello\",发 \"tokio echo\"(10 字节)收到 \"tokio echo\";客户端 shutdown 写端后,服务端的 copy 读到 EOF 返回,打印回显的字节数。", t=tl(S(1)), done=lidx(S(1), '客户端:发', '服务端:一个连接结束'), kv=KV([['accept 循环', '每个连接 spawn 一个任务'], ['io::copy', '读到 EOF 才结束']], ['accept 循环'])),
    step(f"保持 3000 个空闲连接:tokio(4 个工作线程)建立并保持 {tk.group(3) and '3000'} 个连接用 {tk.group(1)} ms,其中 1000 个各做一次回显往返用 {tk.group(2)} ms,全部 {tk.group(3)} 个正确。进程线程数始终是 {tt.group(2)}(不随连接数增长),RSS 从 {tt.group(3)} MB 变成 {tt.group(4)} MB。", t=tl(S(2)), done=lidx(S(2), 'tokio:建立并保持', '线程数'), kv=KV([['连接数', '3000'], ['线程数', f'{tt.group(1)} → {tt.group(2)}'], ['RSS', f'{tt.group(3)} → {tt.group(4)} MB']], ['线程数'])),
    step(f"对照:每连接一个操作系统线程(256 KiB 栈)的阻塞式服务,同样去建 3000 个连接:建到第 {th.group(1)} 个连接就失败了({thf.group(2)}),进程线程数涨到 {tht.group(2)},RSS 从 {tht.group(3)} MB 涨到 {tht.group(4)} MB。线程版为 {th.group(1)} 个连接用掉的内存已经是 tokio 版 3000 个连接的 {int(tht.group(4)) / int(tt.group(4)):.0f} 倍左右。失败的具体原因(系统线程上限还是 accept 队列)本文没有查明。", t=tl(S(3)), mark=lidx(S(3), '失败'), done=lidx(S(3), '线程服务'), b=bars([['tokio 线程数', int(tt.group(2)), tt.group(2)], ['线程服务 线程数', int(tht.group(2)), tht.group(2)]], int(tht.group(2)), cur=[1], done=[0]), kv=KV([['tokio', f'3000 连接 / {tt.group(2)} 线程 / {tt.group(4)} MB'], ['每连接一线程', f'{th.group(1)} 连接后失败 / {tht.group(2)} 线程 / {tht.group(4)} MB']], ['每连接一线程'])),
    step(f"单个连接的往返延迟并不是 tokio 的优势:同一台机器上,发 4 字节等回显 20000 次,tokio 服务端平均 {lt.group(1)} µs,线程服务端平均 {lt.group(2)} µs,线程版略快。tokio 的价值在于连接数,不在单连接延迟。", t=tl(S(4)), done=lidx(S(4), 'tokio 服务端', '线程服务端'), b=bars([['tokio', float(lt.group(1)), f'{lt.group(1)} µs'], ['线程', float(lt.group(2)), f'{lt.group(2)} µs']], max(float(lt.group(1)), float(lt.group(2))) * 1.2, done=[0, 1]), kv=KV([['tokio 服务端', f'{lt.group(1)} µs'], ['线程服务端', f'{lt.group(2)} µs']], ['线程服务端'])),
]
A = mkart('u141', 141, 'Rust,tokio,TCP,回显服务,真实验证,动画演示',
    f'下载 tokio 写一个回显服务并与线程版对比:io::copy 回显;tokio 保持 3000 个连接只用 {tt.group(2)} 个线程、{tt.group(4)} MB;每连接一线程的版本在 {th.group(1)} 个连接处失败并用到 {tht.group(2)} 个线程、{tht.group(4)} MB;单连接往返延迟 tokio {lt.group(1)} µs 对线程 {lt.group(2)} µs。',
    '异步服务器真正的优势是什么?这篇写一个最小的 tokio 回显服务,在同一台机器上与「每连接一线程」对比三个数字:能撑多少连接、占多少线程与内存、单连接的延迟。',
    [(f'{tt.group(2)} 个线程', 'tokio 服务端保持 3000 个连接时的进程线程数'), (f'{th.group(1)} 个连接', '线程版服务端在尝试 3000 个连接时失败的位置'), (f'{lt.group(1)} 对 {lt.group(2)} µs', '单连接回显往返:tokio 对线程')],
    [('最小的回显服务', '<p>阻塞式 TCP 与线程版见<a href="rust-tcp-listener-stream.html">TCP Listener 与 TcpStream</a>;非阻塞与 poll 见<a href="rust-nonblocking-io.html">非阻塞 IO</a>。tokio 1.x 从 crates.io 下载。</p>'), ('tokio 保持 3000 个连接', None), ('每连接一线程', '<p>线程数与 RSS 通过 ps 读取;失败位置与系统限制有关,换机器会不同。</p>'), ('单连接的延迟', '<p>异步运行时的调度见<a href="rust-tokio-scheduling.html">Tokio 任务调度</a>。</p>')],
    steps, [ENV_U + '。macOS;tokio 1.x', '没有验证:更大的连接数(几万)、写入慢的客户端造成的背压、优雅关闭、每个连接的任务内存占用、tokio::net::TcpStream 与 into_split 的所有权、TLS、Linux 上线程数上限的位置'], 'Tokio TCP Echo')

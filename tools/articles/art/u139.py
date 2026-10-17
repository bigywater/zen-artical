from lib import *
import re
S = SS('u139')
R = J('u139'); lo = re.search(r'最大数据报:(\d+) 字节;(\d+) 字节失败', R['max']); lc = re.search(r'收到 (\d+) 个,丢了 (\d+) 个\(([\d.]+)%\)', R['loss'])
steps = [
    step("UDP 保留消息边界:发送端 send_to 三个数据报(3、5、2 字节),接收端三次 recv_from 各得到一个完整的数据报(\"abc\"、\"defgh\"、\"ij\"),并且都能拿到发送端地址。对比 TCP 的字节流,这里「一次发送一次接收」成立。", t=tl(S(1)), done=lidx(S(1), '第 1 次', '第 2 次', '第 3 次'), kv=KV([['3 次 send_to', '3 次 recv_from,边界保留'], ['recv_from', '同时返回发送端地址']], ['3 次 send_to'])),
    step("接收缓冲区小于数据报时,多出的字节被静默丢弃:10 字节的数据报用 4 字节缓冲区读,recv_from 返回 4,内容 \"0123\",剩下的 6 字节没有了;下一次 recv_from 得到的是下一个数据报 \"NEXT\",不是上一个的剩余部分。没有任何错误提示。", t=tl(S(2)), done=lidx(S(2), '用 4 字节缓冲区', '下一次 recv_from'), kv=KV([['缓冲区 < 数据报', '多出的字节丢弃,无报错']], ['缓冲区 < 数据报'])),
    step(f"数据报有大小上限:在这台 macOS 的回环地址上,二分查找得到 send_to 成功的最大数据报是 {lo.group(1)} 字节;{lo.group(2)} 字节失败,错误码 os error 40(消息太长)。这个上限是系统参数,不是协议的 65507。", t=tl(S(3)), done=lidx(S(3), '最大数据报'), kv=KV([['可发送的最大数据报', f'{lo.group(1)} 字节'], ['再大一字节', 'os error 40']], ['可发送的最大数据报'])),
    step("UDP 没有可靠性,发送方不知道对端是否存在:对一个没人监听的端口 send_to 返回 Ok(2),没有任何错误。如果先 connect 到这个死端口,send 也成功,但随后的 recv 得到 Err(ConnectionRefused)(os error 61)—— 内核把对端的「端口不可达」回报在下一次操作上才暴露出来。", t=tl(S(4)), done=lidx(S(4), 'send_to 一个没人监听'), mark=lidx(S(4), 'connect 到死端口'), kv=KV([['send_to 死端口', 'Ok(2)'], ['connect + recv', 'ConnectionRefused / 61']], ['connect + recv'])),
    step(f"丢包是常态:快速发 20000 个 1000 字节的数据报给一个还没来得及读的接收端,发送端每次 send_to 都返回成功,接收端实际只收到 {lc.group(1)} 个,丢了 {lc.group(2)} 个({lc.group(3)}%)—— 接收缓冲区装不下的数据报被内核直接丢弃,发送方对此一无所知。需要可靠性就要自己加序号、确认与重传。", t=tl(S(5)), mark=lidx(S(5), '接收端收到'), b=bars([['收到', int(lc.group(1)), lc.group(1)], ['丢失', int(lc.group(2)), lc.group(2)]], 20000, done=[0], cur=[1]), kv=KV([['发送', '20000'], ['收到', lc.group(1)], ['丢失', f'{lc.group(2)}({lc.group(3)}%)']], ['丢失'])),
]
A = mkart('u139', 139, 'Rust,UDP,UdpSocket,网络,真实验证,动画演示',
    f'用回环地址验证 UdpSocket:数据报保留边界;缓冲区太小静默截断;macOS 上最大数据报 {lo.group(1)} 字节(超过 os error 40);对死端口 send_to 成功、connect 后 recv 得 ConnectionRefused;快速发 20000 个数据报只收到 {lc.group(1)} 个(丢 {lc.group(3)}%)。',
    'UDP 与 TCP 的差别不只是「不可靠」。这篇用 Rust 的 UdpSocket 验证:消息边界、截断、大小上限、发给不存在的对端、以及真实的丢包比例。',
    [(f'{lc.group(3)}%', '快速发 20000 个数据报时接收端的丢包比例'), (f'{lo.group(1)} 字节', '本机回环地址上能发送的最大 UDP 数据报'), ('3 对 3', '发 3 个数据报,收到 3 个独立的数据报(边界保留)')],
    [('数据报边界', '<p>TCP 的字节流见<a href="rust-tcp-listener-stream.html">TCP Listener 与 TcpStream</a>。</p>'), ('缓冲区太小', None), ('大小上限', '<p>这个上限是 macOS 的系统参数(net.inet.udp.maxdgram 一类),换系统不同;没有查该参数。</p>'), ('没有可靠性', None), ('丢包', '<p>丢包比例取决于接收缓冲区大小与发送速度,这次实测是 ' + lc.group(3) + '%,每次不同。</p>')],
    steps, [ENV_U + '。全部使用回环地址', '没有验证:真实网络上的乱序与重复、广播与组播、SO_RCVBUF 调大后的丢包率、IPv6 UDP、UDP 校验和、GSO/GRO'], 'UDP')

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u139'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{net::UdpSocket, thread, time::Duration};
'''
print('== 一:UDP 保留消息边界:发 3 个数据报(长度 3、5、2),接收端 3 次 recv 各得到一个完整的数据报')
r = tryit('u139a', HEAD + '''
    fn main() {
        let rx = UdpSocket::bind("127.0.0.1:0").unwrap(); let tx = UdpSocket::bind("127.0.0.1:0").unwrap(); let dest = rx.local_addr().unwrap();
        for m in [&b"abc"[..], b"defgh", b"ij"] { tx.send_to(m, dest).unwrap(); }
        thread::sleep(Duration::from_millis(30));
        for i in 0..3 { let mut b = [0u8; 64]; let (n, from) = rx.recv_from(&mut b).unwrap(); println!("第 {} 次 recv_from:{} 字节 {:?},来自发送端地址 == tx 的地址: {}", i + 1, n, String::from_utf8_lossy(&b[..n]), from == tx.local_addr().unwrap()); }
    }
''', quiet_src=True); R['boundary'] = r['out']
print()
print('== 二:接收缓冲区小于数据报时,多出的字节被静默丢弃(不会留到下一次 recv)')
r = tryit('u139b', HEAD + '''
    fn main() {
        let rx = UdpSocket::bind("127.0.0.1:0").unwrap(); let tx = UdpSocket::bind("127.0.0.1:0").unwrap(); let dest = rx.local_addr().unwrap();
        tx.send_to(b"0123456789", dest).unwrap(); tx.send_to(b"NEXT", dest).unwrap(); thread::sleep(Duration::from_millis(30));
        let mut small = [0u8; 4]; let (n, _) = rx.recv_from(&mut small).unwrap(); println!("用 4 字节缓冲区读一个 10 字节的数据报:recv_from 返回 {},内容 {:?}(剩下的 6 字节丢了)", n, String::from_utf8_lossy(&small[..n]));
        let mut b = [0u8; 64]; let (n, _) = rx.recv_from(&mut b).unwrap(); println!("下一次 recv_from 得到的是下一个数据报:{:?}(不是上一个的剩余部分)", String::from_utf8_lossy(&b[..n]));
    }
''', quiet_src=True); R['trunc'] = r['out']
print()
print('== 三:数据报的大小上限:找出本机回环地址上 send_to 成功的最大长度(二分)与超过上限的错误')
r = tryit('u139c', HEAD + '''
    fn main() {
        let rx = UdpSocket::bind("127.0.0.1:0").unwrap(); let tx = UdpSocket::bind("127.0.0.1:0").unwrap(); let dest = rx.local_addr().unwrap();
        let (mut lo, mut hi) = (1usize, 70_000usize);
        while lo + 1 < hi { let mid = (lo + hi) / 2; if tx.send_to(&vec![0u8; mid], dest).is_ok() { lo = mid; } else { hi = mid; } }
        println!("send_to 成功的最大数据报:{} 字节;{} 字节失败:{:?}", lo, hi, tx.send_to(&vec![0u8; hi], dest).map_err(|e| (e.kind(), e.raw_os_error())));
    }
''', quiet_src=True); R['max'] = r['out']
print()
print('== 四:UDP 没有可靠性:对着没人监听的端口 send_to 不会报错;connect 之后再 recv,可能收到 ConnectionRefused(ICMP 不可达的回报)')
r = tryit('u139d', HEAD + '''
    fn main() {
        let probe = UdpSocket::bind("127.0.0.1:0").unwrap(); let dead = probe.local_addr().unwrap(); drop(probe);
        let s = UdpSocket::bind("127.0.0.1:0").unwrap();
        println!("send_to 一个没人监听的端口:{:?}(发送方不知道对端不存在)", s.send_to(b"hi", dead).map_err(|e| e.kind()));
        let c = UdpSocket::bind("127.0.0.1:0").unwrap(); c.connect(dead).unwrap(); c.set_read_timeout(Some(Duration::from_millis(300))).unwrap();
        c.send(b"hello?").unwrap(); thread::sleep(Duration::from_millis(50)); let mut b = [0u8; 8];
        println!("connect 到死端口后 send + recv:send 成功;recv 得到 {:?}", c.recv(&mut b).map_err(|e| (e.kind(), e.raw_os_error())));
    }
''', quiet_src=True); R['dead'] = r['out']
print()
print('== 五:丢包:快速发 20000 个 1000 字节数据报给一个还没来得及读的接收端,数一数收到几个(接收缓冲区装不下的被内核丢弃)')
r = tryit('u139e', HEAD + '''
    fn main() {
        let rx = UdpSocket::bind("127.0.0.1:0").unwrap(); let tx = UdpSocket::bind("127.0.0.1:0").unwrap(); let dest = rx.local_addr().unwrap();
        let n = 20_000u32; let payload = vec![7u8; 1000];
        for i in 0..n { let mut p = payload.clone(); p[..4].copy_from_slice(&i.to_le_bytes()); tx.send_to(&p, dest).unwrap(); }
        thread::sleep(Duration::from_millis(100)); rx.set_nonblocking(true).unwrap();
        let (mut got, mut first_missing, mut seen) = (0u32, None::<u32>, vec![false; n as usize]); let mut b = [0u8; 2000];
        while let Ok(k) = rx.recv(&mut b) { got += 1; let i = u32::from_le_bytes(b[..4].try_into().unwrap()); seen[i as usize] = true; }
        let missing = seen.iter().filter(|s| !**s).count(); first_missing = seen.iter().position(|s| !*s).map(|x| x as u32);
        println!("发送 {} 个数据报(共 {} KB),接收端收到 {} 个,丢了 {} 个({:.1}%);发送端 send_to 全部返回了成功", n, n as usize * 1000 / 1000, got, missing, missing as f64 * 100.0 / n as f64);
    }
''', quiet_src=True, release=True); R['loss'] = r['out']
save('u139', R)

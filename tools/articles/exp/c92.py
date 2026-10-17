import sys, os, re, time, subprocess, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c92')
img('python:3.12-alpine', 'alpine:3.20')
purge()
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
LEAK = '''import time, sys, os, socket, threading
mode = sys.argv[1]; keep = []
if mode == "file":
    while True:
        try: keep.append(open("/etc/hostname"))
        except OSError as e:
            print("第 %d 次 open 失败:%s" % (len(keep) + 1, e), flush=True); break
        time.sleep(0.01)
elif mode == "file-keep":
    while True:
        try: keep.append(open("/etc/hostname"))
        except OSError as e:
            for f in keep[-20:]: f.close()
            del keep[-20:]
            print("第 %d 次 open 失败:%s" % (len(keep) + 21, e), flush=True); break
        time.sleep(0.01)
elif mode == "socket":
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", 7000)); srv.listen(100)
    def acc():
        while True:
            c, _ = srv.accept(); c.close()
    threading.Thread(target=acc, daemon=True).start()
    for _ in range(60):
        s = socket.create_connection(("127.0.0.1", 7000)); keep.append(s)
    print("连了 60 个连接,服务端都已关闭,客户端一个都没 close", flush=True)
print("fd 数", len(os.listdir("/proc/self/fd")), flush=True)
time.sleep(300)'''
d = ctx('c92', {'leak.py': LEAK, 'Dockerfile': 'FROM python:3.12-alpine\nCOPY leak.py /leak.py\nENTRYPOINT ["python","-u","/leak.py"]\n'})
rc, o = build(d, 'bwlab-c92', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
print('== 一:不关闭文件的程序,碰到 nofile 上限(Docker Engine 29.8.2)')
n = 'bwlab-c92a'
dk('run', '-d', '--name', n, *LAB, '--ulimit', 'nofile=200:200', 'bwlab-c92', 'file'); time.sleep(4)
s_ = json.loads(out('inspect', '--format', '{{json .State}}', n))
print('  --ulimit nofile=200:200,普通写法的泄漏程序:容器状态 ' + f'{s_["Status"]} ExitCode={s_["ExitCode"]};日志:' + dk('logs', n)[1].strip().replace('\n', ' | ')[:330])
dk('rm', '-f', n)
n = 'bwlab-c92a2'
dk('run', '-d', '--name', n, *LAB, '--ulimit', 'nofile=200:200', 'bwlab-c92', 'file-keep'); time.sleep(4)
print('  同样的上限,出错后先关掉 20 个再汇报的写法:日志:' + dk('logs', n)[1].strip().replace('\n', ' | '))
print('  docker exec 数 /proc/1/fd:' + dk('exec', n, 'sh', '-c', 'ls /proc/1/fd | wc -l')[1].strip() + ' 个(上限 200)')
print('  这些 fd 指向什么(按目标分组):' + dk('exec', n, 'sh', '-c', "for f in /proc/1/fd/*; do readlink $f; done | sed 's/\\[[0-9]*\\]//' | sort | uniq -c | sort -rn | head -4 | awk '{print $2\"×\"$1}' | tr '\\n' ' '")[1].strip())
dk('rm', '-f', n)
print('== 二:没有上限时,泄漏会一直涨(只跑 3 秒,看增长速度)')
n = 'bwlab-c92b'
dk('run', '-d', '--name', n, *LAB, 'bwlab-c92', 'file'); time.sleep(1)
c1 = int(dk('exec', n, 'sh', '-c', 'ls /proc/1/fd | wc -l')[1]); time.sleep(2); c2 = int(dk('exec', n, 'sh', '-c', 'ls /proc/1/fd | wc -l')[1])
fn0 = int(vm('cut -f1 /proc/sys/fs/file-nr')); 
print(f'  默认 nofile 上限(104 万)下:1 秒时 {c1} 个 fd,3 秒时 {c2} 个 fd(每 0.01 秒开一个,约 {(c2 - c1) / 2:.0f} 个/秒)')
print(f'  虚拟机的 /proc/sys/fs/file-nr(已分配的文件句柄数,全局):{fn0}')
time.sleep(3); fn1 = int(vm('cut -f1 /proc/sys/fs/file-nr'))
print(f'  再过 3 秒:{fn1}(增加 {fn1 - fn0},是整台虚拟机共享的计数)')
dk('rm', '-f', n)
fn2 = int(vm('cut -f1 /proc/sys/fs/file-nr')); print(f'  删掉泄漏的容器后:{fn2}(回落 {fn1 - fn2})')
print('== 三:socket 泄漏:服务端关了,客户端不 close,连接停在 CLOSE_WAIT')
n = 'bwlab-c92c'
dk('run', '-d', '--name', n, *LAB, 'bwlab-c92', 'socket'); time.sleep(3)
print('  日志:' + dk('logs', n)[1].strip().replace('\n', ' | '))
st = collections.Counter()
for l in dk('exec', n, 'sh', '-c', "awk 'NR>1 {print $4}' /proc/net/tcp")[1].split():
    st[l] += 1
names = {'01': 'ESTABLISHED', '08': 'CLOSE_WAIT', '06': 'TIME_WAIT', '0A': 'LISTEN', '04': 'FIN_WAIT1', '05': 'FIN_WAIT2', '09': 'LAST_ACK'}
print('  容器里 /proc/net/tcp 各状态的连接数:' + str({names.get(k, k): v for k, v in st.items()}))
print('  fd 里 socket 的数量:' + dk('exec', n, 'sh', '-c', "for f in /proc/1/fd/*; do readlink $f; done | grep -c socket")[1].strip())
dk('rm', '-f', n)
print('== 四:看谁在泄漏:不装 lsof 也能查')
n = 'bwlab-c92d'
dk('run', '-d', '--name', n, *LAB, '--ulimit', 'nofile=300:300', 'bwlab-c92', 'file-keep'); time.sleep(4)
print('  /proc/1/limits 里的 Max open files:' + dk('exec', n, 'sh', '-c', "grep 'open files' /proc/1/limits | tr -s ' '")[1].strip())
print('  /proc/1/fdinfo/<某个 fd> 的内容(位置、标志):' + dk('exec', n, 'sh', '-c', "cat /proc/1/fdinfo/5 | tr '\\n' ' '")[1].strip())
print('  各 fd 的数量随时间(已在上限附近,不再增加):' + dk('exec', n, 'sh', '-c', 'ls /proc/1/fd | wc -l')[1].strip())
dk('rm', '-f', n)
purge()

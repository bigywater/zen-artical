import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c33')
img('python:3.12-alpine')
purge()
OPEN = 'import os,sys,resource\nfs=[]\ntry:\n    while True: fs.append(os.open("/dev/null", os.O_RDONLY))\nexcept OSError as e:\n    print("打开了 %d 个文件后失败:%s(errno %d)" % (len(fs), e.strerror, e.errno))\nprint("soft/hard =", resource.getrlimit(resource.RLIMIT_NOFILE))'
FORK = 'import subprocess,time\nps=[]\ntry:\n    while True: ps.append(subprocess.Popen(["sleep","30"]))\nexcept OSError as e:\n    print("创建了 %d 个子进程后失败:%s" % (len(ps), e.strerror))\nfor p in ps: p.kill()'
def py(code, *opts):
    rc, o = dk('run', '--rm', *LAB, *opts, 'python:3.12-alpine', 'python', '-c', code)
    return rc, o.strip().replace('\n', ' | ')
print('== 一:容器默认的 ulimit(Docker Engine 29.8.2)')
rc, o = dk('run', '--rm', *LAB, 'python:3.12-alpine', 'sh', '-c', 'echo nofile soft=$(ulimit -Sn) hard=$(ulimit -Hn); echo nproc soft=$(ulimit -Su) hard=$(ulimit -Hu); echo core soft=$(ulimit -Sc) hard=$(ulimit -Hc); echo stack soft=$(ulimit -Ss) hard=$(ulimit -Hs); echo memlock soft=$(ulimit -Sl) hard=$(ulimit -Hl)')
for l in o.strip().splitlines(): print('  ' + l)
print('== 二:--ulimit nofile 限制能打开的文件数')
print('  默认:' + py(OPEN)[1])
print('  --ulimit nofile=64:64:' + py(OPEN, '--ulimit', 'nofile=64:64')[1])
print('  --ulimit nofile=64:1024(soft 64,hard 1024):' + py(OPEN, '--ulimit', 'nofile=64:1024')[1])
print('== 三:soft 能不能超过 hard、普通用户能不能把 hard 调高')
rc, o = dk('run', '--rm', *LAB, '--ulimit', 'nofile=64:128', 'python:3.12-alpine', 'sh', '-c', 'ulimit -Sn 200 2>&1; echo "把 soft 调到 200(hard 128) 退出码 $?"; ulimit -Sn 100; echo "把 soft 调到 100 退出码 $?(现在 $(ulimit -Sn))"')
for l in o.strip().splitlines(): print('  ' + l.strip())
rc, o = dk('run', '--rm', *LAB, '--user', '1000', '--ulimit', 'nofile=64:128', 'python:3.12-alpine', 'sh', '-c', 'ulimit -Hn 4096 2>&1; echo "uid 1000 把 hard 调到 4096 退出码 $?"; ulimit -Hn 100; echo "uid 1000 把 hard 降到 100 退出码 $?"; ulimit -Hn 128 2>&1; echo "再升回 128 退出码 $?"')
for l in o.strip().splitlines(): print('  ' + l.strip())
print('== 四:nproc 是按用户(uid)在整个系统里数的,不是按容器')
print('  单个容器 --user 1000 --ulimit nproc=20:' + py(FORK, '--user', '1000', '--ulimit', 'nproc=20')[1])
holders = []
for i in range(2):
    holders.append(out('run', '-d', *LAB, '--user', '1000', 'python:3.12-alpine', 'sh', '-c', 'for i in 1 2 3 4 5 6; do sleep 120 & done; wait'))
time.sleep(1.5)
print('  另外 2 个同样 uid 1000 的容器各占了 7 个进程(1 个 sh 加 6 个 sleep),再跑同样的测试:' + py(FORK, '--user', '1000', '--ulimit', 'nproc=20')[1])
print('  换成 uid 2000(同样 nproc=20):' + py(FORK, '--user', '2000', '--ulimit', 'nproc=20')[1])
for h in holders: dk('rm', '-f', h)
print('  清掉占位容器后,uid 1000 再测一次:' + py(FORK, '--user', '1000', '--ulimit', 'nproc=20')[1])
purge()

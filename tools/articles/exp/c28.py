import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c28')
img('alpine:3.20', 'python:3.12-alpine')
purge()
def case(label, image, *args, opts=(), after=None, delay=1.0):
    n = 'bwlab-c28-' + str(abs(hash(label)) % 10**6)
    if after is None:
        rc, o = dk('run', '--name', n, *LAB, *opts, image, *args)
    else:
        dk('run', '-d', '--name', n, *LAB, *opts, image, *args); time.sleep(delay); after(n)
        for _ in range(30):
            if json.loads(out('inspect', '--format', '{{json .State}}', n))['Status'] == 'exited': break
            time.sleep(0.5)
        rc = None
    s = json.loads(out('inspect', '--format', '{{json .State}}', n)) if out('ps', '-aq', '--filter', f'name={n}') else {}
    print(f'  {label}:' + (f'docker run 退出码 {rc};' if rc is not None else '') + (f'Status={s.get("Status")} State.ExitCode={s.get("ExitCode")} OOMKilled={s.get("OOMKilled")}' if s else '(没有创建出容器)'))
    dk('rm', '-f', n)
    return rc, s
print('== 一:程序自己决定的退出码(Docker Engine 29.8.2)')
case('exit 0', 'alpine:3.20', 'sh', '-c', 'exit 0')
case('exit 3', 'alpine:3.20', 'sh', '-c', 'exit 3')
case('命令不存在', 'alpine:3.20', 'no-such-cmd')
case('文件存在但不可执行(/etc/hostname)', 'alpine:3.20', '/etc/hostname')
case('sh -c 里调用不存在的命令', 'alpine:3.20', 'sh', '-c', 'no-such-cmd')
print('== 二:docker run 自己出错')
case('不存在的选项 --foo', 'alpine:3.20', 'true', opts=['--foo'])
print('== 三:被信号杀死的进程:128 + 信号编号')
case('python 自己 SIGSEGV', 'python:3.12-alpine', 'python', '-c', 'import ctypes; ctypes.string_at(0)')
case('python os.abort()(SIGABRT)', 'python:3.12-alpine', 'python', '-c', 'import os; os.abort()')
rc, o = dk('run', '--rm', *LAB, 'alpine:3.20', 'sh', '-c', 'for s in TERM INT ABRT SEGV KILL; do sh -c "kill -$s \\$\\$"; echo "$s -> $?"; done')
print('  PID 1 的 sh 里依次起子 sh 并让它向自己发信号,子进程的退出状态($?):' + ';'.join(l.strip() for l in o.strip().splitlines()))
case('docker kill(默认 SIGKILL)', 'alpine:3.20', 'sleep', '600', after=lambda n: dk('kill', n))
case('docker kill -s TERM,PID 1 是 sleep(没装处理程序)', 'alpine:3.20', 'sleep', '600', after=lambda n: (dk('kill', '-s', 'TERM', n), time.sleep(2)))
rc = case('docker stop -t 2,PID 1 是 sleep', 'alpine:3.20', 'sleep', '600', after=lambda n: dk('stop', '-t', '2', n))
case('--init 下 docker stop,子进程 sleep 被 SIGTERM 杀死', 'alpine:3.20', 'sleep', '600', opts=['--init'], after=lambda n: dk('stop', '-t', '5', n))
case('--init 下 docker kill -s INT', 'alpine:3.20', 'sleep', '600', opts=['--init'], after=lambda n: dk('kill', '-s', 'INT', n))
print('== 四:同样的 137,OOM 杀死和手动 kill 怎么区分')
case('内存限制 20m,python 一直申请内存', 'python:3.12-alpine', 'python', '-c', 'x=[]\nwhile True: x.append(bytearray(10<<20))', opts=['--memory', '20m', '--memory-swap', '20m'])
purge()

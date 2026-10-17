import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c6')
img('alpine:3.20')
purge()
APP = '#!/bin/sh\ntrap \'echo "收到 SIGTERM,清理后退出"; exit 0\' TERM\necho "app 启动,PID=$$"\nwhile true; do sleep 1 & wait $!; done\n'
variants = [
    ('exec 形式 ENTRYPOINT ["/app.sh"]', 'ENTRYPOINT ["/app.sh"]', []),
    ('shell 形式、单条命令 ENTRYPOINT /app.sh', 'ENTRYPOINT /app.sh', []),
    ('shell 形式、复合命令 ENTRYPOINT /app.sh && echo done', 'ENTRYPOINT /app.sh && echo done', []),
    ('shell 形式、复合命令,但用 exec 接管:ENTRYPOINT exec /app.sh', 'ENTRYPOINT exec /app.sh', []),
    ('exec 形式 ENTRYPOINT ["sleep","300"](没有信号处理)', 'ENTRYPOINT ["sleep", "300"]', []),
    ('同上,docker run --init', 'ENTRYPOINT ["sleep", "300"]', ['--init']),
]
print('== 一:docker stop -t 3 对不同写法的容器要等多久、退出码是多少(Docker Engine 29.8.2)')
for i, (label, line, opts) in enumerate(variants):
    tag = f'bwlab-c6-{i}'
    d = ctx(f'c6_{i}', {'app.sh': APP, 'Dockerfile': f'FROM alpine:3.20\nCOPY --chmod=755 app.sh /app.sh\n{line}\n'})
    build(d, tag)
    cid = out('run', '-d', *LAB, *opts, tag)
    time.sleep(1.0)
    t0 = time.time(); subprocess.run(['docker', 'stop', '-t', '3', cid], capture_output=True); el = time.time() - t0
    code = out('inspect', '--format', '{{.State.ExitCode}}', cid)
    logs = out('logs', cid).replace('\n', ' / ')
    pid1 = ''
    print(f'  [{label}]')
    print(f'      docker stop -t 3 用时 {el:.2f} 秒;退出码 {code};日志:{logs[:90]}')
    subprocess.run(['docker', 'rm', '-f', cid], capture_output=True)
print('== 二:PID 1 的特殊性——同一个 sleep,放在 PID 1 和放在非 PID 1 时对 SIGTERM 的反应')
cid = out('run', '-d', *LAB, 'alpine:3.20', 'sleep', '300')
time.sleep(0.5)
rc, o = dk('exec', cid, 'sh', '-c', 'kill -TERM 1; sleep 1; ps -o pid,args | head -4')
print('  容器内对 PID 1(sleep 300)发 kill -TERM 1 后 1 秒,ps 看到:' + ' | '.join(re.sub(r'\s+', ' ', l.strip()) for l in o.split('\n')[:3]))
rc, o = dk('exec', cid, 'sh', '-c', 'sleep 300 & P=$!; sleep 0.3; kill -TERM $P; wait $P; echo "退出码 $?"')
print('  在同一个容器里另起一个 sleep 300(PID 不是 1),对它发 kill -TERM:' + ([l for l in o.split('\n') if '退出码' in l] or ['(无输出)'])[0].strip() + '(143 = 128 + 15,即被 SIGTERM 终止)')
subprocess.run(['docker', 'rm', '-f', cid], capture_output=True)
print('== 三:从宿主机发信号也是一样')
cid = out('run', '-d', *LAB, 'alpine:3.20', 'sleep', '300')
time.sleep(0.5)
subprocess.run(['docker', 'kill', '--signal', 'TERM', cid], capture_output=True)
time.sleep(1.0)
st = out('inspect', '--format', '{{.State.Status}}', cid)
print(f'  docker kill --signal TERM(sleep 300 作为 PID 1,没有信号处理):1 秒后容器状态 = {st}')
t0 = time.time(); subprocess.run(['docker', 'stop', '-t', '2', cid], capture_output=True); print(f'  接着 docker stop -t 2:用时 {time.time() - t0:.2f} 秒,退出码 {out("inspect", "--format", "{{.State.ExitCode}}", cid)}')
subprocess.run(['docker', 'rm', '-f', cid], capture_output=True)
purge()

import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c83')
img('alpine:3.20')
purge()
SALT = str(time.time())
DF = f'''FROM alpine:3.20
RUN echo salt-{SALT}
RUN addgroup -S -g 10001 app && adduser -S -u 10001 -G app -h /home/app app
COPY --chown=0:0 root.txt /srv/root.txt
USER app
WORKDIR /srv/work
COPY plain.txt /srv/plain.txt
COPY --chown=app:app owned.txt /srv/owned.txt
CMD ["sh", "-c", "id; echo HOME=$HOME; sleep 60"]
'''
d = ctx('c83', {'Dockerfile': DF, 'root.txt': 'r\n', 'plain.txt': 'p\n', 'owned.txt': 'o\n'})
rc, o = build(d, 'bwlab-c83', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def run(*args, opts=()):
    rc, o = dk('run', '--rm', *LAB, *opts, 'bwlab-c83', *args); return o.strip().replace('\n', ' ; ')
print('== 一:USER 之后容器里的进程(Docker Engine 29.8.2)')
print('  docker inspect 的 Config.User = ' + out('image', 'inspect', '--format', '{{.Config.User}}', 'bwlab-c83'))
print('  默认 CMD 的输出:' + dk('run', '--rm', 'bwlab-c83', 'sh', '-c', 'id; echo HOME=$HOME; whoami')[1].strip().replace('\n', ' ; '))
print('  CapEff / CapBnd:' + run('sh', '-c', 'grep -E "^Cap(Eff|Bnd)" /proc/self/status | tr "\\t\\n" "  "'))
print('  写 /tmp、写 /、写 /etc/x、写 $HOME:' + run('sh', '-c', 'for p in /tmp/x /x /etc/x $HOME/x; do (echo 1 > $p) 2>/dev/null && echo "$p 成功" || echo "$p 失败"; done').replace(' ; ', ';  '))
print('== 二:文件和目录的属主')
print('  ' + run('sh', '-c', 'ls -ldn /srv /srv/work /srv/root.txt /srv/plain.txt /srv/owned.txt | awk \'{print $3":"$4, $9}\''))
print('  USER app 之后 WORKDIR /srv/work 创建出来的目录属主:' + run('stat', '-c', '%u:%g', '/srv/work'))
print('  以 app 身份往 /srv/work 里写文件:' + run('sh', '-c', '(echo 1 > /srv/work/x) 2>&1 && echo 成功 || echo 失败'))
print('  以 app 身份修改 COPY 进来的 /srv/plain.txt(root 属主)和 /srv/owned.txt(app 属主):' + run('sh', '-c', '(echo 1 >> /srv/plain.txt) 2>&1 | head -1; (echo 1 >> /srv/owned.txt) 2>&1 && echo owned可写'))
print('== 三:--user 覆盖,以及没有 passwd 记录的 uid')
print('  --user root:' + run('sh', '-c', 'id; whoami', opts=['--user', 'root']))
print('  --user 12345(passwd 里没有):' + run('sh', '-c', 'id; echo HOME=$HOME; whoami 2>&1', opts=['--user', '12345']))
print('  --user 12345:0(加上 root 组):' + run('sh', '-c', 'id', opts=['--user', '12345:0']))
print('  --user app:' + run('sh', '-c', 'id -u', opts=['--user', 'app']) + ';--user 10001:' + run('sh', '-c', 'id -un', opts=['--user', '10001']))
print('== 四:USER 的时机')
d2 = ctx('c83b', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt2-{SALT}\nUSER 10002\nRUN id -u > /who 2>&1 || true\nRUN mkdir /out 2>&1 || echo "mkdir /out 失败"\n'})
rc, o = build(d2, 'bwlab-c83b', '--provenance=false', '--sbom=false')
msgs = [re.sub(r'^#\d+ [\d.]+ ', '', l.strip()) for l in o.splitlines() if ("denied" in l or "失败" in l) and l.startswith('#')]
print(f'  USER 10002 之后的 RUN:构建退出码 {rc};构建输出里的相关行:{msgs}')
print('  这个镜像里 /who、/out 存在吗?' + dk('run', '--rm', '--user', 'root', 'bwlab-c83b', 'sh', '-c', 'ls -d /who /out 2>&1')[1].strip().replace('\n', ' ; '))
print('  RUN 里的 id -u(构建时的用户):' + ('构建时 USER 10002 生效,所以写 / 失败' if 'denied' in ' '.join(msgs) else ''))
purge()

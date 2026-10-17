import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c81')
img('alpine:3.20')
purge()
SALT = str(time.time())
def mkb(name, tag, df, *extra):
    d = ctx(name, {'Dockerfile': df}); rc, o = build(d, tag, '--provenance=false', '--sbom=false', *extra); return rc, o
def info(tag):
    j = json.loads(out('inspect', '--format', '{{json .}}', tag))
    return f'镜像 Size={int(j["Size"]) / 1e6:.1f} MB,RootFS 层数={len(j["RootFS"]["Layers"])},Cmd={j["Config"].get("Cmd")},Env 有 DEMO 吗={any(e.startswith("DEMO=") for e in (j["Config"].get("Env") or []))}'
BASE = f'FROM alpine:3.20\nENV DEMO=1\nCMD ["echo","from-cmd"]\nRUN echo salt-{SALT}\n'
print('== 一:一层里生成 30 MB,下一层把它删掉(Docker Engine 29.8.2)')
rc, o = mkb('c81a', 'bwlab-c81a', BASE + 'RUN dd if=/dev/urandom of=/big.bin bs=1M count=30 2>/dev/null\nRUN rm /big.bin\n'); assert rc == 0, o[-200:]
print('  ' + info('bwlab-c81a'))
print('  docker history 里各层的大小:' + ' | '.join(l.strip() for l in dk('history', '--format', '{{.Size}}', 'bwlab-c81a')[1].splitlines()[:5]))
print('  容器里 /big.bin 存在吗?' + dk('run', '--rm', 'bwlab-c81a', 'sh', '-c', 'ls /big.bin 2>&1')[1].strip())
print('== 二:同一个 RUN 里创建又删除')
rc, o = mkb('c81b', 'bwlab-c81b', BASE + 'RUN dd if=/dev/urandom of=/big.bin bs=1M count=30 2>/dev/null && rm /big.bin\n'); assert rc == 0, o[-200:]
print('  ' + info('bwlab-c81b'))
print('== 三:多阶段 COPY --from 把整个根文件系统压成一层')
rc, o = mkb('c81c', 'bwlab-c81c', 'FROM scratch\nCOPY --from=bwlab-c81a / /\n'); assert rc == 0, o[-200:]
print('  FROM scratch + COPY --from=<A> / /:' + info('bwlab-c81c'))
print('  运行它:' + dk('run', '--rm', 'bwlab-c81c', '/bin/echo', 'squashed-ok')[1].strip().replace('\n', ' '))
rc, o = mkb('c81d', 'bwlab-c81d', 'FROM scratch\nCOPY --from=bwlab-c81a / /\nENV DEMO=1\nCMD ["echo","from-cmd"]\n'); assert rc == 0, o[-200:]
print('  再补上 ENV 和 CMD:' + info('bwlab-c81d'))
print('== 四:docker export | docker import(见 c17)')
cid = out('create', *LAB, 'bwlab-c81a')
p1 = subprocess.Popen(['docker', 'export', cid], stdout=subprocess.PIPE); p2 = subprocess.run(['docker', 'import', '-', 'bwlab-c81e'], stdin=p1.stdout, capture_output=True, text=True); p1.wait()
print('  ' + info('bwlab-c81e'))
dk('rm', '-f', cid)
print('== 五:docker build --squash')
d = ctx('c81f', {'Dockerfile': BASE + 'RUN dd if=/dev/urandom of=/big.bin bs=1M count=30 2>/dev/null\nRUN rm /big.bin\n'})
rc, o = dk('build', '--squash', '-t', 'bwlab-c81f', '--label', 'bwlab=1', str(d), timeout=300)
print(f'  docker build --squash:退出码 {rc};{[l for l in o.splitlines() if "squash" in l.lower() or "rror" in l][:2]}')
print('  加了 --squash 之后的镜像:' + info('bwlab-c81f') + '(没有被压成 1 层)')
purge()

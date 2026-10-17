import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c7')
img('alpine:3.20')
purge()
DF = '''FROM alpine:3.20
ARG TOKEN=default-token
ARG VERSION=1.0
ENV APP_MODE=prod
RUN echo "构建时 TOKEN=$TOKEN" > /build.txt
RUN echo "版本 $VERSION" > /version.txt
'''
d = ctx('c7a', {'Dockerfile': DF})
print('== 一:ARG 与 ENV 在镜像里留下的痕迹(Docker Engine 29.8.2)')
rc, o = build(d, 'bwlab-c7a', '--build-arg', 'TOKEN=abc123SECRET', '--build-arg', 'VERSION=2.0')
warn = [l.strip() for l in o.split('\n') if 'SecretsUsedInArgOrEnv' in l or 'WARN' in l]
print(f'  构建退出码 {rc};BuildKit 的警告:' + (' | '.join(warn)[:300] or '(无)'))
rc, o = dk('run', '--rm', *LAB, 'bwlab-c7a', 'sh', '-c', 'echo "运行时环境变量里有 APP_MODE=$APP_MODE;TOKEN=[$TOKEN];VERSION=[$VERSION]"; cat /build.txt /version.txt')
for l in o.split('\n'): print('  ' + l)
env = out('inspect', '--format', '{{json .Config.Env}}', 'bwlab-c7a')
print('  docker inspect 的 Config.Env = ' + env)
hist = out('history', '--no-trunc', '--format', '{{.CreatedBy}}', 'bwlab-c7a')
leak = [l for l in hist.split('\n') if 'abc123SECRET' in l]
print(f'  docker history --no-trunc 里含有 "abc123SECRET" 的行数 = {len(leak)}:')
for l in leak: print('    ' + re.sub(r'\s+', ' ', l)[:150])
rc, o = dk('save', '-o', '/dev/null', 'bwlab-c7a')
import tarfile, tempfile
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, 'a.tar'); subprocess.run(['docker', 'save', '-o', p, 'bwlab-c7a'], check=True)
hits = 0
with tarfile.open(p) as t:
    for m in t.getmembers():
        if m.isfile() and m.size < 5_000_000:
            data = t.extractfile(m).read()
            if b'abc123SECRET' in data: hits += 1
shutil.rmtree(tmp, ignore_errors=True)
print(f'  docker save 导出的 tar 里,包含 "abc123SECRET" 的文件(含各层 blob 与配置 JSON)有 {hits} 个')
print('== 二:ARG 的值是缓存键的一部分')
def cached_steps(o):
    res = {}
    for m in re.finditer(r'#(\d+) \[(\d+/\d+)\] (RUN [^\n]*)', o):
        n, step, cmd = m.groups()
        if 'salt-' in cmd: continue
        res[step] = (cmd[:40], bool(re.search(rf'#{n} CACHED', o)))
    return res
SALT = f'RUN echo salt-{time.time()}\n'
d = ctx('c7b', {'Dockerfile': DF.replace('ARG TOKEN', SALT + 'ARG TOKEN', 1)})
build(d, 'bwlab-c7b', '--build-arg', 'TOKEN=t1', '--build-arg', 'VERSION=1')
for label, args in (('什么都不变', ['TOKEN=t1', 'VERSION=1']), ('只改 VERSION', ['TOKEN=t1', 'VERSION=2']), ('只改 TOKEN', ['TOKEN=t2', 'VERSION=1'])):
    rc, o = build(d, 'bwlab-c7b', *sum([['--build-arg', a] for a in args], []))
    cs = cached_steps(o)
    print(f'  [{label}] ' + ';'.join(f'{k} {v[0]!r}→{"CACHED" if v[1] else "重新执行"}' for k, v in sorted(cs.items())))
print('== 三:ARG 在 FROM 之前的作用域')
d = ctx('c7c', {'Dockerfile': 'ARG BASE=alpine:3.20\nFROM ${BASE}\n' + SALT + 'RUN echo "FROM 之后直接用 BASE=[$BASE]"\nARG BASE\nRUN echo "重新声明 ARG BASE 之后=[$BASE]"\n'})
rc, o = build(d, 'bwlab-c7c')
print('  ' + ' | '.join(re.sub(r'^#\d+ [\d.]+ ', '', l.strip()) for l in o.split('\n') if ('FROM 之后' in l or '重新声明' in l) and 'echo' not in l))
print('== 四:ENV 之后的运行时覆盖')
rc, o = dk('run', '--rm', *LAB, '-e', 'APP_MODE=dev', 'bwlab-c7a', 'sh', '-c', 'echo APP_MODE=$APP_MODE')
print('  docker run -e APP_MODE=dev:' + o.strip())
purge()

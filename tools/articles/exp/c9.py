import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c9')
img('alpine:3.20')
purge()
SALT = f'{time.time()}'
DF_NO = f'''FROM alpine:3.20
RUN echo salt-{SALT}
ARG BUST=0
RUN echo "BUST=$BUST"; apk add curl 2>&1 | tail -2
'''
DF_CACHE = f'''FROM alpine:3.20
RUN echo salt-{SALT}-b
ARG BUST=0
RUN --mount=type=cache,target=/var/cache/apk,id=bwlab-apk-{SALT} \\
    echo "BUST=$BUST 进入时缓存目录里有 $(ls /var/cache/apk 2>/dev/null | wc -l) 个文件"; \\
    ln -sf /var/cache/apk /etc/apk/cache; apk add curl 2>&1 | tail -2; \\
    echo "结束时缓存目录里有 $(ls /var/cache/apk | wc -l) 个文件,共 $(du -sk /var/cache/apk | cut -f1) KB"
'''
def run_build(name, df, bust):
    d = ctx(name, {'Dockerfile': df})
    t0 = time.time(); rc, o = build(d, f'bwlab-{name}', '--build-arg', f'BUST={bust}'); t = ms(t0)
    lines = [re.sub(r'^#\d+ [\d.]+ ', '', l.strip()) for l in o.split('\n') if re.match(r'#\d+ [\d.]+ ', l.strip()) and 'salt-' not in l]
    return rc, t, lines
print('== 一:每次都重新执行 apk add curl(用 ARG BUST 强制该层重做),没有缓存挂载 vs 有缓存挂载(Docker Engine 29.8.2;容器能访问互联网上的 Alpine 镜像站,这台机器的网络较慢,绝对时间只代表这次)')
for label, df, name in (('没有缓存挂载', DF_NO, 'c9a'), ('RUN --mount=type=cache,target=/var/cache/apk', DF_CACHE, 'c9b')):
    for bust in (1, 2, 3):
        rc, t, lines = run_build(name, df, bust)
        print(f'  [{label}] BUST={bust}:退出码 {rc},构建用时 {t:.0f} ms')
        for l in lines: print('      ' + l[:100])
print('== 二:缓存挂载里的东西不会进入镜像')
rc, o = dk('run', '--rm', *LAB, 'bwlab-c9b', 'sh', '-c', 'ls /var/cache/apk 2>&1 | wc -l')
print('  从有缓存挂载的镜像启动后 ls /var/cache/apk | wc -l = ' + o.strip().split('\n')[-1] + '(目录里没有文件)')
sa = int(out('image', 'inspect', '--format', '{{.Size}}', 'bwlab-c9a')); sb = int(out('image', 'inspect', '--format', '{{.Size}}', 'bwlab-c9b'))
print(f'  两个镜像的 Size:没有缓存挂载 {sa / 1e6:.2f} MB;有缓存挂载 {sb / 1e6:.2f} MB')
print('== 三:缓存按 id 区分;换一个 id 就是全新的空缓存')
d = ctx('c9c', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt-{SALT}-c\nRUN --mount=type=cache,target=/c,id=bwlab-one-{SALT} sh -c \'echo "id=one 里有 $(ls /c | wc -l) 个文件"; date > /c/f-$(date +%s%N)\'\nRUN --mount=type=cache,target=/c,id=bwlab-two-{SALT} sh -c \'echo "id=two 里有 $(ls /c | wc -l) 个文件"\'\n'})
for i in range(2):
    txt = (d / 'Dockerfile').read_text().replace(f'salt-{SALT}-c', f'salt-{SALT}-c-{i}')
    (d / 'Dockerfile').write_text(txt)
    rc, o = build(d, 'bwlab-c9c')
    print(f'  第 {i + 1} 次构建:' + ' | '.join(re.sub(r'^#\d+ [\d.]+ ', '', l.strip()) for l in o.split('\n') if re.search(r'id=(one|two) 里有', l) and 'echo' not in l))
purge()

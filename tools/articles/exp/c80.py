import sys, os, re, time, subprocess, json, pathlib; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c80')
img('alpine:3.20')
purge()
SALT = str(time.time())
def b(d, tag, *extra):
    t0 = time.time(); rc, o = build(d, tag, '--provenance=false', '--sbom=false', *extra); t = time.time() - t0
    steps = re.findall(r'^#\d+ \[[^\]]*\] (?:RUN|COPY|ADD|ENV)[^\n]*?(?:\n#\d+ (CACHED))?$', o, re.M)
    cached = re.findall(r'^#(\d+) CACHED', o, re.M); 
    # 每一步的名字与是否 CACHED
    names = {}
    for m in re.finditer(r'^#(\d+) \[([^\]]*)\] (.*)$', o, re.M): names.setdefault(m.group(1), (m.group(2), m.group(3)))
    res = [(names[i][1][:34], 'CACHED' if i in cached else '执行') for i in sorted(names, key=int) if names[i][1].split()[0] not in ('FROM',) and not names[i][0].startswith('internal') and ('RUN' in names[i][1] or 'COPY' in names[i][1])]
    return rc, t, res
def show(label, r):
    rc, t, res = r
    print(f'  {label}:用时 {t:.1f} 秒;' + ' | '.join(f'{n} → {s}' for n, s in res))
print('== 一:缓存键是什么:内容变了才失效,只改修改时间不算(Docker Engine 29.8.2)')
d = ctx('c80', {'Dockerfile': f'FROM alpine:3.20\nRUN echo salt-{SALT}\nCOPY app.txt /app.txt\nRUN sleep 2 && echo A > /a\nCOPY dep.txt /dep.txt\nRUN sleep 2 && echo B > /b\n', 'app.txt': 'app v1\n', 'dep.txt': 'dep v1\n'})
show('第 1 次构建(冷)', b(d, 'bwlab-c80'))
show('第 2 次:什么都没改', b(d, 'bwlab-c80'))
os.utime(d / 'app.txt', (time.time() + 100, time.time() + 100))
show('第 3 次:只改 app.txt 的修改时间(touch)', b(d, 'bwlab-c80'))
(d / 'app.txt').write_text('app v2\n')
show('第 4 次:改 app.txt 的内容', b(d, 'bwlab-c80'))
(d / 'dep.txt').write_text('dep v2\n')
show('第 5 次:只改 dep.txt 的内容', b(d, 'bwlab-c80'))
(d / 'app.txt').write_text('app v2\n')
show('第 6 次:app.txt 写入同样的内容(v2)', b(d, 'bwlab-c80'))
print('== 二:指令顺序:把很少变的东西放前面')
for label, df in (('先 COPY . 再装依赖(RUN)', f'FROM alpine:3.20\nRUN echo salt2-{SALT}\nCOPY . /src\nRUN sleep 3 && echo deps > /deps\n'), ('先 COPY 依赖清单、装依赖,再 COPY 源码', f'FROM alpine:3.20\nRUN echo salt3-{SALT}\nCOPY deps.txt /src/deps.txt\nRUN sleep 3 && echo deps > /deps\nCOPY . /src\n')):
    d2 = ctx('c80b', {'Dockerfile': df, 'deps.txt': 'a==1\n', 'main.py': 'print(1)\n'})
    b(d2, 'bwlab-c80b')
    (d2 / 'main.py').write_text('print(2)\n')
    show(f'{label}:改了源码 main.py 后', b(d2, 'bwlab-c80b'))
print('== 三:什么样的 Dockerfile 修改会让缓存失效')
base = f'FROM alpine:3.20\nRUN echo salt4-{SALT}\nRUN sleep 2 && echo X > /x\n'
d3 = ctx('c80c', {'Dockerfile': base}); b(d3, 'bwlab-c80c')
for label, df in (('加了一行注释', base.replace('RUN sleep', '# 这是注释\nRUN sleep')), ('RUN 命令末尾多一个空格', base.replace('echo X > /x', 'echo X > /x ')), ('RUN 命令里改了一个字符', base.replace('echo X', 'echo Y')), ('在前面加一个 ENV', base.replace('RUN sleep', 'ENV FOO=1\nRUN sleep'))):
    d3 = ctx('c80c', {'Dockerfile': df}); r = b(d3, 'bwlab-c80c'); show(label, r)
    d3 = ctx('c80c', {'Dockerfile': base}); b(d3, 'bwlab-c80c')
print('== 四:--no-cache 与 --no-cache-filter')
d4 = ctx('c80d', {'Dockerfile': f'FROM alpine:3.20 AS one\nRUN echo salt5-{SALT} && sleep 2 && echo 1 > /1\nFROM alpine:3.20 AS two\nRUN echo salt6-{SALT} && sleep 2 && echo 2 > /2\nFROM alpine:3.20\nCOPY --from=one /1 /1\nCOPY --from=two /2 /2\n'})
b(d4, 'bwlab-c80d')
show('不加参数(全部命中缓存)', b(d4, 'bwlab-c80d'))
show('--no-cache-filter one(只让 one 阶段重新执行)', b(d4, 'bwlab-c80d', '--no-cache-filter', 'one'))
show('--no-cache(全部重新执行)', b(d4, 'bwlab-c80d', '--no-cache'))
purge()

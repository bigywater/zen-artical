import sys, os, re, time, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c10')
img('alpine:3.20')
purge()
def salted(df): return df.replace('@SALT@', str(time.time()))
def timed(name, df, *extra):
    d = ctx(name, {'Dockerfile': salted(df)})
    t0 = time.time(); rc, o = build(d, f'bwlab-{name}', *extra); t = ms(t0)
    return rc, t, o
def steps(o):
    return [re.sub(r'\s+', ' ', l.strip())[:80] for l in o.split('\n') if re.match(r'#\d+ \[', l.strip()) and 'FROM docker.io' not in l]
print('== 一:互不依赖的两个阶段各睡 4 秒,最终阶段从两边各 COPY 一个文件(Docker Engine 29.8.2,BuildKit)')
DF_PAR = '''FROM alpine:3.20 AS a
RUN echo @SALT@ && sleep 4 && echo A > /a.txt
FROM alpine:3.20 AS b
RUN echo @SALT@ && sleep 4 && echo B > /b.txt
FROM alpine:3.20
COPY --from=a /a.txt /a.txt
COPY --from=b /b.txt /b.txt
'''
rc, t, o = timed('c10a', DF_PAR)
print(f'  构建退出码 {rc};总用时 {t / 1000:.2f} 秒(串行执行至少要 8 秒)')
print('  各步骤:' + ' | '.join(steps(o)))
print('== 二:有依赖的两个阶段(b 以 a 为基础)只能串行')
DF_SER = '''FROM alpine:3.20 AS a
RUN echo @SALT@ && sleep 4 && echo A > /a.txt
FROM a AS b
RUN sleep 4 && echo B > /b.txt
FROM alpine:3.20
COPY --from=b /a.txt /b.txt /
'''
rc, t, o = timed('c10b', DF_SER)
print(f'  构建退出码 {rc};总用时 {t / 1000:.2f} 秒')
print('== 三:最终镜像用不到的阶段根本不会被构建')
DF_UNUSED = '''FROM alpine:3.20 AS never
RUN echo @SALT@ && echo "这一步被执行了" && sleep 3
FROM alpine:3.20 AS used
RUN echo @SALT@ && echo "used 阶段执行" > /u.txt
FROM alpine:3.20
COPY --from=used /u.txt /u.txt
'''
rc, t, o = timed('c10c', DF_UNUSED)
print(f'  构建退出码 {rc};总用时 {t / 1000:.2f} 秒;构建输出里 RUN 真正打印出 "这一步被执行了" 的行数 = {len(re.findall(r'^#\d+ [\d.]+ 这一步被执行了', o, re.M))};出现的步骤:' + ' | '.join(steps(o)))
rc, t, o = timed('c10d', DF_UNUSED.replace('@SALT@', '@SALT@'), '--target', 'never')
print(f'  同一个 Dockerfile 用 --target never 单独构建那个阶段:总用时 {t / 1000:.2f} 秒;步骤:' + ' | '.join(steps(o)))
print('== 四:同样的写法,把 a、b 合并成同一个阶段里的两条 RUN —— 只能串行')
DF_ONE = '''FROM alpine:3.20
RUN echo @SALT@ && sleep 4 && echo A > /a.txt
RUN sleep 4 && echo B > /b.txt
'''
rc, t, o = timed('c10e', DF_ONE)
print(f'  构建退出码 {rc};总用时 {t / 1000:.2f} 秒')
print('== 五:4 个互不依赖的阶段各睡 4 秒')
DF_4 = 'FROM alpine:3.20 AS a1\nRUN echo @SALT@ && sleep 4 && echo 1 > /x\nFROM alpine:3.20 AS a2\nRUN echo @SALT@ && sleep 4 && echo 2 > /x\nFROM alpine:3.20 AS a3\nRUN echo @SALT@ && sleep 4 && echo 3 > /x\nFROM alpine:3.20 AS a4\nRUN echo @SALT@ && sleep 4 && echo 4 > /x\nFROM alpine:3.20\nCOPY --from=a1 /x /x1\nCOPY --from=a2 /x /x2\nCOPY --from=a3 /x /x3\nCOPY --from=a4 /x /x4\n'
rc, t, o = timed('c10f', DF_4)
print(f'  构建退出码 {rc};总用时 {t / 1000:.2f} 秒(完全并行约 4 秒,完全串行 16 秒)')
purge()

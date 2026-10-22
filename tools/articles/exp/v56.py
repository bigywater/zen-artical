import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import subprocess as sp, re
tee('v56'); reset()
print('配置热更新:哪些配置可以不重启生效、怎样换才安全。用一个 Go 程序(go1.27.1,darwin/arm64)演示:换配置的三种写法与数据竞争、哪些配置项“热更新”实际上不会生效、坏配置推送的后果、以及触发重载的几种方式(SIGHUP、轮询文件)的延迟。Go 程序源码在 vtmp/v56/main.go,本实验用 Python 编排并解析它的输出')
D = TT / 'v56'; BIN = D / 'v56main'; BINR = D / 'v56mainrace'
r = sp.run(['go', 'build', '-o', str(BIN), 'main.go'], cwd=D, capture_output=True, text=True); assert r.returncode == 0, r.stderr
r = sp.run(['go', 'build', '-race', '-o', str(BINR), 'main.go'], cwd=D, capture_output=True, text=True); assert r.returncode == 0, r.stderr
def run(*a, binary=BIN, timeout=120):
    return sp.run([str(binary), *map(str, a)], capture_output=True, text=True, timeout=timeout)

# ============ 一 ============
print('== 一:换配置的三种写法。配置里有两个必须一起变的字段 A 和 B(不变式 B == 2×A)。写入方每约 200 µs 发布一份新配置,8 个读取方在循环里不停地读 A 和 B 并检查不变式。三种发布方式:原地改字段(inplace);每次新建一份只读的快照,用 atomic.Pointer 整体换指针(atomic);用 RWMutex 保护原地改(rwmutex)。分两种情形,每种 2 s:写入方连续写 A、B(间隔近似 0),以及写 A 和写 B 之间隔 50 µs(模拟中间还要解析下一个配置项)')
for gap in (0, 50):
    r = run('torn', 2, gap); rows = []
    for line in r.stdout.strip().splitlines():
        m = re.match(r'torn (\w+) reads=(\d+) bad=(\d+) writes=(\d+)', line); rows.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    print(f'  写 A 与写 B 之间隔 {gap} µs:')
    table(rows, ['发布方式', '读取次数(8 个读取方合计)', '读到违反不变式的次数', '发布次数'])
rows = []
for v in ('inplace', 'atomic', 'rwmutex'):
    r = run('torn', 0.5, 0, v, binary=BINR); n = r.stderr.count('WARNING: DATA RACE'); rows.append((v, n))
table(rows, ['发布方式(用 go build -race 构建,间隔 0 µs,0.5 s)', '竞态检测器报告 “WARNING: DATA RACE” 的次数'])
print('  不加保护地原地改字段:两次写之间没有间隔时,违反不变式的读取相对读取总数极少(各次运行的数字不一样,开发中的一次 1 s 运行里甚至一次都没有读到),但竞态检测器每次都报告了数据竞争;写入之间一旦有间隔(解析、校验都会产生),读取方就大量读到半新半旧的配置。atomic 方式从来没有读到过半新半旧的配置,读取次数与不加保护的相近;RWMutex 方式也没有,但这个紧循环里读取次数少得多(每次读都要加锁)')

# ============ 二 ============
print('== 二:哪些配置换了之后会立刻生效。服务启动时配置是版本 1(限速 50、worker 4 个),运行中用 atomic.Pointer 换成版本 2(限速 200、worker 8 个、监听地址换成 127.0.0.1:1),再换成版本 3(worker 8 个)。(a)请求处理里每次读配置的值;(b)监听地址是服务启动时用过一次的值;(c)worker 池的大小是启动时用过一次的值,以及一个写了 Resize 的池')
r = run('live'); out = {}
for line in r.stdout.strip().splitlines():
    k, _, rest = line.partition(' '); out[k] = out.get(k, '') + rest + ' '
a = dict(re.findall(r'(\w+)=([\w.:-]+)', out['live_a'])); b = dict(re.findall(r'(\w+)=([\w.:]+)', out['live_b'])); c = out['live_c']
G = lambda pat: re.search(pat, c).group(1)
table([('(a)请求里每次读配置(换指针之后发起的请求)', f'一共 {a["total"]} 个请求;换完指针之后发起的请求里仍然用旧版本的有 {a["stale_after_swap"]} 个;第一个读到新版本的请求发起于换指针之后 {a["first_v2_start_ms"]} ms'),
       ('(b)配置里的监听地址', f'换配置之后,原来的地址还能访问(返回 {b["old_addr_ok"]});配置里的新地址:{b["new_addr"]}'),
       ('(c)启动时按配置起的 worker 数', f'{G(r"started=(\d+)")} 个;配置改成 8 个、没有调用 Resize,500 ms 后仍是 {G(r"after_conf_swap_without_resize=(\d+)")} 个'),
       ('(c)带 Resize 的池:4 → 8', f'调用 Resize(8) 后 worker 数变成 {G(r"resize_up_to_8_ms=[\d.]+ live=(\d+)")},用时 {G(r"resize_up_to_8_ms=([\d.]+)")} ms(显示为 0.000 表示小于 1 µs)'),
       ('(c)带 Resize 的池:8 → 2', f'每个任务 100 ms、队列里还有任务时,从 Resize(2) 到只剩 2 个 worker 用了 {G(r"resize_down_to_2_ms=([\d.]+)")} ms')], ['配置项', '结果'])
print('  每次请求都从原子指针里读的值,换完指针之后的请求就用新值;只在启动时用过一次的值(监听地址、按配置起的 worker 数),换了配置也不会让已经在运行的东西变化,需要专门写“重新绑定 / 调整大小”的代码;缩小 worker 池要等在忙的 worker 做完手上的任务(这里的 worker 每轮在“退出信号”和“新任务”之间由 select 随机选一个)')

# ============ 三 ============
print('== 三:坏配置推送的后果。服务按 “限速 100 次/秒” 工作,客户端以约 300 次/秒的速度请求(所以正常情况下约三分之二的请求会被限流拒绝)。运行约 1.2 s 后推送一份坏配置,统计推送之后 1 s 里被拒绝的请求。三种加载方式:naive_ignore_err(解析出错也把得到的零值配置存进去)、naive_no_range(解析出错就保留旧配置,解析成功就存,不检查取值范围)、validated(解析出错或取值不在 1 到 10000 就保留旧配置)。三种推送:bad_json(不完整的 JSON)、zero(限速写成 0)、huge(限速写成 1000000)')
rows = []
for loader in ('naive_ignore_err', 'naive_no_range', 'validated'):
    for push in ('bad_json', 'zero', 'huge'):
        r = run('bad', loader, push); m = re.search(r'bad (\w+) (\w+) result=(.+?) before_rejected=(\d+)/(\d+) after_rejected=(\d+)/(\d+) limit_now=(\d+)', r.stdout)
        assert m, (loader, push, r.stdout, r.stderr[:300])
        rows.append((loader, push, m.group(3), f'{m.group(4)}/{m.group(5)}', f'{m.group(6)}/{m.group(7)}', m.group(8)))
table(rows, ['加载方式', '推送', '加载结果', '推送之前被拒绝/总请求', '推送之后 1 s 被拒绝/总请求', '推送后生效的限速'])
print('  解析出错时存零值会让所有请求被拒绝;解析成功但值不合理(0 或大了一万倍)时,没有范围检查的加载方式会让限速失效或者把所有请求都拦下;对 bad_json,凡是解析出错就保留旧配置的加载方式(naive_no_range 和 validated)都不受影响;对取值不合理的 zero 和 huge,只有做了范围检查的 validated 保住了原来的限速')

# ============ 四 ============
print('== 四:触发重载的方式与延迟。(a)Go 程序用 signal.Notify 接 SIGHUP,外部 kill -HUP 200 次,每次间隔 20 ms,测从发信号到处理函数拿到信号的时间;(b)程序按固定间隔轮询配置文件的内容,Python 在随机时刻原子替换(写临时文件再 rename)文件内容共 30 次,测从替换到程序发现变化的时间,轮询间隔 100 ms 和 1000 ms')
p = sp.Popen([str(BIN), 'hup'], stdout=sp.PIPE, text=True); assert p.stdout.readline().strip() == 'ready'
lat = []; sent = []
for i in range(200):
    t = time.time_ns(); os.kill(p.pid, signal.SIGHUP); sent.append(t); time.sleep(0.02)
time.sleep(0.2); p.terminate()
got = [int(l.split()[1]) for l in p.stdout.read().splitlines() if l.startswith('hup ')]
lat = [(g - s) / 1e6 for g, s in zip(got, sent)]
rows = [('SIGHUP', f'{len(got)}/200', f'{min(lat):.3f} / {statistics.median(lat):.3f} / {max(lat):.3f}')]
for ms in (100, 1000):
    f = D / f'cfg_{ms}.txt'; f.write_text('v-1'); p = sp.Popen([str(BIN), 'poll', str(ms), str(f)], stdout=sp.PIPE, text=True); assert p.stdout.readline().strip() == 'ready'
    rng = random.Random(3 + ms); ts = {}
    for i in range(30):
        time.sleep(rng.uniform(0.15, 1.3)); tmp = D / 'cfg.tmp'; tmp.write_text(f'v{i}'); t = time.time_ns(); os.replace(tmp, f); ts[f'v{i}'] = t
    time.sleep(ms / 1000 + 0.3); p.terminate()
    ch = {}
    for l in p.stdout.read().splitlines():
        if l.startswith('chg '): _, ns, v = l.split(' ', 2); ch[v] = int(ns)
    ll = [(ch[v] - ts[v]) / 1e6 for v in ts if v in ch]
    rows.append((f'轮询文件,间隔 {ms} ms', f'{len(ll)}/30', f'{min(ll):.1f} / {statistics.median(ll):.1f} / {max(ll):.1f}'))
table(rows, ['触发方式', '发现/收到的次数', '延迟 最小 / 中位 / 最大(ms)'])
print('  信号几乎是即时的,但只能通知“同一台机器上有人发了信号”,不会带内容、也不跨机器;轮询的延迟在 0 到间隔之间,而且有间隔内多次变更被合并的可能;Nacos 之类的推送延迟见第 55 篇')
print('ERRORS', dict(ERRORS))

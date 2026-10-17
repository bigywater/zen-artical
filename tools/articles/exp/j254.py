import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j254'); R = {}
N, CH = 3000, 100
src = ['public class Flood {', '  static long acc;']
for i in range(N): src.append(f'  static int m{i}(int x) {{ int s = x * {i%17+3}; for (int k = 0; k < {i%5+2}; k++) {{ s += (s ^ {i}) % {i%11+3}; if ((s & 1) == 0) s += k; }} return s + {i}; }}')
for c in range(N // CH): src.append(f'  static void run{c}(int n) {{ for (int i = 0; i < n; i++) {{' + ''.join(f' acc += m{c*CH+j}(i);' for j in range(CH)) + ' } }')
src.append('  static void runAll(int rounds, int n, boolean print) { long t0 = System.nanoTime(); for (int r = 0; r < rounds; r++) { ' + ''.join(f'run{c}(n); ' for c in range(N // CH)) + 'if (print) System.out.println("RES round " + r + " " + (System.nanoTime() - t0) / 1_000_000); } if (print) System.out.println("RES total " + (System.nanoTime() - t0) / 1_000_000); }')
src.append('  public static void main(String[] a) throws Exception { runAll(Integer.parseInt(a[0]), Integer.parseInt(a[1]), true); }')
src.append('}')
PROBE = r'''
public class Probe { static long acc;
  static int probe(int x) { int s = x; for (int k = 0; k < 40; k++) { s = s * 31 + k; if ((s & 7) == 0) s ^= k; } return s; }
  public static void main(String[] a) throws Exception { boolean flood = a[0].equals("flood"); Thread t = null;
    if (flood) { t = new Thread(() -> Flood.runAll(6, 3000, false)); t.start(); Thread.sleep(50); }
    long t0 = System.nanoTime(); int B = 2000, NB = 400; double[] ms = new double[NB]; double[] at = new double[NB]; int x = 0;
    for (int b = 0; b < NB; b++) { long s = System.nanoTime(); for (int i = 0; i < B; i++) acc += probe(x++); ms[b] = (System.nanoTime() - s) / 1e6; at[b] = (System.nanoTime() - t0) / 1e6; }
    double[] last = Arrays.copyOfRange(ms, NB - 50, NB); Arrays.sort(last); double steady = last[25]; int fast = -1; for (int b = 0; b < NB; b++) { boolean ok = true; for (int c = b; c < Math.min(NB, b + 5); c++) if (ms[c] > steady * 1.5) ok = false; if (ok) { fast = b; break; } }
    System.out.println("RES 稳态每批 " + String.format("%.3f", steady) + " ms;前 3 批 " + String.format("%.2f %.2f %.2f", ms[0], ms[1], ms[2]) + " ms;连续 5 批都 <= 1.5 倍稳态 从第 " + fast + " 批(时刻 " + String.format("%.0f", at[fast]) + " ms)开始;最慢的一批 " + String.format("%.2f", Arrays.stream(ms).max().getAsDouble()) + " ms");
    if (t != null) t.join(); System.exit(0); } }
'''
PROBE = 'import java.util.*;\n' + PROBE
d = jdir('j254a'); (d / 'Flood.java').write_text('\n'.join(src)); (d / 'Probe.java').write_text(PROBE); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Flood.java', 'Probe.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2000]); sys.exit()
def parse_q(o):
    c1 = c2 = 0; cur = 0; sec = None
    for l in o.splitlines():
        if l.startswith('Current compiles'): sec = 'cur'
        elif l.startswith('C1 compile queue'): sec = 'c1'
        elif l.startswith('C2 compile queue'): sec = 'c2'
        elif 'bytes)' in l:
            if sec == 'c1': c1 += 1
            elif sec == 'c2': c2 += 1
            elif sec == 'cur': cur += 1
    return cur, c1, c2
print('== 一:用 jcmd <pid> Compiler.queue 观察编译队列:3000 个小方法各被调用数千次(3 轮),每约 0.15 s 取一次队列')
flag = subprocess.run(['java', '-XX:+PrintFlagsFinal', '-version'], env=E, capture_output=True, text=True).stdout
cic = re.search(r'CICompilerCount\s*=\s*(\d+)', flag).group(1); print(f'  本机默认 CICompilerCount = {cic}(逻辑 CPU {os.cpu_count()} 个)')
for lab, fl in (('默认编译线程', []), ('-XX:CICompilerCount=2(1 个 C1 + 1 个 C2)', ['-XX:CICompilerCount=2'])):
    p = subprocess.Popen(['java', *fl, '-cp', 'out', 'Flood', '8', '3000'], cwd=d, env=E, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); t0 = time.time(); samples = []; first = None
    while p.poll() is None:
        time.sleep(0.1); q = subprocess.run(['jcmd', str(p.pid), 'Compiler.queue'], capture_output=True, text=True, env=E)
        if q.returncode != 0: break
        cur, c1, c2 = parse_q(q.stdout); samples.append((time.time() - t0, cur, c1, c2))
        if c2 > 3 and (first is None or c2 > first[0]): first = (c2, q.stdout)
    out = p.stdout.read(); p.wait()
    print(f'  [{lab}] 共取样 {len(samples)} 次;C1 队列非空 {sum(1 for s in samples if s[2] > 0)} 次,C2 队列非空 {sum(1 for s in samples if s[3] > 0)} 次;C2 队列长度最大 {max(s[3] for s in samples)},C1 队列长度最大 {max(s[2] for s in samples)},同时在编译的最多 {max(s[1] for s in samples)} 个;程序自己报告 ' + ' '.join(l[4:] for l in out.splitlines() if l.startswith('RES total')))
    print('      取样时刻 / 正在编译 / C1 队列 / C2 队列:' + ';  '.join(f'{s[0]:.1f}s {s[1]}/{s[2]}/{s[3]}' for s in samples[:16]))
    if first: print('      C2 队列最长时的快照(节选):'); [print('          ' + l) for l in [x for x in first[1].splitlines() if x.strip()][1:10]]
print('== 二:CICompilerCount 对完成时间的影响:同一个负载(8 轮,每轮 3000 个方法 × 3000 次),每种设置跑 3 次取中位数')
def flood_run(flags, rounds=8):
    r = subprocess.run(['java', *flags, '-cp', 'out', 'Flood', str(rounds), '3000'], cwd=d, env=E, capture_output=True, text=True, timeout=300); o = r.stdout
    rd = {int(m.group(1)): int(m.group(2)) for m in re.finditer(r'RES round (\d+) (\d+)', o)}; tot = int(re.search(r'RES total (\d+)', o).group(1)); return rd, tot
for lab, fl in (('CICompilerCount=2', ['-XX:CICompilerCount=2']), ('CICompilerCount=3', ['-XX:CICompilerCount=3']), (f'默认({cic})', []), ('CICompilerCount=8', ['-XX:CICompilerCount=8'])):
    rs = [flood_run(fl) for _ in range(3)]; tots = sorted(r[1] for r in rs); r0 = sorted(r[0][0] for r in rs)[1]; r1 = sorted(r[0][1] - r[0][0] for r in rs)[1]; last = sorted(r[0][7] - r[0][6] for r in rs)[1]
    print(f'  {lab}:总用时中位数 {tots[1]} ms(最快 {tots[0]},最慢 {tots[2]});第 0 轮 {r0} ms,第 1 轮 {r1} ms,第 7 轮 {last} ms')
print('== 三:-Xbatch(编译阻塞调用线程)与默认的后台编译:同一个负载,每种跑 3 次')
for lab, fl in (('默认(后台编译)', []), ('-Xbatch', ['-Xbatch']), ('-Xint(不编译)', ['-Xint'])):
    rs = [flood_run(fl, 3) for _ in range(3)]; tots = sorted(r[1] for r in rs); r0 = sorted(r[0][0] for r in rs)[1]; last = sorted(r[0][2] - r[0][1] for r in rs)[1]
    print(f'  {lab}:3 轮总用时中位数 {tots[1]} ms(最快 {tots[0]},最慢 {tots[2]});第 0 轮 {r0} ms,第 2 轮 {last} ms')
print('== 四:队列积压让热点方法的编译变晚:Probe 的 probe() 每批 2000 次调用,看它多久变快;同时另一个线程在跑上面的 3000 方法洪水')
for lab, args, fl in (('只有 Probe', ['alone'], []), ('Probe + 洪水(默认编译线程)', ['flood'], []), ('Probe + 洪水,CICompilerCount=2', ['flood'], ['-XX:CICompilerCount=2'])):
    outs = []
    for _ in range(3):
        r = subprocess.run(['java', *fl, '-cp', 'out', 'Probe', *args], cwd=d, env=E, capture_output=True, text=True, timeout=200); outs.append(r.stdout.strip().splitlines()[-1][4:])
    print(f'  [{lab}] ' + '  ||  '.join(outs))

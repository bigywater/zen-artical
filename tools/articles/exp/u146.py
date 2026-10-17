import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u146'); R = {}
def build(name, code):
    ok, d, binp, _ = rustc(name, code, release=True); assert ok, d; return str(binp)
def sh_(cmd, inp=None): p = subprocess.run(cmd, shell=True, capture_output=True, text=True, input=inp, executable='/bin/bash'); return p.returncode, p.stdout, p.stderr
b = build('u146a', '''
    use std::io::{self, BufRead, Read, IsTerminal, Write};
    fn main() {
        let a = std::env::args().nth(1).unwrap_or_default();
        match a.as_str() {
            "tty" => println!("stdin 是终端: {}  stdout 是终端: {}  stderr 是终端: {}", io::stdin().is_terminal(), io::stdout().is_terminal(), io::stderr().is_terminal()),
            "lines" => { let n = io::stdin().lock().lines().count(); println!("从 stdin 读到 {} 行", n); }
            "all" => { let mut s = String::new(); let n = io::stdin().read_to_string(&mut s).unwrap(); println!("read_to_string 读到 {} 字节,{} 个单词", n, s.split_whitespace().count()); }
            "split" => { println!("这行写到 stdout"); eprintln!("这行写到 stderr"); }
            "order" => { for i in 0..3 { println!("out{}", i); eprintln!("err{}", i); } }
            "many" => { for i in 0..100000 { println!("line {}", i); } }
            "closed" => { let r = io::stdout().write_all(b"hello\\n"); println!("(这行不会显示)"); }
            "partial" => { print!("先写半行"); io::stdout().flush().ok(); std::thread::sleep(std::time::Duration::from_millis(600)); println!("(换行)"); }
            "nolf" => { print!("没有换行的输出"); std::thread::sleep(std::time::Duration::from_millis(600)); println!(); }
            _ => {}
        }
    }
''')
print('== 一:程序怎么知道自己连着终端:IsTerminal。直接在管道/文件里运行是 false;给它一个伪终端(pty)是 true')
for label, cmd in [('stdout 接管道(| cat)', f'{b} tty | cat'), ('stdout 重定向到文件', f'{b} tty > /tmp/u146.out; cat /tmp/u146.out'), ('stdin 来自 /dev/null,其余接管道', f'{b} tty < /dev/null 2>&1 | cat')]:
    rc, o, e = sh_(cmd); print(f'  {label:<30} → {o.strip().replace(chr(13), "")}'); R.setdefault('tty', {})[label] = o.strip().replace('\r', '')
import pty
m, sl = pty.openpty(); import select
p = subprocess.Popen([b, 'tty'], stdin=sl, stdout=sl, stderr=sl); os.close(sl); out = ''
while True:
    r_, _, _ = select.select([m], [], [], 1.0)
    if not r_: break
    try: d = os.read(m, 4096)
    except OSError: break
    if not d: break
    out += d.decode()
p.wait(); out = out.strip().replace('\r', ''); os.close(m)
print(f'  {"伪终端(pty)上运行":<30} → {out}'); R['tty']['pty'] = out
print()
print('== 二:读 stdin:管道输入、重定向文件、here-string;空输入')
for label, cmd, inp in [('echo 管道 3 行', f'printf "a\\nb\\nc\\n" | {b} lines', None), ('文件重定向 < 文件', f'printf "x y z\\nlast line no newline" > /tmp/u146.in; {b} lines < /tmp/u146.in', None), ('read_to_string 单词数', f'printf "one two\\nthree" | {b} all', None), ('空输入 < /dev/null', f'{b} lines < /dev/null', None)]:
    rc, o, e = sh_(cmd); print(f'  {label:<24} → {o.strip()}'); R.setdefault('stdin', {})[label] = o.strip()
print('  (最后一行没有换行符也算一行:lines 数的是 \\n 分隔的片段,"last line no newline" 被算作第 2 行)')
print()
print('== 三:stdout 与 stderr 是两个独立的流:分别重定向')
for label, cmd in [('默认(两个都在终端/捕获)', f'{b} split'), ('2>/dev/null 丢掉 stderr', f'{b} split 2>/dev/null'), ('1>/dev/null 丢掉 stdout', f'{b} split 1>/dev/null'), ('2>&1 合并(经管道)', f'{b} split 2>&1 | cat')]:
    rc, o, e = sh_(cmd); print(f'  {label:<26} stdout={o.strip().splitlines()}  stderr={e.strip().splitlines()}'); R.setdefault('streams', {})[label] = [o.strip().splitlines(), e.strip().splitlines()]
print()
print('== 四:合并到同一个管道时的顺序:println! 与 eprintln! 交替写 3 次,2>&1 之后看到的顺序')
rc, o, e = sh_(f'{b} order 2>&1 | cat'); print('  合并后的行顺序:', o.split()); R['order'] = o.split()
print()
print('== 五:stdout 接到管道时的缓冲:print! 没有换行且没有 flush 的内容,读者要等到换行才看到;显式 flush 则立刻到达')
def timed(cmd):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, executable='/bin/bash'); t0 = time.perf_counter(); first = None; chunks = []
    while True:
        d = os.read(p.stdout.fileno(), 4096)
        if not d: break
        if first is None: first = time.perf_counter() - t0
        chunks.append((round(time.perf_counter() - t0, 1), d.decode()))
    p.wait(); return chunks
for label, mode in [('print! + 显式 flush(600 ms 后才换行)', 'partial'), ('print! 不 flush,没有换行(600 ms 后才换行)', 'nolf')]:
    ch = timed(f'{b} {mode}'); print(f'  {label}:读者收到的数据块(到达时刻 s, 内容):{ch}'); R.setdefault('buf', {})[label] = ch
print()
print('== 六:stdout 出错时:stdout 被关闭(>&-)时 println! 不会 panic(Rust 把这种情况当作成功);但写入真正失败(管道对端已关闭)会 panic')
rc, o, e = sh_(f'{b} closed >&-'); print(f'  stdout 关闭(>&-):退出码 {rc},stderr {e.strip().splitlines()[:2]}(静默忽略)'); R['closed'] = [rc, e.strip().splitlines()[:2]]
rc, o, e = sh_(f'{b} many | true'); L = [l for l in e.strip().splitlines() if 'note:' not in l][:3]; print(f'  stdout 接到已经关闭的管道(| true):退出码 {rc},stderr {L}'); R['full'] = [rc, L]
save('u146', R)

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import statistics, glob, binascii
tee('u165'); R = {}
base = RS / 'proj' / 'u165'; shutil.rmtree(base, ignore_errors=True); shutil.rmtree(RS / 'fz_target', ignore_errors=True)
(base / 'src').mkdir(parents=True)
(base / 'Cargo.toml').write_text('[package]\nname = "fz"\nversion = "0.1.0"\nedition = "2024"\n')
LIB = '''
    pub fn parse(data: &[u8]) -> Option<u32> {
        if data.len() < 4 || &data[..4] != b"FUZZ" { return None; }
        if data.len() > 4 && data[4] == b'!' {
            if data.len() > 5 && data[5] == b'?' {
                return Some(data[6] as u32);
            }
        }
        Some(0)
    }
    pub fn parse_fixed(data: &[u8]) -> Option<u32> {
        if data.len() < 4 || &data[..4] != b"FUZZ" { return None; }
        if data.len() > 4 && data[4] == b'!' {
            if data.len() > 5 && data[5] == b'?' {
                return data.get(6).map(|b| *b as u32);
            }
        }
        Some(0)
    }
    pub fn payload(data: &[u8]) -> u8 {
        if data.len() < 2 { return 0; }
        let n = data[0] as usize;
        unsafe { *data.get_unchecked(1 + n) }
    }
'''
(base / 'src' / 'lib.rs').write_text(show(LIB) + '\n')
def fz(args, timeout=300, extra=None):
    env = dict(ENVN); env.update(extra or {}); env['CARGO_TARGET_DIR'] = str(RS / 'fz_target')
    rc, o, e = sh(['cargo', '+nightly', 'fuzz', *args], cwd=base, env=env, timeout=timeout); return rc, clean(o + e)
def pr(txt, n=30, ind='    ', w=200):
    L = txt.split('\n'); print('\n'.join(ind + l[:w] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
def target(name, body):
    p = base / 'fuzz' / 'fuzz_targets' / f'{name}.rs'; p.write_text('#![no_main]\n\nuse libfuzzer_sys::fuzz_target;\n\nfuzz_target!(|data: &[u8]| {\n    ' + body + '\n});\n'); return p
print('== 一:cargo fuzz init 生成的目录;被测代码;fuzz 目标')
rc, o = fz(['init']); print('  cargo fuzz init:退出码', rc); pr(o, 4)
rc, o = fz(['add', 'parse']); rc, o = fz(['add', 'parse_fixed']); rc, o = fz(['add', 'payload'])
(base / 'fuzz' / 'fuzz_targets' / 'fuzz_target_1.rs').unlink(missing_ok=True)
txt = (base / 'fuzz' / 'Cargo.toml').read_text(); txt = re.sub(r'\n\[\[bin\]\]\nname = "fuzz_target_1".*?\n(?=\n|\Z)', '\n', txt, flags=re.S); (base / 'fuzz' / 'Cargo.toml').write_text(txt)
target('parse', 'let _ = fz::parse(data);'); target('parse_fixed', 'let _ = fz::parse_fixed(data);'); target('payload', 'std::hint::black_box(fz::payload(data));')
files = sorted(str(p.relative_to(base)) for p in base.rglob('*') if p.is_file() and 'target' not in p.parts and 'Cargo.lock' not in p.name)
print('  生成/使用的文件:'); print('\n'.join('    ' + f for f in files)); R['files'] = files
print('  被测代码 src/lib.rs(parse 里藏了一个 bug:长度恰好是 6 时 data[6] 越界):'); print('\n'.join('    ' + l for l in numbered(LIB).split('\n')[:9]))
print('  fuzz/fuzz_targets/parse.rs:'); print('\n'.join('    ' + l for l in numbered((base / 'fuzz' / 'fuzz_targets' / 'parse.rs').read_text()).split('\n')))
print()
print('== 二:运行 cargo fuzz run parse(固定 -seed=1;没有给任何初始语料);选取日志里的覆盖率增长行')
t0 = time.perf_counter(); rc, o = fz(['run', 'parse', '--', '-max_total_time=60', '-seed=1']); dt = time.perf_counter() - t0
L = o.split('\n'); news = [l for l in L if re.match(r'#\d+\s+(NEW|INITED|REDUCE)', l)]
print(f'  退出码 {rc};含编译与运行共 {dt:.1f} 秒')
for l in L:
    if l.startswith(('INFO: Seed', 'INFO: A corpus', 'INFO: -max')): print('    ' + l[:200])
print('  覆盖率相关日志(#执行次数 事件 cov=覆盖的边 ft=特征数 corp=语料数/字节 exec/s):')
print('\n'.join('    ' + re.sub(r'\s+', ' ', l)[:150] for l in news[:30]))
msg = [l for l in L if 'panicked at' in l or 'index out of bounds' in l]; print('  崩溃信息:'); print('\n'.join('    ' + l[:200].replace(str(RS), '<实验目录>') for l in msg[:3]))
for l in L:
    if l.startswith(('SUMMARY', 'MS:', 'Base64')) or l.startswith('0x46'): print('    ' + l[:200])
crash = re.search(r'(fuzz/artifacts/parse/crash-[0-9a-f]+)', o).group(1)
R['run'] = dict(rc=rc, secs=round(dt, 1), news=[re.sub(r'\s+', ' ', l) for l in news], msg=msg[:3], crash=crash)
last = [re.sub(r'\s+', ' ', l) for l in L if l.startswith('#') and 'cov:' in l][-1]; print('  最后一条统计:', last[:150])
pb = RS / 'fz_target' / 'aarch64-apple-darwin' / 'release' / 'parse'; tmpd = RS / 'u165_tmp'; shutil.rmtree(tmpd, ignore_errors=True); tmpd.mkdir()
def crashes(n_): return subprocess.run([str(pb), '-seed=1', f'-runs={n_}', f'-artifact_prefix={tmpd}/'], capture_output=True, text=True).returncode != 0
lo, hi = 1, 2_000_000
assert crashes(hi) and crashes(hi) == crashes(hi)
while lo < hi:
    mid = (lo + hi) // 2
    if crashes(mid): hi = mid
    else: lo = mid + 1
print(f'  同一个种子重放(二分 -runs):第 {lo} 次执行时触发崩溃(-runs={lo - 1} 不崩,-runs={lo} 崩);另两次重复结果一致:{crashes(lo) and not crashes(lo - 1)}'); R['run']['found_at'] = lo
print()
print('== 三:失败的输入与复现:把崩溃输入存成文件,单独重放;fmt 显示 Debug 形式')
data = (base / crash).read_bytes(); print(f'  崩溃输入 {len(data)} 字节:{list(data)}  = {data!r}'); R['crash_bytes'] = list(data)
rc, o = fz(['run', 'parse', crash]); L = o.split('\n'); print('  重放(cargo fuzz run parse <崩溃文件>):退出码', rc)
print('\n'.join('    ' + l[:200] for l in L if 'panicked at' in l or 'index out of bounds' in l or 'Executed' in l or l.startswith(('SUMMARY', 'Error'))))
rc2, o2 = fz(['fmt', 'parse', crash]); print('  cargo fuzz fmt:'); pr(o2.split('Output of')[-1] if 'Output of' in o2 else o2, 4)
R['replay'] = dict(rc=rc, lines=[l[:200] for l in L if 'panicked at' in l or 'index out of bounds' in l or 'Executed' in l])
print()
print('== 四:语料库:fuzzer 保存的「各自带来新覆盖」的输入,按字节数排序')
corp = sorted((base / 'fuzz' / 'corpus' / 'parse').iterdir(), key=lambda p: (p.stat().st_size, p.name)); print(f'  语料文件 {len(corp)} 个')
rows = [(p.stat().st_size, p.read_bytes()) for p in corp]
for sz, b in rows[:20]: print(f'    {sz:>3} 字节  {b!r}')
R['corpus'] = [[sz, repr(b)] for sz, b in rows]
print()
print('== 五:最小化 cargo fuzz tmin:对找到的崩溃输入裁剪')
pad = RS / 'u165_pad.bin'; pad.write_bytes(b'FUZZ!?'); 
(base / 'fuzz' / 'artifacts' / 'parse').mkdir(parents=True, exist_ok=True)
rc, o = fz(['tmin', 'parse', crash]); print('  cargo fuzz tmin 退出码', rc); tl_ = [l for l in o.split('\n') if l.startswith(('CRASH_MIN: minimizing', 'CRASH_MIN: failed', 'INFO: Done Minimize'))] ; tl_ = [re.sub(r'crash-[0-9a-f]+', 'crash-…', l) for l in tl_]; pr('\n'.join(tl_), 8, w=200); R['tmin'] = tl_

print()
print('== 六:随机测试对照:同一个 parse,随机字节(长度 0..=8)喂 2 亿次,命中 bug 多少次?')
rcode = '''
    use std::hint::black_box;
    use std::time::Instant;
    fn parse(data: &[u8]) -> Option<u32> {
        if data.len() < 4 || &data[..4] != b"FUZZ" { return None; }
        if data.len() > 4 && data[4] == b'!' {
            if data.len() > 5 && data[5] == b'?' { return if data.len() == 6 { Some(u32::MAX) } else { Some(data[6] as u32) }; }
        }
        Some(0)
    }
    fn main() {
        let mut s = 0x9E3779B97F4A7C15u64; let mut hits = 0u64; let mut prefix4 = 0u64; let t = Instant::now();
        for _ in 0..200_000_000u64 {
            let mut buf = [0u8; 8];
            for b in buf.iter_mut() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; *b = s as u8; }
            s ^= s << 13; s ^= s >> 7; s ^= s << 17; let len = (s % 9) as usize;
            let r = parse(black_box(&buf[..len]));
            if r.is_some() { prefix4 += 1; }
            if r == Some(u32::MAX) { hits += 1; }
        }
        println!("200000000 次随机输入:通过前 4 字节 FUZZ 的 {} 次,命中 bug 的 {} 次,耗时 {:.1} 秒", prefix4, hits, t.elapsed().as_secs_f64());
    }
'''
ok, diag, binp, _ = rustc('u165_rand', rcode, release=True); assert ok, diag
rc, o, e, t = run(binp, timeout=300); print('  ' + o.strip()); R['rand'] = o.strip()
print()
print('== 七:修复(data.get(6))后再 fuzz 30 秒:不再崩溃,但这不是「没有 bug」的证明')
t0 = time.perf_counter(); rc, o = fz(['run', 'parse_fixed', '--', '-max_total_time=30', '-seed=1']); dt = time.perf_counter() - t0
L = o.split('\n'); print(f'  退出码 {rc}'); 
for l in L:
    if l.startswith(('Done', 'stat::number_of_executed_units', 'stat::average_exec_per_sec', 'stat::peak_rss_mb')): print('    ' + l)
fnews = [re.sub(r'\s+', ' ', l) for l in L if re.match(r'#\d+\s+(NEW|INITED)', l)]; print(f'  覆盖率增长事件 {len(fnews)} 次;最后一次:{fnews[-1][:130]}')
R['fixed'] = dict(rc=rc, done=[l for l in L if l.startswith(('Done', 'stat::'))], last=fnews[-1])
print()
print('== 八:unsafe 的 bug:payload 用 get_unchecked(1 + n),n 由输入的第一个字节决定。默认带 AddressSanitizer;对比 --sanitizer none')
ucode = LIB.split('pub fn payload')[1]; print('  被测函数:'); print('\n'.join('    ' + l for l in ('pub fn payload' + ucode).strip('\n').split('\n')))
def show_payload(label, args, n=14):
    rc, o = fz(['run', *args, 'payload', '--', '-max_total_time=30', '-seed=1']); L = o.split('\n')
    keep = [l for l in L if 'ERROR' in l or 'READ of size' in l or 'is located' in l or 'panicked at' in l or 'unsafe precondition' in l or l.startswith(('SUMMARY', 'Done', '0x')) or re.match(r'\s+#\d+ .*(payload|rust_fuzzer_test_input)', l)]
    keep = [re.sub(r' \(\S+:arm64\+0x[0-9a-f]+\)', '', re.sub(r'0x[0-9a-f]{9,} in ', '', l))[:190] for l in keep]
    print(f'  {label}:退出码 {rc}'); print('\n'.join('    ' + l for l in keep[:n])); return dict(rc=rc, lines=keep[:n])
R['dbg'] = show_payload('默认(带 debug assertions 的 release 构建)', [])
R['asan'] = show_payload('cargo fuzz run -O(关掉 debug assertions,仍带 ASan)', ['-O'])
R['nosan'] = show_payload('cargo fuzz run -O --sanitizer none', ['-O', '--sanitizer', 'none'])
print()
print('== 九:速度:parse_fixed 在有 ASan 与 --sanitizer none 下 20 秒内的执行次数(同样 -seed=1)')
R['speed'] = {}
for label, a in (('ASan(默认)', []), ('--sanitizer none', ['--sanitizer', 'none'])):
    rc, o = fz(['run', *a, 'parse_fixed', '--', '-max_total_time=20', '-seed=1', '-print_final_stats=1']); d = {m.group(1): int(m.group(2)) for m in (re.match(r'(stat::\w+):\s+(\d+)', l) for l in o.split('\n')) if m and m.group(1) in ('stat::number_of_executed_units', 'stat::average_exec_per_sec')}
    R['speed'][label] = d; print(f'  {label:<18} 执行 {d.get("stat::number_of_executed_units", 0):>12,} 次,平均 {d.get("stat::average_exec_per_sec", 0):>9,} 次/秒')
save('u165', R)

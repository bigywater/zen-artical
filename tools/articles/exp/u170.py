import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
import yaml, hashlib, itertools, statistics
tee('u170'); R = {}
WF = '''name: ci
on:
  push:
    branches: [main]
  pull_request:
env:
  CARGO_TERM_COLOR: always
jobs:
  fmt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo fmt --all -- --check
  clippy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo clippy --locked --all-targets -- -D warnings
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        toolchain: [stable, beta]
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@master
        with:
          toolchain: ${{ matrix.toolchain }}
      - uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            target
          key: ${{ runner.os }}-${{ matrix.toolchain }}-${{ hashFiles('**/Cargo.lock') }}
      - run: cargo build --locked
      - run: cargo test --locked
  audit:
    runs-on: ubuntu-latest
    needs: [fmt, clippy, test]
    steps:
      - uses: actions/checkout@v4
      - run: cargo install cargo-audit --locked
      - run: cargo audit
'''
base = RS / 'proj' / 'u170'; wfp = base / '.github' / 'workflows' / 'ci.yml'
LIB_OK = '''pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

pub fn render(n: u32) -> String {
    let mut buf = itoa::Buffer::new();
    buf.format(n).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn adds() {
        assert_eq!(add(2, 2), 4);
    }

    #[test]
    fn renders() {
        assert_eq!(render(42), "42");
    }
}
'''
TOML = '[package]\nname = "ci_demo"\nversion = "0.1.0"\nedition = "2024"\n\n[dependencies]\nitoa = "1"\nserde_json = "1"\nregex = "1"\n'
def setup(lib=LIB_OK, toml=TOML, lock=True):
    shutil.rmtree(base, ignore_errors=True); (base / 'src').mkdir(parents=True); wfp.parent.mkdir(parents=True)
    (base / 'Cargo.toml').write_text(toml); (base / 'src' / 'lib.rs').write_text(lib); wfp.write_text(WF)
    if lock: sh(['cargo', 'generate-lockfile'], cwd=base, env=ENV)
ENV = dict(ENVB, CARGO_TARGET_DIR=str(RS / 'target_u170'), PATH=os.environ['PATH'] + os.pathsep + str(RS / 'rustup_cargo' / 'bin'), CARGO_HOME=str(RS / 'cargo_home'))
ENV['CARGO_HOME'] = str(RS / 'cargo_home')
# cargo-audit 的漏洞库放在 rustup_cargo 的 CARGO_HOME 下;这里用同一份(给 audit 命令单独指定 CARGO_HOME)
AUDIT_ENV = dict(ENV, CARGO_HOME=str(RS / 'rustup_cargo'), RUSTUP_HOME=str(RS / 'rustup_home'), PATH=str(RS / 'rustup_cargo' / 'bin') + os.pathsep + os.environ['PATH'])
def runstep(cmd, env=None, timeout=600):
    t0 = time.perf_counter(); r = subprocess.run(cmd, shell=True, cwd=base, env=env or ENV, capture_output=True, text=True, timeout=timeout); return r.returncode, re.sub(r'\x1b\[[0-9;]*m|\x1b\(B', '', clean(r.stdout + r.stderr)), time.perf_counter() - t0
def pr(txt, n=20, ind='    ', w=200):
    L = txt.split('\n'); print('\n'.join(ind + l[:w] for l in L[:n]))
    if len(L) > n: print(f'{ind}…(共 {len(L)} 行)')
def job_steps(wf, job): return [s['run'] for s in wf['jobs'][job]['steps'] if 'run' in s]
def run_job(job, wf=None):
    """依次执行某个 job 的 run 步骤(跳过 uses: 与 cargo install:本机已有这些工具);遇到失败即停止,返回(状态, 失败步骤, 退出码, 耗时)。"""
    wf = wf or yaml.safe_load(wfp.read_text()); tot = 0
    for c in job_steps(wf, job):
        if c.startswith('cargo install'): continue
        rc, o, t = runstep(c, AUDIT_ENV if c.startswith('cargo audit') else None); tot += t
        if rc != 0: return ('失败', c, rc, tot, o)
    return ('通过', None, 0, tot, '')
print('== 一:工作流文件 .github/workflows/ci.yml(四个 job:fmt、clippy、test(矩阵)、audit)')
setup(); print('\n'.join('    ' + l for l in numbered(WF).split('\n'))); R['wf_lines'] = len(WF.strip().split('\n'))
print()
print('== 二:用 actionlint 检查工作流语法(只是静态检查,不是运行);再故意写错三处看它怎么报')
AL = str(RS / 'gopath' / 'bin' / 'actionlint')
def lint(text, tag):
    f = RS / f'u170_{tag}.yml'; f.write_text(text); r = subprocess.run([AL, '-no-color', str(f)], capture_output=True, text=True); return r.returncode, clean(r.stdout + r.stderr).replace(str(f), f'{tag}.yml')
rc, o = lint(WF, 'ci'); print(f'  actionlint ci.yml:退出码 {rc};输出:{o.strip() or "(无)"}'); R['lint_ok'] = [rc, o.strip()]
bad = {'needs 写错 job 名': WF.replace('needs: [fmt, clippy, test]', 'needs: [fmt, clippy, tset]'), 'matrix 属性写错': WF.replace('${{ matrix.toolchain }}-${{', '${{ matrix.toolchian }}-${{'), '缺少 runs-on': WF.replace('  fmt:\n    runs-on: ubuntu-latest\n', '  fmt:\n')}
R['lint_bad'] = {}
for k, t in bad.items():
    rc, o = lint(t, 'bad'); L = [l for l in o.strip().split('\n') if l.strip()]; print(f'  {k}:退出码 {rc}'); print('\n'.join('    ' + l[:200] for l in L[:4])); R['lint_bad'][k] = [rc, L[:4]]
print()
print('== 三:解析 YAML:各 job 与矩阵展开(这是我用 PyYAML 与笛卡尔积算出来的,不是 GitHub 的实际调度结果)')
wf = yaml.safe_load(WF); trig = wf.get(True) or wf.get('on')
print('  触发条件:', trig); mx = wf['jobs']['test']['strategy']['matrix']; combos = list(itertools.product(mx['os'], mx['toolchain']))
print(f'  test 矩阵:os × toolchain = {len(mx["os"])} × {len(mx["toolchain"])} = {len(combos)} 个 job:', ', '.join(f'{a}/{b}' for a, b in combos))
total = 3 + len(combos); print(f'  整个工作流一次触发的 job 数:fmt 1 + clippy 1 + test {len(combos)} + audit 1 = {total - 3 + 3};audit 声明 needs = {wf["jobs"]["audit"]["needs"]}(要等前面的 job 成功);test 里 fail-fast = {wf["jobs"]["test"]["strategy"]["fail-fast"]}')
print('  每个 job 的 run 步骤:'); 
for j in wf['jobs']: print(f'    {j}: {job_steps(wf, j)}')
R['yaml'] = dict(trig=str(trig), combos=len(combos), jobs={j: job_steps(wf, j) for j in wf['jobs']}, total=1 + 1 + len(combos) + 1)
print()
print('== 四:在本机按工作流里的 run 步骤依次执行一遍(跳过 uses: 步骤与 cargo install;test 只执行一个矩阵项,即本机的 macOS + stable)')
setup(); R['green'] = {}
print(f'  {"job":<8} {"结果":<6} {"耗时(秒)":>9}  执行的命令')
for j in ('fmt', 'clippy', 'test', 'audit'):
    st, cmd, rc, t, o = run_job(j); R['green'][j] = [st, round(t, 1)]; print(f'  {j:<8} {st:<6} {t:>9.1f}  {"; ".join(c for c in job_steps(wf, j) if not c.startswith("cargo install"))}')
rc, o, t = runstep('cargo test --locked 2>&1 | grep -E "^test |test result"'); print('  cargo test 的结果行:'); pr(o, 6); R['test_lines'] = o.strip().split('\n')
print()
print('== 五:门禁:每次注入一个缺陷,看哪个 job 会变红(其它 job 不受影响,与 Actions 里 job 互相独立一致)')
LIB_FMT = LIB_OK.replace('pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}', 'pub fn  add(a:i32,b:i32)->i32{a+b}')
LIB_CLIPPY = LIB_OK.replace('pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}', 'pub fn add(a: i32, b: i32) -> i32 {\n    return a + b;\n}')
LIB_TEST = LIB_OK.replace('assert_eq!(add(2, 2), 4);', 'assert_eq!(add(2, 2), 5);')
defects = [('代码没格式化', dict(lib=LIB_FMT)), ('clippy 警告(needless_return)', dict(lib=LIB_CLIPPY)), ('测试断言错误', dict(lib=LIB_TEST)), ('依赖有已知漏洞(固定 smallvec 1.6.0)', dict(toml=TOML + 'smallvec = "=1.6.0"\n'))]
R['gate'] = {}
print(f'  {"缺陷":<34} ' + ' '.join(f'{j:<9}' for j in ('fmt', 'clippy', 'test', 'audit')))
for name, kw in defects:
    setup(**kw); row = {}
    for j in ('fmt', 'clippy', 'test', 'audit'):
        st, cmd, rc, t, o = run_job(j); row[j] = [st, cmd, rc, o.strip().split('\n')[:3]]
    R['gate'][name] = row; print(f'  {name:<34} ' + ' '.join(f'{row[j][0]:<9}' for j in ('fmt', 'clippy', 'test', 'audit')))
print('  各缺陷下失败 job 的第一条错误信息:')
for name, row in R['gate'].items():
    for j, v in row.items():
        if v[0] == '失败': print(f'    [{name}] {j}:退出码 {v[2]};{v[1]}'); print('\n'.join('        ' + l[:160] for l in v[3] if l.strip()))
print()
print('== 六:--locked:Cargo.toml 改了(新增依赖)但没更新 Cargo.lock 时,CI 里的 cargo build --locked 会失败')
setup(); (base / 'Cargo.toml').write_text(TOML + 'tinyvec = "1"\n'); lock0 = (base / 'Cargo.lock').read_text()
rc, o, t = runstep('cargo build --locked'); print(f'  cargo build --locked:退出码 {rc}'); pr(o, 6); R['locked'] = [rc, o.strip().split('\n')[:6]]
rc, o, t = runstep('cargo build'); lock1 = (base / 'Cargo.lock').read_text(); added = sorted(set(re.findall(r'name = "([^"]+)"', lock1)) - set(re.findall(r'name = "([^"]+)"', lock0)))
print(f'  不加 --locked 的 cargo build:退出码 {rc};Cargo.lock 被悄悄改写,新增的包:{added}'); R['unlocked'] = [rc, added]
print()
print('== 七:缓存的本地对照:冷缓存(空的 target 目录)与恢复缓存后(把上一次的 target 目录复制回来)执行 cargo test --locked;缓存键用 Cargo.lock 的 sha256 近似')
setup(); key = lambda: hashlib.sha256((base / 'Cargo.lock').read_bytes()).hexdigest()[:12]; k1 = key()
cold, warm_same, warm_edit = [], [], []
for _ in range(3):
    shutil.rmtree(RS / 'target_u170', ignore_errors=True); rc, o, t = runstep('cargo test --locked'); cold.append(t)
    saved = RS / 'target_u170_saved'; shutil.rmtree(saved, ignore_errors=True); shutil.copytree(RS / 'target_u170', saved, symlinks=True)
    shutil.rmtree(RS / 'target_u170'); shutil.copytree(saved, RS / 'target_u170', symlinks=True); rc, o, t = runstep('cargo test --locked'); warm_same.append(t)
    (base / 'src' / 'lib.rs').write_text(LIB_OK + f'\n// edit {_}\n'); rc, o, t = runstep('cargo test --locked'); warm_edit.append(t); (base / 'src' / 'lib.rs').write_text(LIB_OK)
k2 = key(); (base / 'Cargo.toml').write_text(TOML + 'smallvec = "1"\n'); sh(['cargo', 'generate-lockfile'], cwd=base, env=ENV); k3 = key()
print(f'  冷缓存:{", ".join(f"{x:.1f}" for x in cold)} 秒(中位数 {statistics.median(cold):.1f});恢复缓存后没改动:{", ".join(f"{x:.2f}" for x in warm_same)} 秒;恢复缓存后改了 lib.rs:{", ".join(f"{x:.2f}" for x in warm_edit)} 秒')
print(f'  缓存键(Cargo.lock 的 sha256 前 12 位):初始 {k1};改源码后 {k2}(不变);新增依赖并重新生成锁文件后 {k3}(变化,缓存失效)')
R['cache'] = dict(cold=statistics.median(cold), same=statistics.median(warm_same), edit=statistics.median(warm_edit), keys=[k1, k2, k3])
save('u170', R)

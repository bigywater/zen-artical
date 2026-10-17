import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u156'); R = {}
def mk(base, files):
    for p, c in files.items(): f = base / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(textwrap.dedent(c).lstrip('\n'))
base = RS / 'proj' / 'u156'; shutil.rmtree(base, ignore_errors=True)
mk(base, {
 'vec2-sys/Cargo.toml': '''
   [package]
   name = "vec2-sys"
   version = "0.1.0"
   edition = "2024"
   links = "vec2"
   build = "build.rs"
   [build-dependencies]
   cc = "1"
 ''',
 'vec2-sys/vendor/vec2.c': '''
   #include <stddef.h>
   #ifndef VEC2_SCALE
   #define VEC2_SCALE 1
   #endif
   typedef struct { double x, y; } Vec2;
   double vec2_dot(const Vec2 *a, const Vec2 *b) { return (a->x * b->x + a->y * b->y) * VEC2_SCALE; }
   #define STR2(x) #x
   #define STR(x) STR2(x)
   const char *vec2_build_info(void) { return "vec2 compiled by cc crate, scale=" STR(VEC2_SCALE); }
 ''',
 'vec2-sys/build.rs': '''
   use std::{env, fs, path::Path};
   fn main() {
       println!("cargo:rerun-if-changed=vendor/vec2.c");
       println!("cargo:rerun-if-env-changed=VEC2_SCALE");
       let scale = env::var("VEC2_SCALE").unwrap_or_else(|_| "1".into());
       let log = Path::new(&env::var("CARGO_MANIFEST_DIR").unwrap()).join("../build_runs.log");
       let mut s = fs::read_to_string(&log).unwrap_or_default(); s.push_str(&format!("scale={}\\n", scale)); fs::write(&log, s).unwrap();
       cc::Build::new().file("vendor/vec2.c").define("VEC2_SCALE", scale.as_str()).opt_level(2).compile("vec2");
       println!("cargo:include={}", Path::new(&env::var("CARGO_MANIFEST_DIR").unwrap()).join("vendor").display());
       println!("cargo:scale={}", scale);
   }
 ''',
 'vec2-sys/src/lib.rs': '''
   #[repr(C)] #[derive(Clone, Copy)] pub struct Vec2 { pub x: f64, pub y: f64 }
   unsafe extern "C" { pub fn vec2_dot(a: *const Vec2, b: *const Vec2) -> f64; pub fn vec2_build_info() -> *const std::ffi::c_char; }
 ''',
 'app/Cargo.toml': '''
   [package]
   name = "app"
   version = "0.1.0"
   edition = "2024"
   build = "build.rs"
   [dependencies]
   vec2-sys = { path = "../vec2-sys" }
 ''',
 'app/build.rs': '''
   fn main() { println!("cargo:warning=app 的 build.rs 收到 DEP_VEC2_INCLUDE={}  DEP_VEC2_SCALE={}", std::env::var("DEP_VEC2_INCLUDE").unwrap(), std::env::var("DEP_VEC2_SCALE").unwrap()); }
 ''',
 'app/src/main.rs': '''
   use vec2_sys::*;
   fn main() { let (a, b) = (Vec2 { x: 1.0, y: 2.0 }, Vec2 { x: 3.0, y: 4.0 }); println!("vec2_dot = {}", unsafe { vec2_dot(&a, &b) }); println!("{}", unsafe { std::ffi::CStr::from_ptr(vec2_build_info()) }.to_str().unwrap()); }
 ''',
})
app = base / 'app'
print('== 一:build.rs 用 cc crate 把 C 源码编译成静态库并自动链接(cc 会输出 cargo:rustc-link-lib / link-search);Rust 直接调用 C 函数')
rc, o = cargo(['run', '--quiet'], app, timeout=900); print('  ' + o.strip().replace('\n', '\n  ')); R['run1'] = o.strip()
rc, o = cargo(['build', '-vv'], app, timeout=300) ; 
out_dir = sorted((TG / 'debug' / 'build').glob('vec2-sys-*/output'))
if out_dir:
    txt = out_dir[0].read_text(); allL = txt.splitlines(); nrerun = sum('rerun-if-env-changed' in l for l in allL); L = [l for l in allL if l.startswith('cargo:rustc-link') or l.startswith('cargo:include') or l.startswith('cargo:scale') or 'rerun-if-changed' in l]; print(f'  build.rs 的输出共 {len(allL)} 行,其中 cc 自动加的 rerun-if-env-changed 有 {nrerun} 行(CC、CFLAGS、AR 等);其余关键指令:'); print('\n'.join('    ' + l.replace(str(RS), '<实验目录>') for l in L)); R['directives'] = [l.replace(str(RS), '<实验目录>') for l in L]; R['nlines'] = [len(allL), nrerun]
sizes = sorted((TG / 'debug' / 'build').glob('vec2-sys-*/out/libvec2.a')); print(f'  生成的静态库:{[ (p.name, p.stat().st_size) for p in sizes]}'); R['lib'] = [(p.name, p.stat().st_size) for p in sizes]
print()
print('== 二:links 键与 DEP_*:上游 -sys crate 通过 cargo:KEY=VALUE 把元数据传给下游的 build.rs(变量名 DEP_<links>_<KEY>)')
rc, o = cargo(['build', '--quiet'], app, timeout=300); rc, o = cargo(['clean', '-p', 'app'], app); rc, o = cargo(['build'], app, timeout=300); L = [l.strip().replace(str(RS), '<实验目录>') for l in o.splitlines() if 'warning: app@' in l]; print('  下游 app 的 build.rs 打印(DEP_VEC2_*):'); print('\n'.join('    ' + l for l in L)); R['dep'] = L
print()
print('== 三:rerun-if-env-changed:改环境变量 VEC2_SCALE 才重新运行 build.rs(日志统计);只改无关环境变量不会')
log = base / 'build_runs.log'
def runs(): return len(log.read_text().splitlines()) if log.exists() else 0
n0 = runs(); rc, o = cargo(['build', '--quiet'], app, timeout=300); n1 = runs()
env = dict(ENVB); rc, o, e = sh(['cargo', 'build', '--quiet'], cwd=app, env=dict(env, UNRELATED='x'), timeout=300); n2 = runs()
rc, o, e = sh(['cargo', 'run', '--quiet'], cwd=app, env=dict(env, VEC2_SCALE='10'), timeout=300); n3 = runs(); out10 = o.strip()
rc, o, e = sh(['cargo', 'run', '--quiet'], cwd=app, env=dict(env, VEC2_SCALE='10'), timeout=300); n4 = runs()
print(f'  build.rs 累计运行次数:起始 {n0};没改动再 build {n1};设置无关变量 UNRELATED {n2};VEC2_SCALE=10 后 {n3};再次相同环境 {n4}'); print('  VEC2_SCALE=10 时的程序输出:', out10.replace('\n', ' | ')); R['envruns'] = [n0, n1, n2, n3, n4]; R['out10'] = out10
print()
print('== 四:build-dependencies 与普通依赖是分开编译的:cc 只在 vec2-sys 的 build 依赖里,最终程序的运行时依赖里没有它')
rc, o = cargo(['tree', '-e', 'normal'], app, timeout=300); print('  cargo tree -e normal(运行时依赖):', [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip() and 'Updating' not in l][:5]); R['tree_normal'] = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip() and 'Updating' not in l][:5]
rc, o = cargo(['tree', '-e', 'normal,build'], app, timeout=300); print('  cargo tree -e normal,build(运行时 + 构建期依赖):', [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip() and 'Updating' not in l][:6]); R['tree_build'] = [l.replace(str(RS), '<实验目录>') for l in o.splitlines() if l.strip() and 'Updating' not in l][:6]
save('u156', R)

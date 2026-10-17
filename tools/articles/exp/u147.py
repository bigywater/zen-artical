import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u147'); R = {}
print('== 一:读取环境变量:env::var 返回 Result;不存在 NotPresent;存在但不是合法 UTF-8 NotUnicode;var_os 返回 OsString 不失败')
ok, d, b, _ = rustc('u147a', '''
    use std::{env, ffi::OsString};
    fn main() {
        for k in ["U147_SET", "U147_MISSING", "U147_BAD", "U147_EMPTY"] { println!("  {:<13} var = {:?}   var_os = {:?}", k, env::var(k).map_err(|e| e.to_string()), env::var_os(k)); }
        println!("  U147_EMPTY 是空字符串不是不存在:{:?}", env::var("U147_EMPTY").map(|s| s.is_empty()));
        println!("  var_os 比 var 能装下非 UTF-8 的值:{:?}", env::var_os("U147_BAD").map(|v| { use std::os::unix::ffi::OsStrExt; v.as_bytes().to_vec() }));
    }
''', release=True); assert ok, d
env = dict(os.environ, U147_SET='hello', U147_EMPTY=''); env.pop('U147_MISSING', None)
p = subprocess.run([str(b)], env=env, capture_output=True); 
# non-UTF8 value via bytes
envb = {k.encode(): v.encode() for k, v in env.items()}; envb[b'U147_BAD'] = b'bad\xff\xfe'
p = subprocess.run([str(b)], env=envb, capture_output=True, text=True); print(p.stdout.rstrip()); R['read'] = p.stdout.rstrip()
print()
print('== 二:修改自己的环境:set_var / remove_var 只影响当前进程(与之后启动的子进程),不影响父 shell;edition 2024 里是 unsafe')
r = tryit('u147b', '''
    use std::{env, process::Command};
    fn main() {
        unsafe { env::set_var("U147_X", "from-rust"); }
        let o = Command::new("sh").arg("-c").arg("echo child sees U147_X=$U147_X").output().unwrap(); println!("set_var 之后子进程看到:{}", String::from_utf8_lossy(&o.stdout).trim());
        unsafe { env::remove_var("U147_X"); }
        let o = Command::new("sh").arg("-c").arg("echo child sees U147_X=[$U147_X]").output().unwrap(); println!("remove_var 之后子进程看到:{}", String::from_utf8_lossy(&o.stdout).trim());
    }
''', quiet_src=False); R['set'] = r['out']
r = tryit('u147c', '''
    fn main() { std::env::set_var("A", "1"); }
''', maxlines=24); R['e0133'] = r['diag']
print()
print('== 三:同一个环境变量在子进程里修改,父进程看不到(进程环境是各自一份拷贝)')
r = tryit('u147d', '''
    use std::process::Command;
    fn main() {
        unsafe { std::env::set_var("U147_SHARED", "parent"); }
        let o = Command::new("sh").arg("-c").arg("export U147_SHARED=child; echo child: $U147_SHARED").output().unwrap(); println!("{}", String::from_utf8_lossy(&o.stdout).trim());
        println!("子进程改完之后,父进程仍然是 {:?}", std::env::var("U147_SHARED"));
    }
''', quiet_src=True); R['copy'] = r['out']
print()
print('== 四:遍历所有环境变量:环境里有非 UTF-8 的变量时 vars() 会 panic,vars_os() 不会')
ok, d, b, _ = rustc('u147e', '''
    use std::env;
    fn main() { let mode = env::args().nth(1).unwrap(); match mode.as_str() { "vars" => { println!("vars() 共 {} 个", env::vars().count()); } _ => { println!("vars_os() 共 {} 个", env::vars_os().count()); } } }
''', release=True); assert ok, d
for mode in ('vars', 'vars_os'):
    p = subprocess.run([str(b), mode], env=envb, capture_output=True, text=True); L = [l for l in p.stderr.splitlines() if l.strip() and 'note:' not in l][:2]
    print(f'  环境里放一个非 UTF-8 的变量:{mode} → 退出码 {p.returncode},stdout {p.stdout.strip()!r},stderr {L}'); R.setdefault('iter', {})[mode] = [p.returncode, p.stdout.strip(), L]
print()
print('== 五:编译期环境变量:option_env! 在编译时读取(缺失得到 None),与运行期 env::var 的区别;env! 缺失则编译失败')
def run_with(compile_env, run_env):
    f = src_file('u147g', '''
        fn main() { println!("编译期 option_env! = {:?};运行期 env::var = {:?}", option_env!("U147_COMPILE"), std::env::var("U147_COMPILE").ok()); }
    '''); out = RS / 'bin' / 'u147g'; rc, o, e = sh(['rustc', '--edition=2024', '-o', str(out), str(f)], env=dict(ENVB, **compile_env)); p = subprocess.run([str(out)], env=dict(os.environ, **run_env), capture_output=True, text=True); return p.stdout.strip()
for label, ce, re_ in [('编译时设置 A,运行时设置 B', {'U147_COMPILE': 'A-at-compile'}, {'U147_COMPILE': 'B-at-run'}), ('编译时没设置,运行时设置 B', {}, {'U147_COMPILE': 'B-at-run'})]:
    out = run_with(ce, re_); print(f'  {label}:{out}'); R.setdefault('compile', {})[label] = out
rc, o, e = sh(['rustc', '--edition=2024', '--emit=metadata', '-o', str(RS / 'bin' / 'u147h.rmeta'), str(src_file('u147h', 'fn main() { let _ = env!("U147_REQUIRED"); }'))]); L = [l for l in (o + e).splitlines() if l.startswith('error')][:1]
print(f'  env!("U147_REQUIRED") 编译期缺失:{L}'); R['env_missing'] = L
save('u147', R)

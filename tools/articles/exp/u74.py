import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u74'); R = {}
print('== 一:thiserror:用 derive 代替手写 Display / Error / From(thiserror 2.0.21,真实下载编译)')
files = {'src/main.rs': '''
    use thiserror::Error;
    use std::error::Error as _;
    #[derive(Debug, Error)]
    pub enum StoreError {
        #[error("键 {0} 不存在")]
        NotFound(String),
        #[error("读取 {path} 失败")]
        Io { path: String, #[source] source: std::io::Error },
        #[error("无效数字")]
        Parse(#[from] std::num::ParseIntError),
    }
    fn get(k: &str) -> Result<i32, StoreError> {
        if k == "missing" { return Err(StoreError::NotFound(k.to_string())); }
        if k == "io" { return Err(StoreError::Io { path: "/不存在".into(), source: std::io::Error::from(std::io::ErrorKind::NotFound) }); }
        Ok(k.parse::<i32>()?)
    }
    fn main() {
        for k in ["12", "missing", "io", "abc"] {
            match get(k) {
                Ok(v) => println!("{:<8} -> Ok({})", k, v),
                Err(e) => println!("{:<8} -> Display: {}   source: {:?}   Debug: {:?}", k, e, e.source().map(|s| s.to_string()), e),
            }
        }
        println!("size_of::<StoreError>() = {}", std::mem::size_of::<StoreError>());
    }
'''}
d = proj('u74a', files, deps='thiserror = "2"')
rc, o = cargo(['run', '--quiet'], d, timeout=600); print('  运行结果(退出码 %d):' % rc); print('\n'.join('    ' + l for l in o.splitlines())); R['thiserror'] = o
print()
print('== 二:thiserror 到底生成了什么(cargo rustc -- -Z unpretty=expanded,取 Display / Error / From 部分)')
env = dict(ENVB, RUSTC_BOOTSTRAP='1')
rc, o2 = cargo(['rustc', '--quiet', '--', '-Z', 'unpretty=expanded'], d, env=env, timeout=600)
lines = o2.splitlines()
keep = []; on = False
for l in lines:
    if re.match(r'\s*(#\[automatically_derived\]\s*)?impl.*(Display|Error|From)\b.*for StoreError', l) or re.match(r'\s*impl.*for StoreError', l): on = True
    if on: keep.append(l)
    if on and l.strip() == '}' and not l.startswith(' '): on = False
txt = '\n'.join(keep) if keep else o2[:3000]
print('  展开后与 StoreError 相关的 impl(共 %d 行,下面显示前 70 行):' % len(keep)); print('\n'.join('    ' + l for l in txt.splitlines()[:70])); R['expanded'] = txt.splitlines()[:70]; R['expanded_n'] = len(keep)
print()
print('== 三:anyhow:不关心具体类型的应用层错误,用 context 叠加说明')
files = {'src/main.rs': '''
    use anyhow::{anyhow, bail, Context, Result};
    fn read_port(s: &str) -> Result<u16> {
        if s.is_empty() { bail!("端口为空"); }
        let n: u16 = s.parse().with_context(|| format!("解析端口 {:?} 失败", s))?;
        if n < 1024 { return Err(anyhow!("端口 {} 是保留端口", n)); }
        Ok(n)
    }
    fn start(s: &str) -> Result<()> { let p = read_port(s).context("启动服务失败")?; println!("监听 {}", p); Ok(()) }
    fn main() {
        for s in ["8080", "", "80", "abc"] {
            match start(s) {
                Ok(()) => {}
                Err(e) => { println!("--- 输入 {:?}", s); println!("{{}}   : {}", e); println!("{{:#}}  : {:#}", e); println!("{{:?}}  :\\n{:?}", e); println!("原因链: {:?}", e.chain().map(|c| c.to_string()).collect::<Vec<_>>()); }
            }
        }
        println!("size_of::<anyhow::Error>() = {}  size_of::<Result<(), anyhow::Error>>() = {}", std::mem::size_of::<anyhow::Error>(), std::mem::size_of::<Result<(), anyhow::Error>>());
        let e = read_port("abc").unwrap_err();
        println!("downcast_ref::<ParseIntError>: {:?}", e.downcast_ref::<std::num::ParseIntError>().map(|p| p.to_string()));
    }
'''}
d = proj('u74b', files, deps='anyhow = "1"')
rc, o = cargo(['run', '--quiet'], d, timeout=600); print('  运行结果(退出码 %d):' % rc); print('\n'.join('    ' + l for l in o.splitlines())); R['anyhow'] = o
print()
print('== 四:边界:库里返回 anyhow::Error,调用方无法 match 具体变体;thiserror 的枚举可以')
files = {'src/main.rs': '''
    use thiserror::Error;
    #[derive(Debug, Error)] enum LibErr { #[error("没有权限")] Denied, #[error("超时 {0} 秒")] Timeout(u32) }
    fn lib_typed(n: u32) -> Result<(), LibErr> { if n == 0 { Err(LibErr::Denied) } else { Err(LibErr::Timeout(n)) } }
    fn lib_anyhow(n: u32) -> anyhow::Result<()> { lib_typed(n)?; Ok(()) }
    fn main() {
        match lib_typed(5) { Err(LibErr::Timeout(s)) => println!("typed:调用方 match 到 Timeout,可以按 {} 秒重试", s), Err(LibErr::Denied) => println!("typed:无权限"), Ok(()) => {} }
        let e = lib_anyhow(5).unwrap_err();
        println!("anyhow:调用方拿到的是 {}", e);
        match e.downcast_ref::<LibErr>() { Some(LibErr::Timeout(s)) => println!("只能 downcast_ref 才能还原:Timeout({})", s), _ => println!("无法还原") }
    }
'''}
d = proj('u74c', files, deps='thiserror = "2"\nanyhow = "1"')
rc, o = cargo(['run', '--quiet'], d, timeout=600); print('  运行结果(退出码 %d):' % rc); print('\n'.join('    ' + l for l in o.splitlines())); R['boundary'] = o
save('u74', R)

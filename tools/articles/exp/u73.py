import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u73'); R = {}
print('== 一:一个完整的自定义错误类型:enum + Display + Error + From,以及 source() 链')
r = tryit('u73a', '''
    use std::{error::Error, fmt, num::ParseIntError, fs, io};
    #[derive(Debug)]
    enum ConfigError { Io(io::Error), Parse { key: String, source: ParseIntError }, Missing(&'static str) }
    impl fmt::Display for ConfigError {
        fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
            match self { ConfigError::Io(_) => write!(f, "读取配置文件失败"), ConfigError::Parse { key, .. } => write!(f, "配置项 {} 不是有效整数", key), ConfigError::Missing(k) => write!(f, "缺少配置项 {}", k) }
        }
    }
    impl Error for ConfigError {
        fn source(&self) -> Option<&(dyn Error + 'static)> {
            match self { ConfigError::Io(e) => Some(e), ConfigError::Parse { source, .. } => Some(source), ConfigError::Missing(_) => None }
        }
    }
    impl From<io::Error> for ConfigError { fn from(e: io::Error) -> Self { ConfigError::Io(e) } }
    fn load(path: &str, key: &'static str) -> Result<i32, ConfigError> {
        let text = fs::read_to_string(path)?;
        let line = text.lines().find(|l| l.starts_with(key)).ok_or(ConfigError::Missing(key))?;
        let v = line.split('=').nth(1).unwrap_or("").trim();
        v.parse().map_err(|e| ConfigError::Parse { key: key.to_string(), source: e })
    }
    fn report(e: &dyn Error) { println!("错误: {}", e); let mut cur = e.source(); let mut d = 1; while let Some(s) = cur { println!("{}由 {} 引起", "  ".repeat(d), s); cur = s.source(); d += 1; } }
    fn main() {
        let dir = std::env::temp_dir().join("u73cfg"); fs::create_dir_all(&dir).unwrap();
        let p = dir.join("a.conf"); fs::write(&p, "port = 8080\\nworkers = many\\n").unwrap();
        let ps = p.to_str().unwrap();
        println!("port -> {:?}", load(ps, "port"));
        for (path, key) in [(ps, "workers"), (ps, "timeout"), ("/不存在的/文件", "port")] {
            match load(path, key) { Ok(v) => println!("{} -> {}", key, v), Err(e) => { report(&e); println!("  Debug: {:?}", e); } }
        }
        let _ = fs::remove_dir_all(&dir);
    }
''', quiet_src=False); R['full'] = r['out']
print()
print('== 二:只实现 Error 而没实现 Display 会编译失败')
r = tryit('u73b', '''
    use std::error::Error;
    #[derive(Debug)] struct MyErr;
    impl Error for MyErr {}
    fn main() { let e: Box<dyn Error> = Box::new(MyErr); println!("{:?}", e); }
''', maxlines=30); R['e_display'] = r['diag']
print()
print('== 三:Box<dyn Error> 与向下转型(downcast_ref):调用方怎么还原具体类型')
r = tryit('u73c', '''
    use std::error::Error; use std::fmt;
    #[derive(Debug)] struct Quota(u32);
    impl fmt::Display for Quota { fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "超出配额 {}", self.0) } }
    impl Error for Quota {}
    fn run(k: u32) -> Result<(), Box<dyn Error>> { if k == 0 { Err(Quota(100))? } else { "x".parse::<i32>()?; } Ok(()) }
    fn main() {
        for k in [0, 1] {
            let e = run(k).unwrap_err();
            if let Some(q) = e.downcast_ref::<Quota>() { println!("k={}: 是 Quota,内部值 {}", k, q.0); }
            else if let Some(p) = e.downcast_ref::<std::num::ParseIntError>() { println!("k={}: 是 ParseIntError: {}", k, p); }
            else { println!("k={}: 未知类型", k); }
        }
        println!("size_of::<Box<dyn Error>>() = {} 字节(胖指针)", std::mem::size_of::<Box<dyn Error>>());
    }
''', quiet_src=True); R['downcast'] = r['out']
print()
print('== 四:错误枚举的大小:Result<T, E> 的大小受 E 影响(大错误拖累成功路径)')
r = tryit('u73d', '''
    use std::mem::size_of;
    #[allow(dead_code)] enum Small { A, B(u8) }
    #[allow(dead_code)] enum WithString { A(String), B }
    #[allow(dead_code)] enum Big { A([u8; 128]), B }
    fn main() {
        println!("Small {}  WithString {}  Big {}", size_of::<Small>(), size_of::<WithString>(), size_of::<Big>());
        println!("Result<u32, Small> {}  Result<u32, WithString> {}  Result<u32, Big> {}  Result<u32, Box<Big>> {}", size_of::<Result<u32, Small>>(), size_of::<Result<u32, WithString>>(), size_of::<Result<u32, Big>>(), size_of::<Result<u32, Box<Big>>>());
        println!("io::Error {}  ParseIntError {}  Box<dyn Error> {}", size_of::<std::io::Error>(), size_of::<std::num::ParseIntError>(), size_of::<Box<dyn std::error::Error>>());
    }
''', quiet_src=True); R['size'] = r['out']
save('u73', R)

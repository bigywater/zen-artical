import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rsl import *
tee('u131'); R = {}
HEAD = '''
    #![allow(unused)]
    use std::{fs::{self, File, OpenOptions}, io::{self, Read, Write}, path::PathBuf};
    fn tmp(name: &str) -> PathBuf { let d = std::env::temp_dir().join("u131"); fs::create_dir_all(&d).unwrap(); d.join(name) }
'''
print('== 一:一行读写:fs::write / fs::read / fs::read_to_string;文件内容是字节,read_to_string 要求合法 UTF-8')
r = tryit('u131a', HEAD + '''
    fn main() {
        let p = tmp("a.txt");
        fs::write(&p, "第一行\\n第二行\\n").unwrap();
        println!("fs::write 之后:大小 {} 字节", fs::metadata(&p).unwrap().len());
        println!("fs::read_to_string: {:?}", fs::read_to_string(&p).unwrap());
        println!("fs::read 得到 {} 个字节,前 6 个 {:?}(UTF-8,每个汉字 3 字节)", fs::read(&p).unwrap().len(), &fs::read(&p).unwrap()[..6]);
        fs::write(&p, [0xff, 0xfe, 0x41]).unwrap();
        println!("写入非法 UTF-8 后 read_to_string: {:?}", fs::read_to_string(&p).map_err(|e| (e.kind(), e.to_string())));
        println!("同一个文件 fs::read: {:?}", fs::read(&p).unwrap());
    }
''', quiet_src=True); R['basic'] = r['out']
print()
print('== 二:错误:io::ErrorKind 与 OS 错误码(NotFound、PermissionDenied、AlreadyExists、IsADirectory)')
r = tryit('u131b', HEAD + '''
    fn main() {
        let e = fs::read_to_string("/不存在的/文件.txt").unwrap_err(); println!("不存在:kind = {:?}  os_error = {:?}  信息 = {}", e.kind(), e.raw_os_error(), e);
        let p = tmp("ro.txt"); fs::write(&p, "x").unwrap(); let mut perm = fs::metadata(&p).unwrap().permissions(); std::os::unix::fs::PermissionsExt::set_mode(&mut perm, 0o444); fs::set_permissions(&p, perm).unwrap();
        let e = OpenOptions::new().write(true).open(&p).unwrap_err(); println!("只读文件以写方式打开:kind = {:?}  os_error = {:?}", e.kind(), e.raw_os_error());
        let e = OpenOptions::new().write(true).create_new(true).open(&p).unwrap_err(); println!("create_new 遇到已存在的文件:kind = {:?}", e.kind());
        let e = fs::read_to_string(std::env::temp_dir()).unwrap_err(); println!("把目录当文件读:kind = {:?}  os_error = {:?}", e.kind(), e.raw_os_error());
        let mut perm = fs::metadata(&p).unwrap().permissions(); std::os::unix::fs::PermissionsExt::set_mode(&mut perm, 0o644); fs::set_permissions(&p, perm).unwrap();
    }
''', quiet_src=True); R['err'] = r['out']
print()
print('== 三:OpenOptions 的语义:write 默认从头覆盖不截断;truncate 截断;append 追加;create / create_new')
r = tryit('u131c', HEAD + '''
    fn main() {
        let p = tmp("o.txt");
        fs::write(&p, "AAAAAAAA").unwrap();
        OpenOptions::new().write(true).open(&p).unwrap().write_all(b"bb").unwrap(); println!("write(true) 只覆盖前 2 字节: {:?}", fs::read_to_string(&p).unwrap());
        OpenOptions::new().write(true).truncate(true).open(&p).unwrap().write_all(b"cc").unwrap(); println!("write + truncate: {:?}", fs::read_to_string(&p).unwrap());
        OpenOptions::new().append(true).open(&p).unwrap().write_all(b"dd").unwrap(); println!("append: {:?}", fs::read_to_string(&p).unwrap());
        let _ = fs::remove_file(tmp("new.txt")); OpenOptions::new().write(true).create(true).open(tmp("new.txt")).unwrap(); println!("create(true) 创建了空文件,大小 {}", fs::metadata(tmp("new.txt")).unwrap().len());
        println!("File::create 会创建文件并截断已有内容:对已有内容的文件再 File::create →");
        File::create(&p).unwrap(); println!("  内容被清空,大小 {}", fs::metadata(&p).unwrap().len());
    }
''', quiet_src=True); R['open'] = r['out']
print()
print('== 四:原子地替换文件:写到临时文件再 rename —— 读者要么看到旧内容、要么看到新内容,看不到写了一半的')
r = tryit('u131d', HEAD + '''
    use std::{thread, sync::{Arc, atomic::{AtomicBool, Ordering::Relaxed}}, time::Duration};
    fn main() {
        let p = tmp("conf.txt"); fs::write(&p, "A".repeat(1000)).unwrap(); let stop = Arc::new(AtomicBool::new(false));
        let (p2, s2) = (p.clone(), stop.clone());
        let reader = thread::spawn(move || { let (mut seen_a, mut seen_b, mut torn) = (0, 0, 0); while !s2.load(Relaxed) { if let Ok(s) = fs::read_to_string(&p2) { if s.len() == 1000 && s.bytes().all(|b| b == b'A') { seen_a += 1; } else if s.len() == 1000 && s.bytes().all(|b| b == b'B') { seen_b += 1; } else { torn += 1; } } } (seen_a, seen_b, torn) });
        let tmpf = tmp("conf.txt.tmp");
        for i in 0..300 { let c = if i % 2 == 0 { "B" } else { "A" }; fs::write(&tmpf, c.repeat(1000)).unwrap(); fs::rename(&tmpf, &p).unwrap(); }
        stop.store(true, Relaxed); let (a, b, t) = reader.join().unwrap();
        println!("原子替换(tmp + rename)300 次期间,读者读到 完整的 A {} 次、完整的 B {} 次、撕裂的内容 {} 次", a, b, t);
        let (p3, s3) = (p.clone(), Arc::new(AtomicBool::new(false))); let s4 = s3.clone();
        let reader = thread::spawn(move || { let mut torn = 0; let mut n = 0; while !s4.load(Relaxed) { match fs::read_to_string(&p3) { Ok(s) => { n += 1; if !(s.len() == 1000 && (s.bytes().all(|b| b == b'A') || s.bytes().all(|b| b == b'B'))) { torn += 1; } } Err(_) => {} } } (n, torn) });
        for i in 0..300 { let c = if i % 2 == 0 { "B" } else { "A" }; let mut f = File::create(&p).unwrap(); f.write_all(c.repeat(1000).as_bytes()).unwrap(); }
        s3.store(true, Relaxed); let (n, t) = reader.join().unwrap();
        println!("直接 File::create 覆盖 300 次期间,读者读了 {} 次,其中读到被截断/不完整内容 {} 次", n, t);
    }
''', quiet_src=True, release=True); R['atomic'] = r['out']
print()
print('== 五:目录:create_dir_all / read_dir(顺序不保证)/ remove_dir_all / metadata 的类型与大小')
r = tryit('u131e', HEAD + '''
    fn main() {
        let root = tmp("tree"); let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("a/b/c")).unwrap(); for n in ["z.txt", "m.txt", "a.txt"] { fs::write(root.join(n), n).unwrap(); } fs::write(root.join("a/b/deep.txt"), "deep").unwrap();
        let mut names: Vec<String> = fs::read_dir(&root).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()).collect();
        let raw = names.clone(); names.sort();
        println!("read_dir 的返回顺序: {:?}(文档不保证顺序);排序后 {:?}", raw, names);
        let m = fs::metadata(root.join("a")).unwrap(); println!("metadata(a): is_dir = {}  is_file = {}", m.is_dir(), m.is_file());
        println!("remove_dir 删除非空目录: {:?}", fs::remove_dir(root.join("a")).map_err(|e| e.kind()));
        fs::remove_dir_all(&root).unwrap(); println!("remove_dir_all 之后目录还在吗: {}", root.exists());
    }
''', quiet_src=True); R['dir'] = r['out']
save('u131', R)

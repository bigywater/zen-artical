from lib import *
import re
S = SS('u131')
R = J('u131')
at = re.search(r'完整的 A (\d+) 次、完整的 B (\d+) 次、撕裂的内容 (\d+) 次', R['atomic']); di = re.search(r'读了 (\d+) 次,其中读到被截断/不完整内容 (\d+) 次', R['atomic'])
steps = [
    step("fs::write / fs::read / fs::read_to_string 是一行读写。写入 \"第一行\\n第二行\\n\" 得到 20 字节(汉字 UTF-8 每个 3 字节),fs::read 返回字节(前 6 个是两个汉字的 UTF-8 [231, 172, 172, 228, 184, 128])。写入非法 UTF-8 的 [0xff, 0xfe, 0x41] 后,read_to_string 返回 Err(InvalidData, \"stream did not contain valid UTF-8\"),而 fs::read 仍能读出这三个字节。", t=tl(S(1)), done=lidx(S(1), 'fs::write 之后', 'fs::read_to_string', 'fs::read 得到'), mark=lidx(S(1), 'InvalidData'), kv=KV([['read_to_string', '要求 UTF-8,否则 InvalidData'], ['fs::read', '任意字节']], ['read_to_string'])),
    step("错误是 io::Error,可以看 kind() 和原始 OS 错误码:不存在的文件 NotFound(os error 2);只读文件以写方式打开 PermissionDenied(13);create_new 遇到已存在的文件 AlreadyExists;把目录当文件读 IsADirectory(21)。", t=tl(S(2)), done=lidx(S(2), '不存在', '只读文件', 'create_new', '把目录'), kv=KV([['不存在', 'NotFound / os 2'], ['无权限', 'PermissionDenied / os 13'], ['目录当文件', 'IsADirectory / os 21']], ['无权限'])),
    step("OpenOptions 的语义:对 \"AAAAAAAA\" 用 write(true) 打开写 \"bb\",只覆盖前 2 字节,得到 \"bbAAAAAA\"(不会截断);加 truncate(true) 写 \"cc\" 得到 \"cc\";append(true) 写 \"dd\" 得到 \"ccdd\";create(true) 创建空文件;File::create 会把已有内容清空(大小 0)。", t=tl(S(3)), done=lidx(S(3), 'write(true)', 'write + truncate', 'append', 'create(true)', '内容被清空'), kv=KV([['write', '从头覆盖,不截断'], ['truncate', '先清空'], ['append', '追加']], ['write'])),
    step(f"原子替换配置文件:写临时文件再 fs::rename 覆盖目标。300 次替换期间,另一个线程不停读取,读到完整的 A {at.group(1)} 次、完整的 B {at.group(2)} 次、撕裂的内容 {at.group(3)} 次 —— 读者要么看到旧版本,要么看到新版本。", t=tl(S(4)), done=lidx(S(4), '原子替换'), kv=KV([['tmp + rename', f'撕裂 {at.group(3)} 次']], ['tmp + rename'])),
    step(f"对照:直接 File::create 覆盖同一个文件(先截断再写)300 次,读者读了 {di.group(1)} 次,其中 {di.group(2)} 次读到被截断或不完整的内容。写一半的状态对读者是可见的,崩溃时也会留下半个文件。需要「要么旧要么新」的场景用临时文件 + rename。", t=tl(S(4)), mark=lidx(S(4), '直接 File::create'), kv=KV([['直接覆盖', f'{di.group(2)} / {di.group(1)} 次读到不完整内容']], ['直接覆盖'])),
    step("目录操作:read_dir 的返回顺序是 [\"z.txt\", \"m.txt\", \"a\", \"a.txt\"](创建顺序也不是它;文档不保证顺序,要有序就自己排序);metadata 给出 is_dir / is_file;remove_dir 删除非空目录得到 Err(DirectoryNotEmpty),remove_dir_all 递归删除,之后目录不存在。", t=tl(S(5)), done=lidx(S(5), 'read_dir', 'metadata(a)', 'remove_dir 删除', 'remove_dir_all'), kv=KV([['read_dir', '顺序不保证'], ['remove_dir', '非空 → DirectoryNotEmpty'], ['remove_dir_all', '递归删除']], ['read_dir'])),
]
A = mkart('u131', 131, 'Rust,std::fs,文件读写,IO,真实验证,动画演示',
    f'用真实文件系统验证 std::fs:一行读写与 UTF-8 要求;NotFound(2)/PermissionDenied(13)/AlreadyExists/IsADirectory(21) 的错误;OpenOptions 的覆盖/截断/追加;tmp + rename 原子替换 300 次读者撕裂 {at.group(3)} 次而直接覆盖读到不完整内容 {di.group(2)} 次;read_dir 顺序不保证。',
    '读写文件看起来很简单,细节却不少:文本与字节、错误的种类、写入时是覆盖还是截断、怎样写才不会让读者看到写了一半的文件。这篇用真实的文件系统与并发读者把这些都验证了。',
    [(f'{at.group(3)} 对 {di.group(2)}', '原子替换与直接覆盖时,读者读到撕裂/不完整内容的次数'), ('13 / 2 / 21', 'PermissionDenied、NotFound、IsADirectory 对应的 OS 错误码'), ('InvalidData', 'read_to_string 遇到非法 UTF-8 的错误种类')],
    [('一行读写', '<p>缓冲读写见<a href="rust-bufreader.html">BufReader 与缓冲读取</a>和<a href="rust-bufwriter.html">BufWriter 与批量写入</a>。</p>'), ('io::Error', None), ('OpenOptions', None), ('原子替换', '<p>文件描述符的释放见<a href="rust-file-descriptor-release.html">文件描述符与资源释放</a>。结果的具体次数每次运行不同。</p>'), ('目录', '<p>路径类型见<a href="rust-path-pathbuf.html">Path 与 PathBuf</a>。</p>')],
    steps, [ENV_U + '。文件放在系统临时目录并在结束后删除(部分测试保留 u131 目录,不含敏感数据)', '没有验证:fsync 与掉电安全、rename 在不同文件系统间的行为、Windows 上 rename 覆盖已打开文件的行为、符号链接与硬链接、文件锁(见文件锁一篇)'], 'std::fs')

from lib import *
S = SS('u14')
steps = [
    step("模块里的项默认私有。bank::Account 的 owner 是 pub,balance 不是:a.balance 报 error[E0616]: field `balance` of struct `Account` is private(并提示「a method `balance` also exists, call it with parentheses」);bank::audit() 报 error[E0603]: function `audit` is private。通过 pub 方法 balance() 读余额没问题(余额 50)。", t=tl(S(1)), mark=lidx(S(1), 'error[E0616]', 'error[E0603]'), kv=KV([['私有字段', 'E0616'], ['私有函数', 'E0603']], ['私有字段'])),
    step("可见性可以限定范围:pub(crate) 整个 crate 可见、pub(super) 只有父模块可见、pub 到处可见。outer 里调用 inner::parent_only() 成功,输出「pub(super):只有父模块 outer 可见」;从 main 直接调 outer::inner::parent_only() 报 error[E0603]: function `parent_only` is private。", t=tl(S(2)), mark=lidx(S(2), 'error[E0603]'), done=lidx(S(2), 'pub(crate)', 'pub:', 'pub(super)'), kv=KV([['pub(crate)', '整个 crate'], ['pub(super)', '只到父模块']], ['pub(super)'])),
    step("私有性的方向:子模块可以访问祖先模块的私有项(child::peek() 里的 super::secret() 没有被编译器指出错误),但祖先不能访问子模块的私有项 —— 父模块里调用 child::hidden()(私有)被拒绝。私有是「模块树里向下不可见」。", t=tl(S(3)), mark=lidx(S(3), 'error'), kv=KV([['子 → 祖先的私有项', '可以'], ['祖先 → 子的私有项', '不可以']], ['祖先 → 子的私有项'])),
    step("文件与模块的对应:main.rs 里写 mod util; 就去找 src/util.rs;mod net; 找 src/net.rs 或 src/net/mod.rs,里面再 pub mod client; 对应 src/net/client.rs。cargo run 输出「来自 util.rs」「来自 net/client.rs」。声明了 mod nothere; 却没有文件时报 error[E0583]: file not found for module `nothere`,并告诉你该创建 src/nothere.rs 或 src/nothere/mod.rs。", t=tl(S(4)), done=lidx(S(4), '来自'), mark=lidx(S(4), 'error[E0583]'), kv=KV([['mod foo;', 'foo.rs 或 foo/mod.rs'], ['找不到文件', 'E0583']], ['mod foo;'])),
]
A = mkart('u14', 14, 'Rust,模块,可见性,pub,真实验证,动画演示',
    '用真实编译验证模块与可见性:默认私有,访问私有字段/函数报 E0616/E0603;pub(crate)、pub(super) 的范围;子模块能访问祖先的私有项而祖先不能访问子模块的;mod foo; 对应 foo.rs 或 foo/mod.rs,缺文件报 E0583。',
    '模块系统是 Rust 里最容易「看懂了、写不对」的部分。这篇用真实的编译器报错把规则一条条验证:什么算私有、pub 的几种范围、私有性在模块树里的方向,以及 mod 声明和磁盘文件是怎么对应的。',
    [('E0603 / E0616', '访问私有函数 / 私有字段的错误'), ('pub(super)', '只有父模块可见;从外面调用被拒绝'), ('E0583', 'mod 声明了却没有对应文件')],
    [('默认私有', None), ('pub(crate)、pub(super)', None), ('私有性的方向', None), ('模块与文件', '<p>crate、package、workspace 的关系见<a href="rust-crate-package-workspace.html">Crate、Package 与 Workspace</a>。</p>')],
    steps, [ENV_U + '。前三节用 rustc 单文件编译,第四节用 cargo 项目验证目录结构', '没有验证:pub(in path)、use 的重导出 pub use、use 的 glob 导入与命名冲突、#[path] 属性、测试模块 #[cfg(test)] mod tests 对私有项的访问'], '模块与可见性')

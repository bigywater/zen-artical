from lib import *
S = SS('u51')
steps = [
    step("Display 面向用户,Debug 面向开发者,{} 需要 Display,{:?} 需要 Debug。只 derive 了 Debug 的 P 用 {} 打印报 error[E0277]: `P` doesn't implement `std::fmt::Display`,note 提示「in format strings you may be able to use `{:?}` (or {:#?} for pretty-print) instead」。", t=tl(S(1)), mark=lidx(S(1), 'error[E0277]'), kv=KV([['{}', '需要 Display'], ['{:?}', '需要 Debug(可 derive)']], ['{}'])),
    step("同一个值两种输出的差别:字符串 Debug 带引号并转义(\"a\\\"b\\n\"),Display 原样;字符 ' 的 Debug 是 '\\'';浮点 1.0 的 Display 是 1,Debug 是 1.0;1e21 的 Display 是一长串 1000000000000000000000,Debug 是 1e21;Option 与 Vec 只有 Debug。{:#?} 分行缩进打印嵌套结构。", t=tl(S(2)), done=lidx(S(2), 'Display:', 'Debug:'), kv=KV([['1.0f64', 'Display 1 / Debug 1.0'], ['字符串', 'Debug 带引号与转义']], ['1.0f64'])),
    step("格式化说明符:宽度与对齐({:8}、{:<8}、{:>8}、{:^8},字符串默认左对齐、数字默认右对齐)、填充({:*^8} 得 ***ab***、{:->8})、补零与符号({:08}、{:+08.2} 得 +0003.14)、精度({:.2}、{:8.3}、{:.1e})、进制({:x}、{:#x}、{:#010x} 得 0x000000ff、{:b}、{:#b}、{:o})、宽度来自参数({:w$.p$}、{:.*})、位置与命名参数。", t=tl(S(3)), done=lidx(S(3), '['), kv=KV([['{:*^8}', '***ab***'], ['{:#010x}', '0x000000ff'], ['{:+08.2}', '+0003.14']], ['{:#010x}'])),
    step("自定义 Display 时宽度与对齐默认被忽略:write!(f, ...) 实现的 A 用 {:>6} 与 {:<6} 都输出 [ab];用 f.pad(...) 实现的 B 则遵守,得 [    ab] 与 [ab    ]。Debug 手写用 f.debug_struct(\"Secret\").field(...),可以把敏感字段遮掉:{:?} 输出 Secret { user: \"ann\", pass: \"***\" },{:#?} 自动分行缩进。", t=tl(S(4)), mark=lidx(S(4), 'write!', 'f.pad'), done=lidx(S(4), 'Secret'), kv=KV([['write! 实现', '忽略宽度'], ['f.pad 实现', '遵守宽度与对齐']], ['f.pad 实现'])),
]
A = mkart('u51', 51, 'Rust,Display,Debug,格式化,真实验证,动画演示',
    '用真实运行验证 Display 与 Debug:{} 对只有 Debug 的类型报 E0277;字符串、字符、浮点的两种输出差别与 {:#?};宽度、对齐、填充、精度、符号、进制等格式化说明符;自定义 Display 用 write! 会忽略宽度而 f.pad 遵守;用 debug_struct 手写 Debug 遮掉敏感字段。',
    '格式化是每天都在用的功能,但很多细节容易写错:Display 和 Debug 到底有什么不同、说明符的完整写法、为什么自己实现 Display 之后 {:>8} 不起作用。这篇逐项跑出真实输出。',
    [('E0277', '{} 用在只有 Debug 的类型上'), ('f.pad', '自定义 Display 要遵守宽度与对齐必须用它,write! 会忽略'), ('{:#010x}', '0x000000ff:带前缀、补零、宽度 10 的十六进制')],
    [('两个 trait', '<p>derive(Debug) 的展开见<a href="rust-derive-traits.html">derive 自动生成 Trait 实现</a>。</p>'), ('同一个值的两种输出', None), ('格式说明符', None), ('自定义 Display 与 Debug', None)],
    steps, [ENV_U, '没有验证:{:p} 指针格式、{:?} 在 HashMap 上的顺序(不稳定)、i18n、fmt::Write 与 io::Write 的区别、format_args! 的零分配'], 'Display 与 Debug')

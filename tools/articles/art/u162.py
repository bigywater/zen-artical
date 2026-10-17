from lib import *
S = SS('u162')
R = J('u162'); W = R['widths']
steps = [
    step("rustfmt --check 不改文件:对一份故意写得挤成一团的代码(13 行,import 没分行、没有空格、if/else 压在一行),退出码是 1,输出一份 Diff:红色的 - 是原来的行、绿色的 + 是格式化后的行。CI 里的 cargo fmt --check 就靠这个退出码判断「有没有人忘了格式化」。", t=tl(S(1)), mark=lidx(S(1), '退出码 1', 'Diff in'), kv=KV([['--check', '只报差异,不改文件'], ['退出码', '1 = 有差异,0 = 已格式化']], ['退出码'])),
    step(f"格式化后 13 行变成 38 行:use 分成三行、struct 的字段各占一行、长函数签名的参数各占一行、长表达式在加号处换行并缩进。而程序含义完全没变:格式化前后用 rustc -O2 生成的汇编(去掉文件名与调试指令)哈希都是 {R['asm'][0][0]}、983 行,逐行相同({R['asm'][2]})。格式化只改空白与换行,不改语义。", t=tl(S(2)), done=lidx(S(2), '格式化前 汇编哈希', '格式化后的代码', 'use std::io::{self, Read};'), kv=KV([['行数', '13 → 38'], ['汇编哈希', f"{R['asm'][0][0]} = {R['asm'][1][0]}(相同)"]], ['汇编哈希'])),
    step("幂等:对已经格式化的代码再运行一次 rustfmt,内容与第一次完全相同(True);再 --check,退出码 0。同一份代码无论格式化多少次结果都一样,所以团队里每个人的编辑器与 CI 不会来回改。", t=tl(S(3)), done=lidx(S(3), '第二次格式化后', '再 --check'), kv=KV([['格式化两次', '结果相同'], ['再 --check', '退出码 0']], ['格式化两次'])),
    step(f"rustfmt.toml 里的 max_width 决定换行:同一段代码,max_width = 40 时变成 {len(W['40'])} 行(vec! 的元素分两行、方法链每个调用一行);max_width = 100(默认)与 140 都是 {len(W['100'])} 行,保持在一行内。只要选项在稳定版里可用,放在 rustfmt.toml 里整个项目共享。", t=tl(S(4)), done=lidx(S(4), 'max_width = 40', 'max_width = 100', 'max_width = 140'), b=bars([['max_width=40', len(W['40']), f"{len(W['40'])} 行"], ['max_width=100', len(W['100']), f"{len(W['100'])} 行"], ['max_width=140', len(W['140']), f"{len(W['140'])} 行"]], len(W['40']), done=[0, 1, 2]), kv=KV([['max_width = 40', f"{len(W['40'])} 行"], ['max_width = 100 / 140', f"{len(W['100'])} 行"]], ['max_width = 40'])),
    step("#[rustfmt::skip] 让某段保持手工排版:对齐的 3×3 单位矩阵 m 加了 skip,格式化后保持 1,0,0 / 0,1,0 / 0,0,1 三行不变;没有 skip 的 n 被压成 [1, 0, 0, 0, 1, 0]。在 rustfmt.toml 里写 nightly 才有的选项(imports_granularity)时,稳定版给出警告「Warning: can't set `imports_granularity = Crate`, unstable features are only available in nightly channel」并忽略它。", t=tl(S(5)), done=lidx(S(5), '#[rustfmt::skip]', 'let n = [1, 0, 0, 0, 1, 0]'), mark=lidx(S(5), 'Warning: can\'t set'), kv=KV([['#[rustfmt::skip]', '保留手工排版'], ['nightly 选项', '稳定版警告并忽略']], ['#[rustfmt::skip]'])),
]
A = mkart('u162', 162, 'Rust,rustfmt,代码格式化,工具链,真实验证,动画演示',
    f'用 rustfmt 1.9 验证代码格式化:--check 退出码 1 并给出 Diff;格式化前后汇编哈希相同({R["asm"][0][0]},语义不变);幂等;max_width = 40 时 {len(W["40"])} 行对 100 时 {len(W["100"])} 行;#[rustfmt::skip];稳定版忽略 nightly 才有的配置项并警告。',
    '格式化工具会不会改变程序行为?反复运行结果稳定吗?配置怎么影响输出?想保留手工排版怎么办?这篇用真实的 rustfmt 与汇编哈希逐个验证。',
    [('1 / 0', 'rustfmt --check 在有差异 / 已格式化时的退出码'), (f'{R["asm"][0][0]}', '格式化前后相同的汇编哈希(语义不变)'), (f'{len(W["40"])} 对 {len(W["100"])} 行', 'max_width = 40 与 100 时同一段代码的行数')],
    [('--check', '<p>静态检查工具见<a href="rust-clippy.html">Clippy 静态检查</a>;CI 里的完整用法见<a href="rust-ci.html">Rust 项目持续集成</a>。rustfmt 1.9.0。</p>'), ('语义不变', None), ('幂等', None), ('rustfmt.toml', None), ('跳过与 nightly 选项', None)],
    steps, [ENV_U + '。rustfmt 1.9.0(稳定版)', '没有验证:nightly 选项(imports_granularity、group_imports、wrap_comments 等)的实际效果、cargo fmt 对工作区的处理、对宏内部代码的格式化限制、与 rust-analyzer 保存时格式化的集成、格式化失败(语法错误)时的行为'], 'rustfmt')

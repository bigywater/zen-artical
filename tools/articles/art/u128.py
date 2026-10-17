from lib import *
S = SS('u128')
R = J('u128'); rows = {r[0]: r for r in R['rows']}
b = rows['release(默认)'][1]
def r_(n): return rows[n]
def pct(n): return f"{(r_(n)[1] / b - 1) * 100:+.0f}%"
full = r_('全套:fat+cgu1+abort+z+strip')
steps = [
    step(f"同一个使用 rayon + HashMap + format! 的程序,release 默认配置的二进制是 {b:,} 字节,全量编译 {r_('release(默认)')[2]} s。以它为基准,逐个改 profile 重新全量编译。", t=tl(S(1)), done=lidx(S(1), 'release(默认)'), kv=KV([['基准', f'{b:,} 字节']], ['基准'])),
    step(f"strip = true(去掉符号表):{r_('+ strip = true')[1]:,} 字节({pct('+ strip = true')}),编译时间几乎不变。这是成本最低的瘦身。", t=tl(S(1)), done=lidx(S(1), 'strip = true'), b=bars([['默认', b, f'{b:,}'], ['strip', r_('+ strip = true')[1], f"{r_('+ strip = true')[1]:,}"]], b, done=[0, 1]), kv=KV([['strip = true', f"{pct('+ strip = true')}"]], ['strip = true'])),
    step(f"LTO(链接时优化,跨 crate 内联与去掉死代码):thin {r_('+ lto = \"thin\"')[1]:,} 字节({pct('+ lto = \"thin\"')}),fat {r_('+ lto = \"fat\"')[1]:,} 字节({pct('+ lto = \"fat\"')}),fat + codegen-units = 1 是 {r_('+ lto fat + codegen-units = 1')[1]:,} 字节({pct('+ lto fat + codegen-units = 1')});代价是编译时间从 {r_('release(默认)')[2]} s 涨到 {r_('+ lto = \"fat\"')[2]} s。", t=tl(S(1)), done=lidx(S(1), 'lto = "thin"', 'lto = "fat"', 'codegen-units = 1'), b=bars([['默认', b, f'{b:,}'], ['thin', r_('+ lto = "thin"')[1], f"{r_('+ lto = \"thin\"')[1]:,}"], ['fat', r_('+ lto = "fat"')[1], f"{r_('+ lto = \"fat\"')[1]:,}"], ['fat+cgu1', r_('+ lto fat + codegen-units = 1')[1], f"{r_('+ lto fat + codegen-units = 1')[1]:,}"]], b, done=[0, 1, 2, 3]), kv=KV([['thin', pct('+ lto = "thin"')], ['fat', pct('+ lto = "fat"')], ['fat + cgu=1', pct('+ lto fat + codegen-units = 1')]], ['fat'])),
    step(f"panic = \"abort\"(不生成展开用的代码):{r_('+ panic = \"abort\"')[1]:,} 字节({pct('+ panic = \"abort\"')})。", t=tl(S(1)), done=lidx(S(1), 'panic = "abort"'), kv=KV([['panic = abort', pct('+ panic = "abort"')]], ['panic = abort'])),
    step(f"出乎意料:opt-level = \"s\" 是 {r_('+ opt-level = \"s\"')[1]:,} 字节({pct('+ opt-level = \"s\"')}),\"z\" 是 {r_('+ opt-level = \"z\"')[1]:,} 字节({pct('+ opt-level = \"z\"')})—— 在这个程序里反而比默认更大。原因本文没有深挖:预编译的标准库按固定级别构建,这两个级别只影响本 crate 与依赖;而 rayon 这类代码偏向内联时体积不一定变小。「优化体积」不是单调的,要实测。", t=tl(S(1)), mark=lidx(S(1), 'opt-level = "s"', 'opt-level = "z"'), kv=KV([['opt-level = s', pct('+ opt-level = "s"')], ['opt-level = z', pct('+ opt-level = "z"')]], ['opt-level = z'])),
    step(f"全套(fat LTO + codegen-units = 1 + panic = abort + opt-level = z + strip):{full[1]:,} 字节,只有默认的 {full[1] / b * 100:.0f}%({pct('全套:fat+cgu1+abort+z+strip')}),编译 {full[2]} s。各项运行时间都在几毫秒的噪声范围内(每项取 5 次最小值,范围 {min(r[3] for r in R['rows'])}–{max(r[3] for r in R['rows'])} ms),这个微小程序里看不出运行性能差别。", t=tl(S(1)), done=lidx(S(1), '全套'), b=bars([[r[0].split('(')[0].replace('+ ', '')[:14], r[1], f'{r[1]:,}'] for r in R['rows']], b * 1.05, done=list(range(len(R['rows'])))), kv=KV([['默认', f'{b:,}'], ['全套', f"{full[1]:,}({pct('全套:fat+cgu1+abort+z+strip')})"]], ['全套'])),
]
A = mkart('u128', 128, 'Rust,LTO,二进制体积,Cargo,真实验证,动画演示',
    f'下载 rayon 做一个真实依赖的程序,逐项改 release profile 全量重编:strip {pct("+ strip = true")}、thin LTO {pct('+ lto = "thin"')}、fat LTO {pct('+ lto = "fat"')}、panic = abort {pct('+ panic = "abort"')};opt-level s/z 反而更大;全套配置只剩默认体积的 {full[1] / b * 100:.0f}%({full[1]:,} 字节)。',
    '想让 Rust 二进制变小,常见招数有 strip、LTO、panic = abort、opt-level = "z"。每一招到底省多少、编译时间涨多少、有没有反效果?这篇在同一个真实依赖的程序上逐项实测。',
    [(f'{full[1] / b * 100:.0f}%', '全套瘦身配置的二进制大小占默认的比例'), (pct('+ strip = true'), 'strip = true 单独带来的体积变化'), ('s / z 更大', 'opt-level = "s" 与 "z" 在这个程序里的结果')],
    [('各项配置的体积', '<p>Cargo profile 的完整配置见<a href="rust-cargo-profile.html">Cargo Profile</a>;更细的体积分析见<a href="rust-binary-size-analysis.html">二进制体积分析</a>。rayon 1.x 从 crates.io 下载。</p>')],
    steps, [ENV_U + '。每个变体全量重编;运行时间是该进程 5 次中的最小值', '没有验证:opt-level s/z 变大的原因、upx 压缩、-Z build-std、不同程序(无依赖 / 大依赖)上的结果差别、LTO 对运行速度的影响(这个微小程序里量不出)'], 'LTO 与二进制体积')

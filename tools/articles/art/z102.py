from lib import *
R = J('z102'); rows = [r for r in R['rows'] if 'zk' in r]; kf = R['kafka']; zv = R['zkvers']
def S(k): return [x for x in out('z102').split('== ')[k].splitlines()[1:] if x.strip()]
has = [r for r in rows if r['zk']]; no = [r for r in rows if not r['zk']]
steps = [
    step(f"查 14 个常见项目最新正式版的 Maven 依赖图(deps.dev 对 Maven Central 的解析):{len(has)} 个项目的依赖图里有 ZooKeeper —— " + '、'.join(f"{r['ga'].split(':')[1]} {r['zk'][0]}({'直接' if r['zk'][1] == 'DIRECT' else '传递'})" for r in has) + "。ZooKeeper 客户端版本分布在 3.8.x 与 3.9.x。", t=tl(S(1)), done=[0], kv=KV([['有 ZooKeeper 依赖', f'{len(has)} 个项目'], ['版本', '3.8.x / 3.9.x']], ['有 ZooKeeper 依赖'])),
    step("依赖图里「没有」ZooKeeper 的项目:" + '、'.join(r['ga'].split(':')[1] for r in no) + "。这不等于「不使用」—— 可能是可选(optional)或 provided 依赖,由使用者自己引入;我没有逐个查原因。例如本系列第 101 篇真正运行 Dubbo 时,就需要自己额外引入 Curator 与 ZooKeeper 的依赖。", t=tl(S(1)), mark=[len(S(1)) - 1], kv=KV([['依赖图里没有', '≠ 不用 ZooKeeper'], ['原因', '没有查']], ['依赖图里没有'])),
    step("Kafka 各版本对 ZooKeeper 的依赖:" + ';'.join(f"{k['v']} → {(k['zk'][0]) if k['zk'] else '无'}" for k in kf) + "。从 3.x 的直接依赖(3.5.9 → 3.6.3 → 3.8.4)到 4.0.2 起依赖图里不再有 ZooKeeper,与「Kafka 4.0 去掉 ZooKeeper 模式」一致(第 103、104 篇会具体实验)。", t=tl(S(2)), b=bars([[k['v'], 1 if k['zk'] else 0, k['zk'][0] if k['zk'] else '无'] for k in kf], 1, mark=[len(kf) - 2, len(kf) - 1], done=list(range(len(kf) - 2))), kv=KV([['3.9.2', 'ZooKeeper 3.8.4'], ['4.0.2 / 4.1.2', '无']], ['4.0.2 / 4.1.2'])),
    step("ZooKeeper 自己在 Maven Central 的最近版本:" + '、'.join(f"{v}({t})" for v, t in zv) + "。3.8 与 3.9 两个系列并行维护(同一天 3.8.7 与 3.9.6 发布),所以其它项目声明的依赖会落在不同的小版本上 —— 升级 ZooKeeper 服务端时,要看你的客户端依赖是哪一版(见第 69 篇滚动升级)。", t=tl(S(3)), done=[0], kv=KV([['并行维护', '3.8.x 与 3.9.x'], ['最新', '3.9.6']], ['并行维护'])),
]
A = dict(
    n=102, series='zookeeper', tags='ZooKeeper,生态,Maven,依赖,真实验证,动画演示',
    desc=f'用 deps.dev 解析 14 个常见项目的 Maven 依赖图:{len(has)} 个声明了 ZooKeeper 依赖(3.8.x / 3.9.x);Kafka 3.9.2 依赖 ZooKeeper 3.8.4、4.0.2 起依赖图里没有 ZooKeeper;依赖图里没有不等于不使用。',
    lead='「谁在用 ZooKeeper」常被讲成一份名单,但名单很容易过时。这篇不列印象,而是查数据:拿 14 个常见项目最新正式版的 Maven 依赖图,看它们声明了哪个版本的 ZooKeeper,再看 Kafka 从 2.8 到 4.1 的依赖是怎么变的。它只能说明「声明了什么」,不能说明「怎么用」;怎么用的部分,本系列后面几篇会逐个实验。',
    facts=[(f'{len(has)} / 14', '依赖图里有 ZooKeeper 的项目数(最新正式版)'), ('3.8.4 → 无', 'Kafka 3.9.2 → 4.0.2 依赖图中的 ZooKeeper'), ('3.8.x + 3.9.x', 'ZooKeeper 同时维护的两个系列')],
    body=[
        sec('14 个项目的依赖', '', term('', blk('z102', 1)), '<p>数据是 deps.dev 解析 Maven Central 的依赖图得到的;「DIRECT」是 pom 里直接写的,「INDIRECT」是通过别的库带进来的(比如通过 Curator)。</p>'),
        sec('Kafka 的变化', '', term('', blk('z102', 2)), '<p>这只是依赖图上的变化。Kafka 4.0 具体怎么运行、从 ZooKeeper 迁移到 KRaft 的过程见第 103、104 篇。</p>'),
        sec('ZooKeeper 的发布', '', term('', blk('z102', 3))),
        sec('分步演示', '', demo('生态数据', [('t', 'term', '输出'), ('b', 'bars', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。数据来自 api.deps.dev 对 Maven Central 的依赖图(2026-10-01 查询,各项目「最新正式版」按发布时间取);没有逐个运行这些项目', '没有验证:依赖图里「无」的项目为什么没有(可选 / provided)、各项目运行时是否必须有 ZooKeeper、druid-processing 的查询失败(404)、非 Java 项目(如 ClickHouse)对 ZooKeeper 或 Keeper 的使用'],
)

from lib import *
R = J('z63')
def S(k): return [l for l in out('z63').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step(f"Prometheus 指标:zoo.cfg 里配置 metricsProvider.className=org.apache.zookeeper.metrics.prometheus.PrometheusMetricsProvider 和 metricsProvider.httpPort=7390 后,GET /metrics 返回 200、Content-Type: text/plain; version=0.0.4,共 {R['n_lines']} 行、{R['n_names']} 个不同的指标名(含每个指标的 _count / _sum / 分位数)。", t=tl(S(1)), done=[0], kv=KV([['端点', '/metrics(text/plain 0.0.4)'], ['规模', f"{R['n_names']} 个指标名"]], ['端点'])),
    step("最常用的指标原样:znode_count 5005、num_alive_connections 1、watch_count 0、outstanding_requests 0、packets_received / packets_sent、fsynctime_count、jvm_memory_bytes_used{area=\"heap\"}、jvm_gc_collection_seconds_count{gc=\"G1 Young Generation\"} 等。ZooKeeper 自己的指标没有 zk_ 前缀(与 mntr 不同),JVM 的指标带 jvm_ 前缀(来自 Prometheus 的 hotspot 导出器)。", t=tl(S(2)), done=[0, 1, 2, 3, 4, 5, 6, 7, 8], kv=KV([['ZooKeeper 指标', '无 zk_ 前缀'], ['JVM 指标', 'jvm_ 前缀,含 GC 次数 / 耗时']], ['ZooKeeper 指标'])),
    step("GC 日志(-Xlog:gc*)里每一次回收都有一行:「Pause Young (Normal) (G1 Evacuation Pause) 14M->3M(34M) 1.763ms」——回收前后堆大小与停顿时间。Prometheus 的 jvm_gc_collection_seconds_* 是累计次数与累计耗时,适合做告警(比如 GC 耗时占比);GC 日志是每一次的细节,适合事后排查(第 62 篇看到,自带的停顿监视器会低估,要以 GC 日志为准)。", t=tl(S(3)), kv=KV([['Prometheus', '累计值,做告警'], ['GC 日志', '每一次的细节,做排查']], ['Prometheus'])),
]
A = dict(
    n=63, series='zookeeper', tags='ZooKeeper,Prometheus,GC日志,监控,真实验证,动画演示',
    desc=f'GC 日志与 Prometheus 指标:ZooKeeper 3.9.6 自带 Prometheus 指标提供者(metricsProvider.className + httpPort),/metrics 共 {R["n_names"]} 个指标名,含 znode_count、num_alive_connections、outstanding_requests、fsynctime_* 以及 jvm_gc_collection_seconds_*;GC 日志 -Xlog:gc* 记录每一次回收。',
    lead='生产环境里 ZooKeeper 的监控怎么接?3.6 之后自带 Prometheus 指标端点,不需要额外的 exporter。这篇配置它、抓一次、看有哪些指标,再看 GC 日志怎么和它们配合。',
    facts=[(f'{R["n_names"]} 个', '/metrics 里不同的指标名'), ('无 zk_ 前缀', 'ZooKeeper 的指标与 mntr 同源但命名不带 zk_'), ('累计 vs 明细', 'jvm_gc_* 适合告警,GC 日志适合排查')],
    body=[
        sec('开启 Prometheus 端点', '', term('', blk('z63', 1)), '<p>这个端点没有认证,所以只绑定 127.0.0.1(<code>metricsProvider.httpHost</code>)。要给 Prometheus 抓取,应当放在内网并用防火墙限制来源(第 67 篇谈四字命令的暴露面,同样的道理)。</p>'),
        sec('常用指标', '', term('', blk('z63', 2))),
        sec('GC 日志', '', term('', blk('z63', 3))),
        sec('分步演示', '', demo('Prometheus 与 GC 日志', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。单机,JVM 堆 128 MiB(G1);Prometheus 提供者在 3.9.6 jar 的 zookeeper-prometheus-metrics 里;GC 日志 -Xlog:gc*:file=…', '没有验证:Prometheus 服务端的抓取与告警规则、Grafana 面板、集群里 leader / follower 各自独有的指标、指标基数很大(几万个路径)时的抓取耗时(这里已经有 1.5 万行)'],
)

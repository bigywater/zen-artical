from lib import *
import re
R = J('d61')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
sp = re.search(r'dumpdata 1 万行: ([\d.]+) s,文件 (\d+) KiB;loaddata 1 万行: ([\d.]+) s', R['speed'])
steps = [
    step("dumpdata 输出一个 JSON 数组,每个对象是 {model, pk, fields}:外键存的是数字 pk(\"author\": 1),日期是 ISO 字符串。默认格式 json,还支持 jsonl 和 xml。--natural-foreign 时外键写成自然键 [\"ann\"](要求被引用的模型有 natural_key());--natural-primary 时干脆不输出 pk。", t=tl(L('dump')[:5], cur=[0, 1, 2]), kv=KV([['默认', 'pk + 数字外键'], ['natural key', '用业务键代替数字 id']], ['natural key'])),
    step("loaddata 用的是原始保存(raw):模型自定义的 save() 没有被调用(标题是 'from-fixture',没有被加 '!'),auto_now 的字段保留文件里写的 2000-01-01,而不是当前时间;但 post_save 信号仍会触发一次,且 raw=True。所以信号处理函数里要判断 raw,否则装载 fixture 会触发业务逻辑。", t=tl(L('load')), kv=KV([['loaddata', '不调用 save(),但发 post_save(raw=True)']], ['loaddata'])),
    step("边界:同 pk 再装载一次是覆盖(update),不是新增(pk=7 的名字变成 zed2,作者总数仍是 1);fixture 里多了模型没有的字段 → DeserializationError;外键指向不存在的行 → IntegrityError: … has an invalid foreign key(约束在装载结束时统一检查)。", t=tl(L('edge')), kv=KV([['同 pk', '覆盖'], ['坏数据', '装载失败']], ['同 pk'])),
    step("为什么需要 natural key:数字 pk 在不同环境里不一样,fixture 里写死 \"author\": 1 装到另一个库会指错人。用 natural_primary + natural_foreign,Author 不输出 pk,Book 的 author 写成 [\"ann\"](按 name 关联)。", t=tl(L('natural')), kv=KV([['跨环境', '用 natural key 关联']], ['跨环境'])),
    step(f"速度:1 万本书 dumpdata {sp.group(1)} s、文件 {sp.group(2)} KiB;loaddata {sp.group(3)} s(慢得多——逐条反序列化、逐条 save_base)。fixture 适合测试数据和小型初始数据,不适合大规模迁移数据。", b=bars([['dumpdata 1 万行(s)', float(sp.group(1)), sp.group(1)], ['loaddata 1 万行(s)', float(sp.group(3)), sp.group(3)]], float(sp.group(3)) * 1.1, mark=[1], done=[0]), kv=KV([['loaddata', f"{sp.group(3)} s / 1 万行"]], ['loaddata'])),
]
A = dict(
    n=61, series='django', tags='Django,fixture,dumpdata,loaddata,真实验证,动画演示',
    desc=f'实测 dumpdata / loaddata:输出格式与 natural key;loaddata 不调用自定义 save()、auto_now 保留文件里的值、post_save 以 raw=True 触发;同 pk 是覆盖;坏字段与坏外键的报错;1 万行 dumpdata {sp.group(1)} s、loaddata {sp.group(3)} s。',
    lead='fixture 是测试和初始数据的老朋友,但它绕过了很多你以为一定会发生的事:自定义 save()、auto_now、约束顺序。这篇逐项验证 dumpdata 与 loaddata 的行为。',
    facts=[('不调用 save()', 'loaddata 不执行模型自定义的 save();post_save 信号仍触发,raw=True'), ('覆盖', '同 pk 再装载一次是 update,不是新增'), (f'{sp.group(1)} vs {sp.group(3)} s', '1 万行:dumpdata vs loaddata')],
    body=[
        sec('dumpdata 的输出', '', term('', blk('d61', 1)), '<p>默认导出所有指定 app 的所有对象;跨环境用 natural key 避免数字 id 冲突。<code>contenttypes</code>、<code>auth.permission</code> 之类由迁移自动创建的数据一般要 <code>--exclude</code>(本文没有测)。</p>'),
        sec('loaddata 绕过了什么', '', term('', blk('d61', 2)), '<p>用 <code>Model.save_base(raw=True)</code> 保存。所以:自定义 <code>save()</code> 不执行、<code>auto_now</code>/<code>auto_now_add</code> 用文件里的值、信号处理函数收到 <code>raw=True</code>。</p>'),
        sec('覆盖与错误', '', term('', blk('d61', 3)), '<p>fixture 是「按 pk 写入」,重复装载幂等;数据有误时报错并整体回滚(本文只验证了报错,没有验证回滚范围)。</p>'),
        sec('natural key', '', term('', blk('d61', 4)), '<p>要在模型上实现 <code>natural_key()</code> 与管理器的 <code>get_by_natural_key()</code>(本文只实现了前者,装载路径没有测)。</p>'),
        sec('速度', '', term('', blk('d61', 5)), '<p>SQLite 单机数字。</p>'),
        sec('分步演示:fixture 的行为', '', demo('fixture', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:loaddata 装载失败时的事务回滚范围、fixtures 目录的搜索顺序与 FIXTURE_DIRS、压缩格式(.gz)、PostgreSQL 上的序列重置(loaddata 之后 pk 序列是否需要 sqlsequencereset)、natural key 在装载路径上的 get_by_natural_key'],
)

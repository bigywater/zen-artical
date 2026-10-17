from lib import *
import re
R = J('d33')
rows = []
for l in R['perf'].splitlines():
    m = re.search(r'^(.*?)\s+([\d.]+) ms\s+峰值内存\s+([\d.]+) MiB', l)
    if m: rows.append((m.group(1).strip(), float(m.group(2)), float(m.group(3))))
steps = [
    step(f"50000 行、4 列(其中一列 200 字节)全部读进内存:模型对象 Row.objects.all() {rows[0][1]:.0f} ms、峰值内存 {rows[0][2]:.0f} MiB;values('a','b')(dict){rows[3-1][1]:.0f} ms / {rows[2][2]:.0f} MiB;values_list('a','b')(tuple){rows[3][1]:.0f} ms / {rows[3][2]:.0f} MiB;values_list('a', flat=True){rows[4][1]:.0f} ms / {rows[4][2]:.0f} MiB。", b=bars([[r[0][:34], r[1], f"{r[1]:.0f} ms"] for r in rows], rows[0][1] * 1.1, mark=[0], done=[4]), kv=KV([['最慢', '完整模型对象'], ['最快', 'values_list(flat=True)']], ['最慢'])),
    step("同样的数据,峰值内存(tracemalloc):" + ';'.join(f"{r[0][:20]} {r[2]:.1f} MiB" for r in rows[:5]) + "。模型实例每个都带 __dict__ 与 _state,比 tuple / int 重得多。", b=bars([[r[0][:34], r[2], f"{r[2]:.1f} MiB"] for r in rows], rows[0][2] * 1.1, mark=[0], done=[4]), kv=KV([['内存', f"对象 {rows[0][2]:.0f} MiB → flat {rows[4][2]:.0f} MiB"]], ['内存'])),
    step(f"only('a') 仍然构造模型对象:耗时 {rows[1][1]:.0f} ms,与取全部字段 {rows[0][1]:.0f} ms 接近——构造对象的开销主要在「每行一个实例」,不在列数(内存少了,{rows[1][2]:.0f} vs {rows[0][2]:.0f} MiB)。", kv=KV([['only()', '省内存,不省对象构造'], ['耗时', f"{rows[1][1]:.0f} vs {rows[0][1]:.0f} ms"]], ['only()'])),
    step("类型:对象是 Row(带 __dict__ / _state);values() 是 dict;values_list() 是 tuple;flat=True 是单个值;named=True 得到具名元组 Row(a=0, b='bee-0')。values() 只给数据库列,模型上定义的方法、@property 都拿不到。", t=tl(R['types'].splitlines() + R['nomodel'].splitlines()[1:], cur=[0, 1, 2, 3, 4], mark=[5]), kv=KV([['values / values_list', '只有列,没有模型逻辑']], ['values / values_list'])),
]
A = dict(
    n=33, series='django', tags='Django,ORM,values,性能,真实验证,动画演示',
    desc=f'5 万行读入内存:模型对象 {rows[0][1]:.0f} ms / {rows[0][2]:.0f} MiB,values() {rows[2][1]:.0f} ms / {rows[2][2]:.0f} MiB,values_list(flat=True) {rows[4][1]:.0f} ms / {rows[4][2]:.1f} MiB;only() 省内存但仍构造对象;values 系列拿不到模型上的方法。',
    lead='只要几个值的时候,什么时候该用 values() / values_list()?省多少?这篇用 5 万行数据量出耗时和峰值内存,并说明 values 系列失去了什么。',
    facts=[(f'{rows[0][1]:.0f} → {rows[4][1]:.0f} ms', '5 万行:完整模型对象 → values_list(flat=True) 的耗时'), (f'{rows[0][2]:.0f} → {rows[4][2]:.1f} MiB', '同样两种取法的峰值内存(tracemalloc)'), ('only() 还是对象', 'only("a") 构造的仍是模型实例,耗时与全字段接近')],
    body=[
        sec('耗时与内存', '', term('', blk('d33', 1)), '<p>耗时每种取 3 次中最快的一次(不带 tracemalloc);内存是另开一次用 <code>tracemalloc</code> 量的峰值。(我第一次把两者混在一起量,tracemalloc 把耗时放大了近 7 倍,后来拆开了。)</p>'),
        sec('每种写法的类型', '', term('', blk('d33', 2)), term('', blk('d33', 3)), '<p>取舍:需要模型上的方法 / 属性 / 信号 / 关系访问就用对象;只要数据(导出、聚合前的中间值、大批量处理)用 <code>values</code> / <code>values_list</code>;只想省一列大字段,<code>only</code> / <code>defer</code>(第 29 篇)。</p>'),
        sec('分步演示:对象与值', '', demo('values 与对象', [('b', 'bars', '耗时 / 内存'), ('t', 'term', '类型'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite,50000 行,c 列 40 字符、d 列 200 字节', '没有验证:PostgreSQL / MySQL 上网络传输带来的差别、iterator() 与 chunk_size 对内存的影响(第 102 篇)、CPython 版本差异、values() 对带 from_db_value 的自定义字段的转换(第 38 篇)'],
)

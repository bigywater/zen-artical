import json
marks = json.load(open('out/71.marks'))
samples = []
for l in open('out/71.samples'):
    t, _, rest = l.strip().partition(' ')
    samples.append((float(t), [x for x in rest.split(';') if x]))
port = None
res = []
for t, name in marks:
    # 取该阶段标记后 0.35s 处最近的采样(阶段内会停顿 0.7s 以上, 此时内核状态已稳定)
    s = min(samples, key=lambda x: abs(x[0] - (t + 0.35)))
    rows = []
    for e in s[1]:
        a, b, st = e.split(' ')
        rows.append((a.rsplit('.', 1)[1], b.rsplit('.', 1)[1] if b != '*.*' else '*', st))
    res.append((name.split(' ')[0], name, rows))
lines = []
for code, name, rows in res:
    lines.append(f"{name}")
    for a, b, st in rows: lines.append(f"    本地端口 {a:>5}  对端 {b:>5}  {st}")
    if not rows: lines.append("    (netstat 里没有这个端口的任何连接)")
open('out/71_timeline.txt', 'w').write('\n'.join(lines) + '\n')
json.dump(res, open('out/71_timeline.json', 'w'), ensure_ascii=False)
print('\n'.join(lines))

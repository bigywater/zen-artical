import sys, os, asyncio, subprocess, textwrap; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p21')
d = pdir('p21')
CODE = textwrap.dedent(r'''
    import asyncio, sys, time, resource, json
    maxsize, N, item_kb, cons_ms, prod_ms = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
    async def main():
        q = asyncio.Queue(maxsize=maxsize); peak = 0; done_prod = None
        async def producer():
            nonlocal done_prod
            for i in range(N):
                if prod_ms: await asyncio.sleep(prod_ms / 1000)
                await q.put(b'x' * (item_kb * 1024))        # 每个"页面"都是新分配并写满的 item_kb KB
                nonlocal peak; peak = max(peak, q.qsize())
            done_prod = time.perf_counter() - t0
            await q.put(None)
        async def consumer():
            while True:
                x = await q.get()
                if x is None: return
                await asyncio.sleep(cons_ms / 1000)
        t0 = time.perf_counter()
        await asyncio.gather(producer(), consumer())
        return done_prod, time.perf_counter() - t0, peak
    base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
    p, tot, peak = asyncio.run(main())
    print(json.dumps(dict(prod=p, total=tot, peak=peak, base=base, mem=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576)))
''')
(d / 'q.py').write_text(CODE)
import json
def run(maxsize, N=2000, kb=100, cons=5, prod=0):
    o = subprocess.run([sys.executable, str(d / 'q.py'), str(maxsize), str(N), str(kb), str(cons), str(prod)], capture_output=True, text=True, timeout=300)
    return json.loads(o.stdout)

print('== 一:生产者很快、消费者很慢(消费者每个条目 5 ms),2000 个条目,每个 100 KB,队列有界与无界')
print(f'  {"队列":<14}{"生产者发完用了":>14}{"队列最长":>9}{"峰值内存":>10}{"全部处理完":>12}')
for ms_, lab in ((0, '无界(maxsize=0)'), (1000, 'maxsize=1000'), (100, 'maxsize=100'), (10, 'maxsize=10'), (1, 'maxsize=1')):
    r = run(ms_)
    print(f'  {lab:<14}{r["prod"] * 1000:>11.0f} ms{r["peak"]:>9}{r["mem"]:>8.0f} MiB{r["total"] * 1000:>9.0f} ms')
print(f'  (起点内存 {r["base"]:.0f} MiB;2000 个 100 KB 的条目合计约 {2000 * 100 / 1024:.0f} MiB)')

print('== 二:队列上限只管"积压",不改变吞吐:消费者是瓶颈时总时间都由消费者决定;生产者是瓶颈时队列根本积不起来')
print(f'  {"场景":<28}{"maxsize":>8}{"队列最长":>9}{"全部处理完":>12}')
for lab, prod, cons in (('消费者慢(5 ms)、生产者快', 0, 5), ('生产者慢(5 ms)、消费者快(1 ms)', 5, 1)):
    for m in (0, 10):
        r = run(m, N=1000, kb=10, cons=cons, prod=prod)
        print(f'  {lab:<28}{m:>8}{r["peak"]:>9}{r["total"] * 1000:>9.0f} ms')

print('== 三:put_nowait 与 join:有界队列满了会怎样,忘了 task_done 会怎样')
async def semantics():
    q = asyncio.Queue(maxsize=2)
    q.put_nowait(1); q.put_nowait(2)
    try: q.put_nowait(3)
    except Exception as e: print(f'  maxsize=2,已有 2 个,再 put_nowait:{type(e).__name__}')
    t0 = time.perf_counter()
    try: await asyncio.wait_for(q.put(3), 0.3)
    except Exception as e: print(f'  await q.put(3) 一直等到被取消:{type(e).__name__}(等了 {ms(t0):.0f} ms)')
    q2 = asyncio.Queue()
    for i in range(3): q2.put_nowait(i)
    async def c_forget():
        while True: await q2.get()                    # 取了不调 task_done
    c = asyncio.create_task(c_forget()); await asyncio.sleep(0.05)
    t0 = time.perf_counter()
    try: await asyncio.wait_for(q2.join(), 0.5)
    except Exception as e: print(f'  消费者取完了 3 个条目但没调 task_done:q.join() 等了 {ms(t0):.0f} ms 仍未返回({type(e).__name__})')
    c.cancel()
    q3 = asyncio.Queue()
    for i in range(3): q3.put_nowait(i)
    async def c_ok():
        while True:
            await q3.get(); q3.task_done()
    c = asyncio.create_task(c_ok()); t0 = time.perf_counter(); await asyncio.wait_for(q3.join(), 0.5)
    print(f'  每取一个调一次 task_done:q.join() 在 {ms(t0):.1f} ms 内返回'); c.cancel()
asyncio.run(semantics())

print('== 四:三段流水线 抓取 → 解析 → 存储,每段后面一个有界队列(maxsize=5);哪一段最慢,积压就出现在它前面的队列')
async def pipeline(delays):
    q1, q2, q3 = asyncio.Queue(5), asyncio.Queue(5), asyncio.Queue(5)
    N = 100; samples = []; outs = []
    async def stage_fetch():
        for i in range(N): await asyncio.sleep(delays[0] / 1000); await q1.put(i)
        await q1.put(None)
    async def stage_parse():
        while True:
            x = await q1.get()
            if x is None: await q2.put(None); return
            await asyncio.sleep(delays[1] / 1000); await q2.put(x)
    async def stage_store():
        while True:
            x = await q2.get()
            if x is None: return
            await asyncio.sleep(delays[2] / 1000); outs.append(x)
    async def sampler():
        while True:
            samples.append((q1.qsize(), q2.qsize())); await asyncio.sleep(0.005)
    s = asyncio.create_task(sampler()); t0 = time.perf_counter()
    await asyncio.gather(stage_fetch(), stage_parse(), stage_store()); tot = ms(t0); s.cancel()
    m1 = sum(a for a, _ in samples) / len(samples); m2 = sum(b for _, b in samples) / len(samples)
    return tot, m1, m2
print(f'  {"每段耗时(抓取/解析/存储)":<26}{"总耗时":>9}{"理论 = 100×最慢段":>18}{"抓取→解析 队列平均长度":>22}{"解析→存储 队列平均长度":>22}')
for delays in ((2, 2, 2), (2, 10, 2), (2, 2, 10), (10, 2, 2)):
    tot, m1, m2 = asyncio.run(pipeline(delays))
    print(f'  {"/".join(map(str, delays)) + " ms":<26}{tot:>7.0f} ms{100 * max(delays):>16} ms{m1:>22.1f}{m2:>22.1f}')
purge()

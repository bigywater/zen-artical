import sys, os, asyncio, inspect; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
import aiohttp
tee('p22')

print('== 一:wait_for 与 asyncio.timeout:异常类型、耗时、嵌套时谁先触发')
async def work(sec, log=None):
    try:
        await asyncio.sleep(sec)
        if log is not None: log.append('完成')
        return 'ok'
    except asyncio.CancelledError:
        if log is not None: log.append('收到取消')
        raise
async def part1():
    print(f'  asyncio.TimeoutError is TimeoutError:{asyncio.TimeoutError is TimeoutError}(Python {sys.version.split()[0]})')
    log = []; t0 = time.perf_counter()
    try: await asyncio.wait_for(work(1.0, log), 0.2)
    except Exception as e: print(f'  wait_for(work(1.0), 0.2):{type(e).__name__},耗时 {ms(t0):.0f} ms,被取消的协程日志 {log}')
    log = []; t0 = time.perf_counter()
    try:
        async with asyncio.timeout(0.2): await work(1.0, log)
    except Exception as e: print(f'  async with asyncio.timeout(0.2):{type(e).__name__},耗时 {ms(t0):.0f} ms,日志 {log}')
    t0 = time.perf_counter()
    try:
        async with asyncio.timeout(0.3):
            async with asyncio.timeout(1.0): await work(2.0)
    except Exception as e: print(f'  外层 timeout(0.3) 包着内层 timeout(1.0):{type(e).__name__},耗时 {ms(t0):.0f} ms(外层先到期)')
    t0 = time.perf_counter()
    try:
        async with asyncio.timeout(1.0) as cm:
            await asyncio.sleep(0.1); cm.reschedule(asyncio.get_running_loop().time() + 0.2); await work(2.0)
    except Exception as e: print(f'  timeout(1.0) 内部在 0.1 秒时用 reschedule 改成再过 0.2 秒到期:{type(e).__name__},耗时 {ms(t0):.0f} ms')
    cm = asyncio.timeout(1.0)
    async with cm: pass
    print(f'  没超时的 async with:cm.expired() = {cm.expired()}')
    cm = asyncio.timeout(0.05)
    try:
        async with cm: await asyncio.sleep(1)
    except TimeoutError: print(f'  超时的 async with:TimeoutError 抛出,cm.expired() = {cm.expired()}')
asyncio.run(part1())

print('== 二:取消是协作式的:被取消的协程如果吞掉 CancelledError,超时就拦不住它')
async def part2():
    async def swallower():
        try: await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            await asyncio.sleep(1.0)       # 吞掉取消,继续干活
        return 'swallower 结束'
    t0 = time.perf_counter()
    try: r = await asyncio.wait_for(swallower(), 0.2); print(f'  wait_for(swallower(), 0.2) 返回 {r!r},耗时 {ms(t0):.0f} ms(0.2 秒到期,但协程又睡了 1 秒才结束)')
    except Exception as e: print(f'  wait_for(swallower(), 0.2):{type(e).__name__},耗时 {ms(t0):.0f} ms')
    async def good_cleanup():
        try: await asyncio.sleep(1.0)
        finally: await asyncio.sleep(0.1)    # finally 里还有 await:清理也需要时间
    t0 = time.perf_counter()
    try: await asyncio.wait_for(good_cleanup(), 0.2)
    except Exception as e: print(f'  finally 里还有 0.1 秒的清理:wait_for(…, 0.2) 抛 {type(e).__name__},耗时 {ms(t0):.0f} ms(等清理做完才抛)')
asyncio.run(part2())

print('== 三:shield:超时只取消外面的包装,里面的任务继续跑')
async def part3():
    done = []
    async def job():
        await asyncio.sleep(0.5); done.append('job 完成了'); return 42
    t = asyncio.create_task(job()); t0 = time.perf_counter()
    try: await asyncio.wait_for(asyncio.shield(t), 0.1)
    except TimeoutError: print(f'  wait_for(shield(task), 0.1):{ms(t0):.0f} ms 时超时,task.done()={t.done()}')
    await asyncio.sleep(0.6)
    print(f'  再过 0.6 秒:task.done()={t.done()},task.result()={t.result()},done 日志 {done}(任务没被取消,结果还能拿到)')
    done.clear(); t2 = asyncio.create_task(job())
    try: await asyncio.wait_for(t2, 0.1)
    except TimeoutError: pass
    await asyncio.sleep(0.6)
    print(f'  对照:wait_for(task, 0.1)(没有 shield):task.cancelled()={t2.cancelled()},done 日志 {done}')
asyncio.run(part3())

print('== 四:gather 与 TaskGroup:一个任务失败时,其它任务怎么办')
async def part4():
    counter = {'g': 0, 'tg': 0}
    async def ticker(key, n=10):
        for _ in range(n): await asyncio.sleep(0.05); counter[key] += 1
    async def boom(): await asyncio.sleep(0.05); raise ValueError('失败')
    try: await asyncio.gather(boom(), ticker('g'), ticker('g'))
    except ValueError as e: print(f'  gather 抛出 {type(e).__name__} 的时刻:两个 ticker 已计数 {counter["g"]}')
    await asyncio.sleep(0.7)
    print(f'  再过 0.7 秒,两个 ticker 在后台继续跑完:计数 {counter["g"]}(共 20)——gather 抛异常时并没有取消其它任务')
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom()); tg.create_task(ticker('tg')); tg.create_task(ticker('tg'))
    except* ValueError as eg: print(f'  TaskGroup 抛出 ExceptionGroup(含 {[type(x).__name__ for x in eg.exceptions]}),此刻 ticker 计数 {counter["tg"]}')
    await asyncio.sleep(0.7)
    print(f'  再过 0.7 秒:计数 {counter["tg"]}(其它任务已被取消,不再增长)')
asyncio.run(part4())

print('== 五:取消一个进行中的 aiohttp 请求,连接怎么办')
with Srv(lambda h: (time.sleep(0.3), h.reply(200, b'ok'))[1]) as sv:
    async def part5():
        async with aiohttp.ClientSession() as s:
            async with s.get(sv.url('/')) as r: await r.read()
            n1 = sv.n_conn
            async with s.get(sv.url('/')) as r: await r.read()
            n2 = sv.n_conn
            try:
                async with asyncio.timeout(0.1):
                    async with s.get(sv.url('/')) as r: await r.read()
            except TimeoutError: pass
            async with s.get(sv.url('/')) as r: await r.read()
            n3 = sv.n_conn
        print(f'  连续 2 个正常请求累计连接数 {n1} → {n2}(复用);第 3 个请求在 0.1 秒被 asyncio.timeout 取消,之后第 4 个请求累计连接数 {n3}(被取消的请求用的连接被关闭,下一个请求要新建)')
    asyncio.run(part5())
purge()

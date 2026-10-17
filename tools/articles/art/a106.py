import json
from lib import *
txt = out('106').splitlines(); J = json.load(open('out/106.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
rows = J['rows']; log = J['log']
FL = lambda cur, done=(): {'nodes': [['自然运行', '10/10 都对'], ['强制切换点', '10/10 都错'], ['排演交错', '每次都复现'], ['超时', '别卡死 CI'], ['轮询', '不要固定 sleep']], 'cur': cur, 'done': list(done)}
steps = [
    step("同一段「先读余额、再写回」的代码,自然运行 10 次:结果全是 800——测试全绿。但竞态并没有消失,只是线程恰好没有在读和写之间被切走。", fl=FL([0]), kv={'items': [['自然运行 ×10', '[800, 800, 800, …] 全部正确']], 'hl': ['自然运行 ×10']}),
    step("在读和写之间加一个线程让出点(time.sleep(0)):10 次结果是 200 多到 270 多,没有一次等于 800。同样的逻辑,只是给线程切换创造了机会。", fl=FL([1], [0]), kv={'items': [['强制让出 ×10', '228, 269, 240, 249, 238, …'], ['等于 800 的次数', '0']], 'hl': ['等于 800 的次数']}),
    step("更好的办法:用两个 Event 精确排演一种交错。事件 1:线程 A 读到余额 0。", fl=FL([2], [0, 1]), ev={'lines': [log[0]], 'cur': [0]}, kv={'items': [['余额', '0']], 'hl': []}),
    step("事件 2:线程 B 也读到 0(此时 A 还没写)。", fl=FL([2], [0, 1]), ev={'lines': log[:2], 'cur': [1]}, kv={'items': [['余额', '0']], 'hl': []}),
    step("事件 3:B 写入 1。", fl=FL([2], [0, 1]), ev={'lines': log[:3], 'cur': [2]}, kv={'items': [['余额', '1']], 'hl': ['余额']}),
    step("事件 4:A 也写入 1(它手里的「旧值 0」+1)——B 的那次存款被覆盖。两次存款,余额只有 1。这个顺序是我强制的,所以每次运行结果都一样,可以写成稳定的回归测试。", fl=FL([2], [0, 1]), ev={'lines': list(log), 'cur': [3]}, kv={'items': [['余额', '1(期望 2)'], ['加锁后同样两次存款', '2']], 'hl': ['余额']}),
    step("并发测试一定要有超时:消费者线程等一个永远不会来的消息,join(timeout=0.5) 在 0.51 s 后返回、线程仍存活——测试可以据此明确失败,而不是永远挂在那里把 CI 卡死。", fl=FL([3], [0, 1, 2]), kv={'items': [['join(timeout=0.5)', '0.51 s 后返回,is_alive() = True'], ['外部兜底', 'subprocess.run(timeout=1.0) 在 1.01 s 杀掉']], 'hl': ['join(timeout=0.5)']}),
    step("等待后台结果:轮询直到条件成立,比固定 sleep(0.2) 快也更稳。任务需要 20/50/100 ms 时,轮询版等了 %.0f/%.0f/%.0f ms;固定 sleep 版本永远等 200 ms,而且任务变慢到 250 ms 时会失败。" % tuple(r[1] * 1000 for r in rows), fl=FL([4], [0, 1, 2, 3]),
         b={'items': [[f'任务 {int(d*1000)} ms 轮询', w * 1000, f'{w*1000:.0f} ms'] for d, w in rows] + [['固定 sleep(0.2)', 200, '200 ms']], 'max': 200, 'cur': [3]}),
]
A = dict(
    n=106,
    tags='Python,测试,并发,线程,真实验证,动画演示',
    desc='本机真实验证并发测试的稳定性:一段「先读后写」的存款代码自然运行 10 次全部正确(800),加一个线程让出点后 10 次全部错误(200 多);用两个 Event 排演「A 读→B 读→B 写→A 写」每次都稳定复现丢失更新(余额 1,期望 2),加锁后得 2;并用 join(timeout) 和 subprocess 超时避免卡死、用轮询代替固定 sleep(任务 20 ms 时 ' + f'{rows[0][1]*1000:.0f}' + ' ms 通过)。',
    lead='并发 bug 最麻烦的是:测试大多数时候是绿的。这篇不去「祈祷它红」,而是换一套思路——放大竞态、精确排演交错、加超时、别用固定 sleep——每一条都用真实实验证明它有效(以及一条我没能复现的)。',
    facts=[('10/10 vs 0/10', '同一逻辑自然运行全对,加一个让出点后全错'), ('A读 B读 B写 A写', '用两个 Event 排演的交错:每次都稳定复现丢失更新'), (f'{rows[0][1]*1000:.0f} ms vs 200 ms', '后台任务 20 ms 时,轮询版与固定 sleep(0.2) 版测试的等待时间')],
    body=[
        sec('验证一:「绿」的测试不代表没有竞态', '', src('有竞态的存款', '''def deposit_racy(self, n):
    cur = self.balance          # 读
    time.sleep(0)               # 让出一次 GIL: 制造线程切换的机会
    self.balance = cur + n      # 写'''), term('', block('== 一', '== 二')),
            '<p>4 个线程各存 200 次。<b>自然运行</b>(没有让出点,同样的先读后写逻辑)10 次全部是 800,测试全绿;<b>加一个让出点</b>后,10 次结果都是 200 多,没有一次正确。竞态一直在,只是线程恰好没在读写之间被切走。所以「跑了 100 次都通过」并不能证明代码线程安全。(这份代码在自由线程构建里更容易自然出错,见第 91 篇。)</p>'),
        sec('验证二:调小切换间隔——我没能复现', '', term('', block('== 二', '== 三')),
            '<p>一个常听到的技巧是 <code>sys.setswitchinterval(1e-6)</code> 让线程更频繁地切换,以放大竞态。我把它调到 0.001 ms,重复 300 次 <code>box[0] += 1</code>,<b>在这台机器、GIL 版 3.14 上出错次数依然是 0</b>。也就是说这一招不是万能的——结果取决于解释器版本和具体代码。别把它当成可靠的复现手段,要用下面的办法。</p>'),
        sec('验证三:排演一次特定的交错', '', src('用 Event 强制顺序', '''def deposit(name, wait_evt, set_evt):
    cur = a.balance; log.append(f"{name} 读到 {cur}")
    if set_evt: set_evt.set()          # 通知对方: 我读完了
    if wait_evt: wait_evt.wait()       # 等对方写完我再写
    a.balance = cur + 1'''), term('', block('== 三', '== 四')),
            '<p>不靠运气,直接安排「A 读 → B 读 → B 写 → A 写」这个最坏的顺序:两个线程分别在关键点上等待对方发来的 <code>Event</code>。这样两次存款后余额<b>每次都是 1</b>,可以稳定复现,写成回归测试。给同样的存款加上锁之后,同样两次存款得到 2。这种「把线程调度写进测试」的做法需要你知道有问题的交错是哪种,但换来的是确定性。</p>'),
        sec('验证四:超时是并发测试的安全网', '', term('', block('== 四', '== 五')),
            '<p>并发代码最坏的失败方式不是断言失败,而是<b>永远卡住</b>。消费者线程在等一个永远不会到的消息:如果测试用无超时的 <code>join()</code>,整个 CI 就挂了;用 <code>join(timeout=0.5)</code>,0.51 s 后返回,线程仍存活,测试可以据此明确失败。整个进程级别也要有兜底(<code>subprocess.run(timeout=…)</code>,或 pytest 的超时插件)。</p>'),
        sec('验证五:轮询代替固定 sleep', '', term('', block('== 五', 'zzzz')),
            f'<p>要等后台任务完成,常见的写法是 <code>time.sleep(0.2)</code> 再断言。这种写法慢(永远等 200 ms)而且不稳(任务某次多花了 250 ms 就失败)。写一个 <code>eventually(cond, timeout)</code> 轮询:条件一成立就通过——任务需要 20、50、100 ms 时分别只等了约 {rows[0][1]*1000:.0f}、{rows[1][1]*1000:.0f}、{rows[2][1]*1000:.0f} ms;条件永远不成立才走到超时。这样既快,又不会因为机器偶尔慢而失败。</p>'),
        sec('分步演示:从「碰运气」到「确定性」', '交错的四步取自上面排演实验的原始日志',
            demo('并发测试的稳定手段', [('fl', 'flow', '手段'), ('ev', 'term', '排演的事件顺序'), ('kv', 'kv', '观察'), ('b', 'bars', '等待时间(ms)')], steps, '当前手段 / 事件')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7(GIL 版),标准库 <code>threading</code>、<code>queue</code>、<code>subprocess</code>',
          '没有验证:pytest-timeout、pytest-repeat、hypothesis 的并发/状态机测试、asyncio 任务的确定性测试、自由线程版上调小切换间隔的效果'],
)

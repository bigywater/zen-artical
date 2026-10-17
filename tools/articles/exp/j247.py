import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j247'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static final long T0 = System.nanoTime(); static long now() { return (System.nanoTime() - T0) / 1_000_000; }
  static class D implements Delayed { final String name; final long at; final long seq; static final AtomicLong SEQ = new AtomicLong(); final boolean bySeq;
    D(String n, long delayMs, boolean bySeq) { name = n; at = System.nanoTime() + delayMs * 1_000_000; seq = SEQ.incrementAndGet(); this.bySeq = bySeq; }
    public long getDelay(TimeUnit u) { return u.convert(at - System.nanoTime(), TimeUnit.NANOSECONDS); }
    public int compareTo(Delayed o) { D d = (D) o; return bySeq ? Long.compare(seq, d.seq) : Long.compare(at, d.at); } public String toString() { return name; } }
  public static void main(String[] a) throws Exception {
    System.out.println("== 一:语义:poll 与 take 只返回已到期的元素");
    DelayQueue<D> q = new DelayQueue<>(); q.put(new D("c", 600, false)); q.put(new D("a", 200, false)); q.put(new D("b", 400, false));
    System.out.println("  放入 a(200 ms)、b(400 ms)、c(600 ms);t=0:size() = " + q.size() + ",isEmpty() = " + q.isEmpty() + ",peek() = " + q.peek() + "(堆顶是最早到期的),poll() = " + q.poll());
    System.out.println("  iterator 遍历:" + new ArrayList<>(q).stream().map(D::toString).toList() + "(含未到期元素),remainingCapacity() = " + q.remainingCapacity());
    long t0 = System.nanoTime(); D x = q.take(); System.out.println("  take() 返回 " + x + ",等了约 " + (System.nanoTime() - t0) / 1_000_000 + " ms(预期 200)");
    x = q.take(); System.out.println("  再 take() 返回 " + x + ",累计约 " + (System.nanoTime() - t0) / 1_000_000 + " ms(预期 400)");
    Thread.sleep(300); System.out.println("  又睡 300 ms(此时 c 已到期):size() = " + q.size() + ",poll() = " + q.poll() + ",size() = " + q.size());
    System.out.println("== 二:compareTo 与到期时间不一致时的队头阻塞:A(延迟 2000 ms,序号 1)先入队,B(延迟 100 ms,序号 2)后入队,compareTo 按序号比较");
    DelayQueue<D> bad = new DelayQueue<>(); D bA = new D("A", 2000, true), bB = new D("B", 100, true); bad.put(bA); bad.put(bB); Thread.sleep(400);
    System.out.println("  400 ms 后(B 已到期 300 ms):poll() = " + bad.poll() + ",size() = " + bad.size() + ",peek() = " + bad.peek() + ",peek().getDelay = " + bad.peek().getDelay(TimeUnit.MILLISECONDS) + " ms");
    t0 = System.nanoTime(); D got = bad.poll(3000, TimeUnit.MILLISECONDS); System.out.println("  poll(3 s) 返回 " + got + ",等了约 " + (System.nanoTime() - t0) / 1_000_000 + " ms;之后 poll() 取到 " + bad.poll() + ",此时 B 比它的到期时刻晚了约 " + (System.nanoTime() - bB.at) / 1_000_000 + " ms");
    DelayQueue<D> good = new DelayQueue<>(); good.put(new D("A", 2000, false)); good.put(new D("B", 100, false)); Thread.sleep(400); System.out.println("  对照:compareTo 按到期时间比较,400 ms 后 poll() = " + good.poll());
    System.out.println("== 三:到期精度:10,000 个延迟 20 ms 的元素逐个 take(延迟 20 ms 起每 100 个增加 1 ms,以各自的到期时刻为预期)");
    for (String load : new String[]{"空闲", "8 个空转线程"}) { List<Thread> burners = new ArrayList<>(); AtomicBoolean stop = new AtomicBoolean(); if (load.startsWith("8")) for (int i = 0; i < 8; i++) { Thread t = new Thread(() -> { long z = 0; while (!stop.get()) z++; }); t.setDaemon(true); t.start(); burners.add(t); }
      Thread.sleep(200); DelayQueue<D> dq = new DelayQueue<>(); long[] late = new long[10000]; for (int i = 0; i < 10000; i++) dq.put(new D("e" + i, 20 + i / 100, false));
      for (int i = 0; i < 10000; i++) { D d = dq.take(); late[i] = (System.nanoTime() - d.at) / 1000; } stop.set(true); Arrays.sort(late);
      System.out.println("  " + load + ":取到元素时比到期时间晚(微秒)p50 = " + late[5000] + ",p99 = " + late[9900] + ",max = " + late[9999]); }
    System.out.println("== 四:4 个消费者同时 take() 一个 100 ms 后到期的元素,只放入 1 个");
    DelayQueue<D> dq4 = new DelayQueue<>(); AtomicInteger gotc = new AtomicInteger(); List<Thread> cs = new ArrayList<>(); for (int i = 0; i < 4; i++) { Thread c = new Thread(() -> { try { dq4.take(); gotc.incrementAndGet(); } catch (InterruptedException e) { } }); c.setDaemon(true); cs.add(c); c.start(); }
    dq4.put(new D("one", 100, false)); Thread.sleep(500); long waiting = cs.stream().filter(t -> t.getState() == Thread.State.WAITING || t.getState() == Thread.State.TIMED_WAITING).count();
    System.out.println("  500 ms 后:取到元素的消费者 " + gotc.get() + " 个,仍在等待的消费者 " + waiting + " 个");
    System.out.println("== 五:remove(Object) 与取消:从 DelayQueue 里取消(remove)一个元素的成本随队列长度增长");
    for (int n : new int[]{1000, 10000, 100000}) { long per = 0, per2 = 0;
      for (int rep = 0; rep < 3; rep++) { DelayQueue<D> big = new DelayQueue<>(); List<D> els = new ArrayList<>(); for (int i = 0; i < n; i++) { D d = new D("x" + i, 3_600_000 + i, false); els.add(d); big.put(d); } Collections.reverse(els);
        int k = 200; long s = System.nanoTime(); for (int i = 0; i < k; i++) big.remove(els.get(i)); per = (System.nanoTime() - s) / k;
        ScheduledThreadPoolExecutor ex = new ScheduledThreadPoolExecutor(1); ex.setRemoveOnCancelPolicy(true); List<ScheduledFuture<?>> fs = new ArrayList<>(); for (int i = 0; i < n; i++) fs.add(ex.schedule(() -> { }, 3600 + i, TimeUnit.SECONDS)); Collections.reverse(fs);
        s = System.nanoTime(); for (int i = 0; i < k; i++) fs.get(i).cancel(false); per2 = (System.nanoTime() - s) / k; ex.shutdownNow(); }
      System.out.println("  队列里 " + n + " 个元素(取消最晚到期的 200 个,第 3 次重复):DelayQueue.remove 每次约 " + per + " ns;ScheduledThreadPoolExecutor(removeOnCancel)cancel 每次约 " + per2 + " ns"); }
    System.exit(0);
  }
}
'''
r = jrun('j247a', {'Main.java': MAIN}, timeout=600)
if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
print(r['out'])

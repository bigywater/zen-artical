import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j248'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static class Job { final String name; volatile int prio; final long seq; static final AtomicLong S = new AtomicLong(); final long created = System.nanoTime(); Job(String n, int p) { name = n; prio = p; seq = S.incrementAndGet(); } public String toString() { return name + ":" + prio; } }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("main")) {
      System.out.println("== 一:相同优先级不保证先进先出;iterator / toString 不是优先级顺序;不可比较的元素");
      PriorityBlockingQueue<Job> q = new PriorityBlockingQueue<>(11, Comparator.comparingInt((Job j) -> j.prio)); for (int i = 0; i < 12; i++) q.put(new Job("t" + i, 1));
      List<String> order = new ArrayList<>(); Job j; while ((j = q.poll()) != null) order.add(j.name);
      System.out.println("  12 个优先级都是 1 的任务按 t0..t11 入队,出队顺序:" + order + "(是否与入队顺序相同:" + order.equals(List.of("t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11")) + ")");
      PriorityBlockingQueue<Job> q2 = new PriorityBlockingQueue<>(11, Comparator.comparingInt((Job x) -> x.prio).thenComparingLong(x -> x.seq)); for (int i = 0; i < 12; i++) q2.put(new Job("t" + i, 1)); order.clear(); while ((j = q2.poll()) != null) order.add(j.name);
      System.out.println("  加上序号作第二比较键(thenComparingLong(seq)):" + order);
      PriorityBlockingQueue<Integer> q3 = new PriorityBlockingQueue<>(); for (int v : new int[]{9, 3, 7, 1, 8, 2, 6}) q3.put(v); List<Integer> poll = new ArrayList<>(); PriorityBlockingQueue<Integer> copy = new PriorityBlockingQueue<>(q3); while (!copy.isEmpty()) poll.add(copy.poll());
      System.out.println("  依次放入 9 3 7 1 8 2 6:toString() = " + q3 + ";poll 顺序 = " + poll + ";stream 的顺序 = " + q3.stream().toList());
      try { new PriorityBlockingQueue<Object>().put(new Object()); System.out.println("  put(new Object()) 成功"); } catch (Exception e) { System.out.println("  没有比较器时 put(new Object()):" + e.getClass().getSimpleName() + ":" + e.getMessage().replaceAll("\\s+", " ").substring(0, 90) + "…"); }
      System.out.println("== 二:元素入队后改变它的优先级");
      PriorityBlockingQueue<Job> q4 = new PriorityBlockingQueue<>(11, Comparator.comparingInt((Job x) -> x.prio)); Job[] js = new Job[6]; for (int i = 0; i < 6; i++) { js[i] = new Job("j" + i, 10 + i); q4.put(js[i]); }
      js[5].prio = 1; System.out.println("  j0..j5 优先级 10..15;把 j5 的优先级改成 1 之后(没有重新入队):peek() = " + q4.peek() + ",poll 顺序 = " + drain(q4));
      PriorityBlockingQueue<Job> q5 = new PriorityBlockingQueue<>(11, Comparator.comparingInt((Job x) -> x.prio)); Job[] j5 = new Job[6]; for (int i = 0; i < 6; i++) { j5[i] = new Job("j" + i, 10 + i); q5.put(j5[i]); }
      q5.remove(j5[5]); j5[5].prio = 1; q5.put(j5[5]); System.out.println("  先 remove 再改再 put:poll 顺序 = " + drain(q5));
      System.out.println("== 三:低优先级饥饿:持续有高优先级任务到达时,先积压 500 个高优先级任务,之后每毫秒新到 3 个高优先级任务(约 3000 个/秒)、消费者每个处理 0.5 ms(约 2000 个/秒);1 个低优先级任务(prio 100)要等多久");
      for (boolean aging : new boolean[]{false, true}) {
        PriorityBlockingQueue<Job> pq = new PriorityBlockingQueue<>(11, aging ? Comparator.comparingLong((Job x) -> x.created / 1_000_000 * 1 + x.prio * 20L) : Comparator.comparingInt((Job x) -> x.prio));
        AtomicBoolean stop = new AtomicBoolean(); AtomicLong lowWait = new AtomicLong(-1); AtomicLong done = new AtomicLong();
        for (int i = 0; i < 500; i++) pq.put(new Job("hi", 1)); Job low = new Job("low", 100); pq.put(low); long t0 = System.nanoTime();
        Thread prod = new Thread(() -> { try { while (!stop.get()) { for (int k = 0; k < 3; k++) pq.put(new Job("hi", 1)); Thread.sleep(1); } } catch (InterruptedException e) { } });
        Thread cons = new Thread(() -> { try { while (!stop.get()) { Job x = pq.poll(10, TimeUnit.MILLISECONDS); if (x == null) continue; done.incrementAndGet(); if (x == low) { lowWait.set((System.nanoTime() - t0) / 1_000_000); } long e = System.nanoTime() + 500_000; while (System.nanoTime() < e) { } } } catch (InterruptedException e) { } });
        prod.start(); cons.start(); Thread.sleep(3000); stop.set(true); prod.join(); cons.join();
        System.out.println("  " + (aging ? "按“创建时间 + prio × 20 ms”排序(越旧越优先)" : "纯按 prio 排序") + ":3 秒内处理了 " + done.get() + " 个任务;低优先级任务" + (lowWait.get() < 0 ? "3 秒内一直没有被取到,队列里积压 " + pq.size() : "在 " + lowWait.get() + " ms 时被取到")); }
    } else if (mode.equals("oom")) {
      PriorityBlockingQueue<byte[]> q = new PriorityBlockingQueue<>(11, Comparator.comparingInt(b -> b.length)); long n = 0; try { while (true) { q.put(new byte[1024]); n++; } } catch (OutOfMemoryError e) { q.clear(); System.out.println("RES 无界队列 put 持续放入 1 KiB 数组,-Xmx64m 下放入 " + n + " 个(约 " + n / 1024 + " MiB)后 OutOfMemoryError:" + e.getMessage()); }
    } else if (mode.equals("bounded")) {
      Semaphore sem = new Semaphore(1000); PriorityBlockingQueue<byte[]> q = new PriorityBlockingQueue<>(11, Comparator.comparingInt(b -> b.length)); AtomicLong prod = new AtomicLong(), cons = new AtomicLong();
      Thread p = new Thread(() -> { try { while (true) { sem.acquire(); q.put(new byte[1024]); prod.incrementAndGet(); } } catch (InterruptedException e) { } });
      Thread c = new Thread(() -> { try { while (true) { q.take(); sem.release(); cons.incrementAndGet(); Thread.sleep(1); } } catch (InterruptedException e) { } }); p.start(); c.start(); Thread.sleep(2000);
      System.out.println("RES 用 Semaphore(1000) 限界:2 秒内生产 " + prod.get() + ",消费 " + cons.get() + ",队列里 " + q.size() + "(不会超过 1000),无 OOM"); p.interrupt(); c.interrupt();
    }
    System.exit(0);
  }
  static List<String> drain(PriorityBlockingQueue<Job> q) { List<String> r = new ArrayList<>(); Job j; while ((j = q.poll()) != null) r.add(j.toString()); return r; }
}
'''
def run(*args, jopts=()):
    r = jrun('j248a', {'Main.java': MAIN}, args=args, jopts=jopts, clean=False, timeout=180)
    if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
    return r['out']
print(run('main'))
print('== 四:无界队列的代价:生产者远快于消费者(1 KiB 的元素,-Xmx64m)')
print('  ' + run('oom', jopts=('-Xmx64m',)).replace('RES ', ''))
print('  ' + run('bounded', jopts=('-Xmx64m',)).replace('RES ', ''))

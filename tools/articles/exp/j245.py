import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j245'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*; import java.lang.management.*;
public class Main {
  static long ms(long t0) { return (System.nanoTime() - t0) / 1_000_000; }
  public static void main(String[] a) throws Exception {
    System.out.println("== 一:语义:容量 0、offer 立即返回、put 等消费者");
    SynchronousQueue<String> q = new SynchronousQueue<>();
    System.out.println("  remainingCapacity() = " + q.remainingCapacity() + ",size() = " + q.size() + ",isEmpty() = " + q.isEmpty());
    System.out.println("  没有消费者时 offer(\"a\") = " + q.offer("a") + ",poll() = " + q.poll() + ",peek() = " + q.peek());
    long t0 = System.nanoTime(); boolean ok = q.offer("a", 200, TimeUnit.MILLISECONDS); System.out.println("  offer(\"a\", 200 ms) = " + ok + ",耗时约 " + ms(t0) + " ms");
    t0 = System.nanoTime(); String got = q.poll(200, TimeUnit.MILLISECONDS); System.out.println("  poll(200 ms) = " + got + ",耗时约 " + ms(t0) + " ms");
    Thread prod = new Thread(() -> { try { long s = System.nanoTime(); q.put("x"); System.out.println("  生产者 put(\"x\") 在 " + ms(s) + " ms 后返回"); } catch (InterruptedException e) { } }); prod.start();
    Thread.sleep(300); System.out.println("  生产者已阻塞 300 ms:size() = " + q.size() + ",peek() = " + q.peek() + ",iterator().hasNext() = " + q.iterator().hasNext() + ",线程状态 " + prod.getState());
    String x = q.take(); prod.join(); System.out.println("  消费者 take() 取到 " + x);
    System.out.println("  消费者还没来时 offer(\"direct\") = " + q.offer("direct"));
    Thread waitingCons = new Thread(() -> { try { q.take(); } catch (InterruptedException e) { } }); waitingCons.start(); Thread.sleep(100);
    System.out.println("  已有消费者在 take() 等待时 offer(\"y\") = " + q.offer("y")); waitingCons.join();
    System.out.println("== 二:Executors.newCachedThreadPool 用 SynchronousQueue:任务数与线程数,以及有上限的池");
    ThreadPoolExecutor cached = (ThreadPoolExecutor) Executors.newCachedThreadPool(); CountDownLatch go = new CountDownLatch(1);
    for (int i = 0; i < 50; i++) cached.execute(() -> { try { go.await(); } catch (InterruptedException e) { } });
    Thread.sleep(200); System.out.println("  50 个阻塞任务同时提交:池里线程数 " + cached.getPoolSize() + ",队列元素数 " + cached.getQueue().size() + ",队列类型 " + cached.getQueue().getClass().getSimpleName());
    go.countDown(); Thread.sleep(300); int idle = cached.getPoolSize(); System.out.println("  任务结束后空闲线程仍有 " + idle + " 个(60 秒内不回收)");
    cached.shutdown();
    ThreadPoolExecutor bounded = new ThreadPoolExecutor(2, 4, 1, TimeUnit.SECONDS, new SynchronousQueue<>()); CountDownLatch go2 = new CountDownLatch(1); int acc = 0, rej = 0; String firstRej = null;
    for (int i = 0; i < 10; i++) { try { bounded.execute(() -> { try { go2.await(); } catch (InterruptedException e) { } }); acc++; } catch (RejectedExecutionException e) { rej++; if (firstRej == null) firstRej = "第 " + (i + 1) + " 个任务被拒绝"; } }
    System.out.println("  ThreadPoolExecutor(2, 4, SynchronousQueue):连续提交 10 个阻塞任务,接受 " + acc + " 个、拒绝 " + rej + " 个(" + firstRej + ")");
    go2.countDown(); bounded.shutdown();
    System.out.println("== 三:公平与非公平:5 个生产者依次(间隔 100 ms)put 并阻塞,之后消费者逐个 take,看取到的顺序");
    for (boolean fair : new boolean[]{true, false}) { SynchronousQueue<Integer> sq = new SynchronousQueue<>(fair); List<Thread> ps = new ArrayList<>();
      for (int i = 1; i <= 5; i++) { int k = i; Thread t = new Thread(() -> { try { sq.put(k); } catch (InterruptedException e) { } }); ps.add(t); t.start(); Thread.sleep(100); }
      List<Integer> order = new ArrayList<>(); for (int i = 0; i < 5; i++) order.add(sq.take()); for (Thread t : ps) t.join();
      System.out.println("  fair = " + fair + ":先后到达的生产者 1..5 被取走的顺序 " + order); }
    System.out.println("== 四:交接成本:1 个生产者 + 1 个消费者,各传 2,000,000 个对象(取 5 轮中位数,不是 JMH)");
    Map<String, BlockingQueue<Integer>> qs = new LinkedHashMap<>(); qs.put("SynchronousQueue", new SynchronousQueue<>()); qs.put("SynchronousQueue(fair)", new SynchronousQueue<>(true)); qs.put("ArrayBlockingQueue(1)", new ArrayBlockingQueue<>(1)); qs.put("ArrayBlockingQueue(1024)", new ArrayBlockingQueue<>(1024)); qs.put("LinkedBlockingQueue", new LinkedBlockingQueue<>());
    int N = 2_000_000;
    for (var e : qs.entrySet()) { long[] r = new long[5]; for (int rr = 0; rr < 5; rr++) { BlockingQueue<Integer> bq = e.getKey().contains("fair") ? new SynchronousQueue<>(true) : e.getKey().equals("SynchronousQueue") ? new SynchronousQueue<>() : e.getKey().equals("ArrayBlockingQueue(1)") ? new ArrayBlockingQueue<>(1) : e.getKey().equals("ArrayBlockingQueue(1024)") ? new ArrayBlockingQueue<>(1024) : new LinkedBlockingQueue<>();
        long s = System.nanoTime(); Thread p = new Thread(() -> { try { for (int i = 0; i < N; i++) bq.put(i); } catch (InterruptedException ex) { } }); p.start(); long sum = 0; for (int i = 0; i < N; i++) sum += bq.take(); p.join(); r[rr] = System.nanoTime() - s; }
      Arrays.sort(r); System.out.printf("  %-26s 每个对象约 %.0f ns(中位数,共 %d ms)%n", e.getKey(), r[2] / (double) N, r[2] / 1_000_000); }
    System.exit(0);
  }
}
'''
r = jrun('j245a', {'Main.java': MAIN}, timeout=300)
if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
print(r['out'])

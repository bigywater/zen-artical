import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j246'); R = {}
MAIN = r'''
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static long ms(long t0) { return (System.nanoTime() - t0) / 1_000_000; }
  public static void main(String[] a) throws Exception {
    System.out.println("== 一:transfer / tryTransfer / put 的语义(没有消费者在等时)");
    LinkedTransferQueue<String> q = new LinkedTransferQueue<>();
    System.out.println("  tryTransfer(\"a\"):" + q.tryTransfer("a") + ";之后 size() = " + q.size() + "(没有消费者,元素没有入队)");
    long t0 = System.nanoTime(); boolean r = q.tryTransfer("b", 200, TimeUnit.MILLISECONDS); System.out.println("  tryTransfer(\"b\", 200 ms):" + r + ",耗时约 " + ms(t0) + " ms;之后 size() = " + q.size() + "(超时后元素被移除)");
    q.put("c"); System.out.println("  put(\"c\") 立即返回;size() = " + q.size() + ",hasWaitingConsumer() = " + q.hasWaitingConsumer()); System.out.println("  poll() = " + q.poll());
    Thread tr = new Thread(() -> { try { long s = System.nanoTime(); q.transfer("d"); System.out.println("  生产者 transfer(\"d\") 在 " + ms(s) + " ms 后返回"); } catch (InterruptedException e) { } }); tr.start(); Thread.sleep(300);
    System.out.println("  transfer(\"d\") 阻塞 300 ms 期间:size() = " + q.size() + ",peek() = " + q.peek() + ",线程状态 " + tr.getState()); System.out.println("  take() = " + q.take()); tr.join();
    Thread cw = new Thread(() -> { try { q.take(); } catch (InterruptedException e) { } }); cw.start(); Thread.sleep(100);
    System.out.println("  一个消费者在 take() 等待时:hasWaitingConsumer() = " + q.hasWaitingConsumer() + ",getWaitingConsumerCount() = " + q.getWaitingConsumerCount() + ";tryTransfer(\"e\") = " + q.tryTransfer("e")); cw.join();
    System.out.println("== 二:队列里已有 3 个元素时 transfer 要等到哪一个被取走");
    LinkedTransferQueue<Integer> q2 = new LinkedTransferQueue<>(); q2.put(1); q2.put(2); q2.put(3); AtomicLong back = new AtomicLong();
    Thread t2 = new Thread(() -> { try { long s = System.nanoTime(); q2.transfer(99); back.set(ms(s)); } catch (InterruptedException e) { } }); t2.start(); Thread.sleep(100);
    System.out.println("  队列里 [1, 2, 3],另一个线程 transfer(99) 已等待 100 ms:size() = " + q2.size() + "(99 在队尾," + new ArrayList<>(q2) + ")");
    for (int i = 0; i < 3; i++) { Thread.sleep(100); System.out.println("  " + (i + 1) + " 个元素被取走后(+" + (i + 1) * 100 + " ms):取到 " + q2.take() + ",transfer 线程状态 " + t2.getState()); }
    Thread.sleep(100); System.out.println("  取走 99 之前 transfer 线程状态 " + t2.getState() + ";取走 99:" + q2.take()); t2.join(); System.out.println("  transfer(99) 总共等了约 " + back.get() + " ms(= 排在前面的 3 个元素被取走 + 99 本身被取走)");
    System.out.println("== 三:消费者很慢(每个 1 ms)时,生产者 1 秒内生产了多少:put、transfer、有界的 ArrayBlockingQueue(100) put");
    for (String mode : new String[]{"LinkedTransferQueue.put", "LinkedTransferQueue.transfer", "ArrayBlockingQueue(100).put"}) {
      BlockingQueue<Integer> bq = mode.startsWith("Array") ? new ArrayBlockingQueue<>(100) : new LinkedTransferQueue<>(); AtomicLong produced = new AtomicLong(), consumed = new AtomicLong(); AtomicBoolean stop = new AtomicBoolean();
      Thread c = new Thread(() -> { try { while (!stop.get()) { Integer v = bq.poll(50, TimeUnit.MILLISECONDS); if (v != null) { consumed.incrementAndGet(); Thread.sleep(1); } } } catch (InterruptedException e) { } });
      Thread p = new Thread(() -> { try { int i = 0; while (!stop.get()) { if (mode.endsWith("transfer")) ((LinkedTransferQueue<Integer>) bq).transfer(i++); else bq.put(i++); produced.incrementAndGet(); } } catch (InterruptedException e) { } });
      c.start(); p.start(); Thread.sleep(1000); long pr = produced.get(), co = consumed.get(), sz = bq.size(); stop.set(true); p.interrupt(); c.join(); p.join();
      System.out.println("  " + String.format("%-30s", mode) + " 1 秒内生产 " + pr + ",消费 " + co + ",队列里积压 " + sz); }
    System.out.println("== 四:size() 的代价与容量");
    for (int n : new int[]{1000, 100000, 1000000}) { LinkedTransferQueue<Integer> big = new LinkedTransferQueue<>(); for (int i = 0; i < n; i++) big.put(i); long best = Long.MAX_VALUE; int s = 0; for (int k = 0; k < 20; k++) { long x = System.nanoTime(); s = big.size(); best = Math.min(best, System.nanoTime() - x); }
      LinkedBlockingQueue<Integer> lb = new LinkedBlockingQueue<>(); for (int i = 0; i < n; i++) lb.put(i); long best2 = Long.MAX_VALUE; for (int k = 0; k < 20; k++) { long x = System.nanoTime(); lb.size(); best2 = Math.min(best2, System.nanoTime() - x); }
      System.out.println("  " + n + " 个元素:LinkedTransferQueue.size() 最快一次约 " + best / 1000 + " µs,LinkedBlockingQueue.size() 约 " + best2 + " ns"); }
    System.out.println("  LinkedTransferQueue.remainingCapacity() = " + new LinkedTransferQueue<Integer>().remainingCapacity() + "(没有容量上限)");
    System.out.println("== 五:吞吐:N 个生产者 + N 个消费者共传 4,000,000 个对象(取 5 轮中位数,不是 JMH)");
    int TOTAL = 4_000_000;
    for (int pairs : new int[]{1, 4}) for (String name : new String[]{"LinkedTransferQueue", "LinkedBlockingQueue", "ConcurrentLinkedQueue(自旋)"}) {
      long[] rr = new long[5]; for (int rd = 0; rd < 5; rd++) { Queue<Integer> qq = name.startsWith("LinkedTransfer") ? new LinkedTransferQueue<>() : name.startsWith("LinkedBlocking") ? new LinkedBlockingQueue<>() : new ConcurrentLinkedQueue<>(); BlockingQueue<Integer> bq = qq instanceof BlockingQueue ? (BlockingQueue<Integer>) qq : null;
        int per = TOTAL / pairs; AtomicLong got = new AtomicLong(); List<Thread> ts = new ArrayList<>(); long s = System.nanoTime();
        for (int k = 0; k < pairs; k++) { ts.add(new Thread(() -> { try { for (int i = 0; i < per; i++) { if (bq != null) bq.put(i); else qq.add(i); } } catch (InterruptedException e) { } }));
          ts.add(new Thread(() -> { try { for (int i = 0; i < per; i++) { if (bq != null) bq.take(); else { while (qq.poll() == null) Thread.onSpinWait(); } } } catch (InterruptedException e) { } })); }
        for (Thread t : ts) t.start(); for (Thread t : ts) t.join(); rr[rd] = System.nanoTime() - s; }
      Arrays.sort(rr); System.out.printf("  %d 对 %-28s 每个对象约 %.0f ns(中位数,共 %d ms)%n", pairs, name, rr[2] / (double) TOTAL, rr[2] / 1_000_000); }
    System.exit(0);
  }
}
'''
r = jrun('j246a', {'Main.java': MAIN}, timeout=600)
if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
print(r['out'])

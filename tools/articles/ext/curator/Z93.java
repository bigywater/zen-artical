import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.locks.*;
import org.apache.curator.retry.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class Z93 {
    static CuratorFramework mk() { CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:7300").sessionTimeoutMs(3000).retryPolicy(new ExponentialBackoffRetry(100, 5)).build(); c.start(); return c; }
    public static void main(String[] a) throws Exception {
        CuratorFramework c = mk(); c.blockUntilConnected();
        System.out.println("== 一:互斥:10 个线程(各有一个客户端)各做 20 次「读计数器 → 加 1 → 写回」,共 200 次;InterProcessMutex");
        c.create().forPath("/counter", "0".getBytes());
        long t = System.nanoTime(); List<Thread> ths = new ArrayList<>(); List<CuratorFramework> cls = new ArrayList<>();
        for (int i = 0; i < 10; i++) { final CuratorFramework ci = mk(); cls.add(ci); Thread th = new Thread(() -> { try { InterProcessMutex m = new InterProcessMutex(ci, "/lock"); for (int k = 0; k < 20; k++) { m.acquire(); try { int v = Integer.parseInt(new String(ci.getData().forPath("/counter"))); ci.setData().forPath("/counter", String.valueOf(v + 1).getBytes()); } finally { m.release(); } } } catch (Exception e) { e.printStackTrace(); } }); ths.add(th); th.start(); }
        for (Thread th : ths) th.join();
        System.out.printf("  最终 %s / 200,用时 %.1f s%n", new String(c.getData().forPath("/counter")), (System.nanoTime() - t) / 1e9);
        for (CuratorFramework x : cls) x.close();
        System.out.println();
        System.out.println("== 二:可重入:同一线程两次 acquire(InterProcessMutex)与 InterProcessSemaphoreMutex(不可重入)");
        InterProcessMutex m = new InterProcessMutex(c, "/re"); m.acquire(); m.acquire();
        System.out.println("  InterProcessMutex 同线程第二次 acquire 成功;/re 下的锁节点:" + c.getChildren().forPath("/re") + "(只有 1 个节点,本地计数)");
        m.release(); System.out.println("  release 一次后 /re 下还有 " + c.getChildren().forPath("/re").size() + " 个节点(还没释放完)"); m.release(); System.out.println("  release 第二次后 /re 下有 " + c.getChildren().forPath("/re").size() + " 个节点");
        InterProcessSemaphoreMutex sm = new InterProcessSemaphoreMutex(c, "/nre"); sm.acquire(); long t2 = System.nanoTime(); boolean ok = sm.acquire(1, TimeUnit.SECONDS);
        System.out.printf("  InterProcessSemaphoreMutex 同线程第二次 acquire(1 s) → %s,等了 %.1f s(自己把自己锁住了)%n", ok, (System.nanoTime() - t2) / 1e9); sm.release();
        try { m.release(); } catch (IllegalMonitorStateException e) { System.out.println("  多 release 一次 → " + e.getClass().getSimpleName()); }
        System.out.println();
        System.out.println("== 三:获取超时:A 持有锁,B 在另一个客户端 acquire(1, SECONDS)");
        CuratorFramework c2 = mk(); InterProcessMutex ma = new InterProcessMutex(c, "/to"), mb = new InterProcessMutex(c2, "/to"); ma.acquire();
        long t3 = System.nanoTime(); boolean got = mb.acquire(1, TimeUnit.SECONDS); System.out.printf("  B.acquire(1 s) → %s,%.2f s 后返回;/to 下的节点数 = %d(B 超时后自己的排队节点已清理)%n", got, (System.nanoTime() - t3) / 1e9, c.getChildren().forPath("/to").size());
        System.out.println("  锁节点名:" + c.getChildren().forPath("/to")); ma.release(); c2.close();
        System.out.println();
        System.out.println("== 四:读写锁 InterProcessReadWriteLock:5 个读者同时持有;写者等待;写者排队后到达的新读者是否插队");
        CuratorFramework[] rc = new CuratorFramework[7]; for (int i = 0; i < 7; i++) rc[i] = mk();
        AtomicInteger cur = new AtomicInteger(), max = new AtomicInteger(); List<String> ev = Collections.synchronizedList(new ArrayList<>()); long T0 = System.nanoTime();
        CountDownLatch inside = new CountDownLatch(5); List<Thread> rs = new ArrayList<>();
        for (int i = 0; i < 5; i++) { final int id = i; Thread th = new Thread(() -> { try { InterProcessReadWriteLock rw = new InterProcessReadWriteLock(rc[id], "/rw"); rw.readLock().acquire(); int n = cur.incrementAndGet(); max.accumulateAndGet(n, Math::max); inside.countDown(); Thread.sleep(1500); cur.decrementAndGet(); rw.readLock().release(); } catch (Exception e) { e.printStackTrace(); } }); rs.add(th); th.start(); }
        inside.await(); ev.add(String.format("%.1fs 5 个读者都已持有读锁(同时在内的最大数 %d)", (System.nanoTime() - T0) / 1e9, max.get()));
        Thread w = new Thread(() -> { try { InterProcessReadWriteLock rw = new InterProcessReadWriteLock(rc[5], "/rw"); rw.writeLock().acquire(); ev.add(String.format("%.1fs 写者拿到写锁(此时读者数 %d)", (System.nanoTime() - T0) / 1e9, cur.get())); Thread.sleep(500); rw.writeLock().release(); } catch (Exception e) { e.printStackTrace(); } });
        Thread.sleep(200); w.start(); Thread.sleep(300);
        Thread late = new Thread(() -> { try { InterProcessReadWriteLock rw = new InterProcessReadWriteLock(rc[6], "/rw"); long s = System.nanoTime(); rw.readLock().acquire(); ev.add(String.format("%.1fs 写者之后到达的读者拿到读锁(等了 %.1f s)", (System.nanoTime() - T0) / 1e9, (System.nanoTime() - s) / 1e9)); rw.readLock().release(); } catch (Exception e) { e.printStackTrace(); } });
        late.start(); for (Thread th : rs) th.join(); w.join(); late.join();
        for (String s : ev) System.out.println("  " + s);
        for (CuratorFramework x : rc) x.close(); c.close(); System.exit(0);
    }
}

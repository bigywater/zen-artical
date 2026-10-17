import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.atomic.*;
import org.apache.curator.retry.*;
import org.apache.curator.RetryPolicy;
import org.apache.zookeeper.CreateMode;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class Z96 {
    static CuratorFramework mk() { CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:7300").sessionTimeoutMs(6000).retryPolicy(new RetryNTimes(0, 0)).build(); c.start(); return c; }
    static int[] run(String path, int threads, int per, RetryPolicy rp, PromotedToLock pl) throws Exception {
        List<CuratorFramework> cs = new ArrayList<>(); AtomicInteger ok = new AtomicInteger(), fail = new AtomicInteger(); List<Thread> ths = new ArrayList<>();
        for (int i = 0; i < threads; i++) { CuratorFramework c = mk(); cs.add(c); DistributedAtomicLong d = pl == null ? new DistributedAtomicLong(c, path, rp) : new DistributedAtomicLong(c, path, rp, pl);
            Thread th = new Thread(() -> { try { for (int k = 0; k < per; k++) { AtomicValue<Long> v = d.increment(); if (v.succeeded()) ok.incrementAndGet(); else fail.incrementAndGet(); } } catch (Exception e) { e.printStackTrace(); } }); ths.add(th); th.start(); }
        for (Thread th : ths) th.join();
        CuratorFramework c = cs.get(0); long fin = new DistributedAtomicLong(c, path, rp).get().postValue(); for (CuratorFramework x : cs) x.close();
        return new int[]{ok.get(), fail.get(), (int) fin};
    }
    public static void main(String[] a) throws Exception {
        System.out.println("== 一:DistributedAtomicLong(默认乐观方式 + ExponentialBackoffRetry):10 线程各 increment() 100 次,期望 1000");
        long t = System.nanoTime(); int[] r = run("/al1", 10, 100, new ExponentialBackoffRetry(5, 50), null);
        System.out.printf("  succeeded()=true %d 次,false %d 次;最终值 %d;用时 %.1f s%n", r[0], r[1], r[2], (System.nanoTime() - t) / 1e9);
        System.out.println();
        System.out.println("== 二:重试次数用完:同样 10 线程 × 100 次,但重试策略只允许重试 1 次(RetryNTimes(1, 0))");
        t = System.nanoTime(); r = run("/al2", 10, 100, new RetryNTimes(1, 0), null);
        System.out.printf("  succeeded()=true %d 次,false %d 次;最终值 %d(= 成功次数,失败的 increment 没有被计入,也没有抛异常);用时 %.1f s%n", r[0], r[1], r[2], (System.nanoTime() - t) / 1e9);
        System.out.println();
        System.out.println("== 三:PromotedToLock:乐观失败后升级为用分布式锁串行执行,保证成功");
        t = System.nanoTime(); r = run("/al3", 10, 100, new RetryNTimes(1, 0), PromotedToLock.builder().lockPath("/al3-lock").retryPolicy(new ExponentialBackoffRetry(5, 50)).build());
        System.out.printf("  succeeded()=true %d 次,false %d 次;最终值 %d;用时 %.1f s%n", r[0], r[1], r[2], (System.nanoTime() - t) / 1e9);
        System.out.println();
        System.out.println("== 四:线程数 1 / 2 / 5 / 10 时的吞吐(PromotedToLock 关闭,ExponentialBackoffRetry(5, 50),每线程 100 次)");
        for (int th : new int[]{1, 2, 5, 10}) { t = System.nanoTime(); r = run("/alt" + th, th, 100, new ExponentialBackoffRetry(5, 50), null); double s = (System.nanoTime() - t) / 1e9; System.out.printf("  %2d 线程:%.0f 次/s(成功 %d / %d)%n", th, r[0] / s, r[0], th * 100); }
        System.out.println();
        System.out.println("== 五:用顺序节点做 ID 发号:10 线程各创建 100 个 PERSISTENT_SEQUENTIAL 节点(创建后立刻删除),序号是否唯一");
        CuratorFramework c = mk(); c.blockUntilConnected(); c.create().forPath("/ids"); Set<String> seen = ConcurrentHashMap.newKeySet(); List<Thread> ths = new ArrayList<>(); List<CuratorFramework> cs = new ArrayList<>(); t = System.nanoTime();
        for (int i = 0; i < 10; i++) { CuratorFramework ci = mk(); cs.add(ci); Thread th = new Thread(() -> { try { for (int k = 0; k < 100; k++) { String p = ci.create().withMode(CreateMode.PERSISTENT_SEQUENTIAL).forPath("/ids/n-"); seen.add(p); ci.delete().forPath(p); } } catch (Exception e) { e.printStackTrace(); } }); ths.add(th); th.start(); }
        for (Thread th : ths) th.join(); double s = (System.nanoTime() - t) / 1e9;
        System.out.printf("  1000 个序号中不同的 %d 个;用时 %.1f s(%.0f 个/s,含每个一次删除);最大序号 %s%n", seen.size(), s, 1000 / s, seen.stream().max(String::compareTo).get());
        for (CuratorFramework x : cs) x.close(); c.close(); System.exit(0);
    }
}

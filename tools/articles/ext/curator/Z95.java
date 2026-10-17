import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.cache.*;
import org.apache.curator.retry.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class Z95 {
    static CuratorFramework mk() { CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:7300").sessionTimeoutMs(6000).retryPolicy(new ExponentialBackoffRetry(100, 5)).build(); c.start(); return c; }
    public static void main(String[] a) throws Exception {
        CuratorFramework c = mk(); c.blockUntilConnected(); CuratorFramework w = mk(); w.blockUntilConnected();
        System.out.println("== 一:CuratorCache 初始加载:/tree 下 1000 个 1 KiB 的节点,建缓存到 initialized 的时间;之后读缓存 vs 读 ZooKeeper 的耗时");
        c.create().forPath("/tree"); byte[] kb = new byte[1024];
        List<CompletableFuture<Void>> fs = new ArrayList<>();
        for (int i = 0; i < 1000; i++) { CompletableFuture<Void> f = new CompletableFuture<>(); w.create().inBackground((cf, ev) -> f.complete(null)).forPath("/tree/n" + i, kb); fs.add(f); }
        for (CompletableFuture<Void> f : fs) f.get();
        CuratorCache cache = CuratorCache.build(c, "/tree"); CountDownLatch init = new CountDownLatch(1); long t = System.nanoTime();
        cache.listenable().addListener(CuratorCacheListener.builder().forInitialized(() -> init.countDown()).build()); cache.start(); init.await();
        System.out.printf("  建缓存并加载完成:%.0f ms;缓存里的节点数 %d(含 /tree 自己)%n", (System.nanoTime() - t) / 1e6, cache.size());
        long t1 = System.nanoTime(); for (int i = 0; i < 100000; i++) cache.get("/tree/n" + (i % 1000)); double cm = (System.nanoTime() - t1) / 1e3 / 100000;
        t1 = System.nanoTime(); for (int i = 0; i < 2000; i++) c.getData().forPath("/tree/n" + (i % 1000)); double zm = (System.nanoTime() - t1) / 1e3 / 2000;
        System.out.printf("  读一个节点:缓存 %.2f µs,直接读 ZooKeeper %.0f µs(约 %.0f 倍)%n", cm, zm, zm / cm);
        System.out.println();
        System.out.println("== 二:事件:改 / 建 / 删一个节点,监听器收到的事件类型与延迟;连续快速改 200 次,监听器收到多少次 CHANGED");
        BlockingQueue<String> q = new LinkedBlockingQueue<>(); AtomicLong ts = new AtomicLong();
        cache.listenable().addListener((type, old, nw) -> { q.add(type + "@" + (System.nanoTime() - ts.get()) / 1000); });
        Thread.sleep(300); q.clear();
        for (String op : new String[]{"建", "改", "删"}) {
            ts.set(System.nanoTime()); if (op.equals("建")) w.create().forPath("/tree/new", "1".getBytes()); else if (op.equals("改")) w.setData().forPath("/tree/new", "2".getBytes()); else w.delete().forPath("/tree/new");
            String ev = q.poll(3, TimeUnit.SECONDS); System.out.println("  " + op + " → " + ev.split("@")[0] + ",延迟 " + String.format("%.1f", Long.parseLong(ev.split("@")[1]) / 1000.0) + " ms");
        }
        Thread.sleep(300); q.clear(); w.create().forPath("/tree/hot", "0".getBytes()); Thread.sleep(300); q.clear();
        for (int i = 0; i < 200; i++) w.setData().forPath("/tree/hot", ("v" + i).getBytes());
        Thread.sleep(1500); int changed = 0; for (String s : q) if (s.startsWith("NODE_CHANGED")) changed++;
        System.out.println("  快速 setData 200 次(同步连续):监听器收到 NODE_CHANGED " + changed + " 次;缓存里最终值 = " + new String(cache.get("/tree/hot").get().getData()));
        cache.close(); c.close(); w.close(); System.exit(0);
    }
}

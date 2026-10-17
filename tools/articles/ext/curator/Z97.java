import org.apache.curator.framework.*;
import org.apache.curator.retry.*;
import org.apache.curator.*;
import java.util.*;
import java.util.concurrent.*;
import java.io.*;

public class Z97 {
    static class Log implements RetryPolicy {
        final RetryPolicy d; final Map<String, List<String>> ev = new LinkedHashMap<>(); synchronized void add(String m) { ev.computeIfAbsent(Thread.currentThread().getName().replaceAll("-\\d+$", ""), k -> new ArrayList<>()).add(m); } long t0 = System.nanoTime(); Log(RetryPolicy d) { this.d = d; }
        public boolean allowRetry(int n, long elapsed, RetrySleeper s) {
            boolean r = d.allowRetry(n, elapsed, (t, u) -> { add(String.format("%d ms", u.toMillis(t))); s.sleepFor(t, u); }); if (!r) add("放弃"); return r; }
        public boolean allowRetry(Throwable e, int n, long elapsed, RetrySleeper s) { return allowRetry(n, elapsed, s); }
    }
    static CuratorFramework mk(String port, RetryPolicy rp) { CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:" + port).sessionTimeoutMs(6000).connectionTimeoutMs(500).retryPolicy(rp).build(); c.start(); return c; }
    public static void main(String[] a) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        System.out.println("== 一:服务端不可用(端口上没有服务)时,不同重试策略的行为:getData() 在放弃前尝试了几次、睡了多久、总共花多久");
        Object[][] ps = {{"RetryOneTime(500)", new RetryOneTime(500)}, {"RetryNTimes(3, 200)", new RetryNTimes(3, 200)}, {"ExponentialBackoffRetry(100, 5)", new ExponentialBackoffRetry(100, 5)}, {"ExponentialBackoffRetry(100, 5, maxSleep=300)", new ExponentialBackoffRetry(100, 5, 300)}, {"BoundedExponentialBackoffRetry(100, 800, 6)", new BoundedExponentialBackoffRetry(100, 800, 6)}, {"RetryUntilElapsed(2000, 300)", new RetryUntilElapsed(2000, 300)}};
        for (Object[] p : ps) {
            Log lg = new Log((RetryPolicy) p[1]); CuratorFramework c = mk("7399", lg); long t = System.nanoTime(); String r;
            try { c.getData().forPath("/x"); r = "成功"; } catch (Exception e) { r = e.getClass().getSimpleName(); }
            double el = (System.nanoTime() - t) / 1e9; System.out.printf("  %-46s → %s,共 %.1f s;各线程里 allowRetry 的睡眠序列 %s%n", p[0], r, el, lg.ev); c.close();
        }
        System.out.println();
        System.out.println("== 二:服务端重启(停止后约 1.5 s 重新启动,实际不可用约 2.5–3 s)期间发起一次 setData,不同重试策略能否成功");
        Object[][] ps2 = {{"RetryNTimes(1, 100)", new RetryNTimes(1, 100)}, {"RetryNTimes(5, 200)", new RetryNTimes(5, 200)}, {"ExponentialBackoffRetry(100, 5)", new ExponentialBackoffRetry(100, 5)}, {"RetryUntilElapsed(10000, 200)", new RetryUntilElapsed(10000, 200)}};
        CuratorFramework adm = mk("7300", new RetryNTimes(10, 500)); adm.blockUntilConnected(); try { adm.create().forPath("/k", "0".getBytes()); } catch (Exception e) {}
        for (Object[] p : ps2) {
            CuratorFramework c = mk("7300", (RetryPolicy) p[1]); c.blockUntilConnected(); c.setData().forPath("/k", "warm".getBytes());
            System.out.println("STOP_ZK"); System.out.flush(); in.readLine();
            long t = System.nanoTime(); String r; try { c.setData().forPath("/k", "x".getBytes()); r = "成功"; } catch (Exception e) { r = e.getClass().getSimpleName(); }
            double el = (System.nanoTime() - t) / 1e9; System.out.printf("  %-34s → %s,发起后 %.1f s 返回%n", p[0], r, el); System.out.println("DONE_ONE"); System.out.flush(); in.readLine(); c.close();
        }
        adm.close(); System.exit(0);
    }
}

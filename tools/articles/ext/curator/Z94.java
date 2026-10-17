import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.leader.*;
import org.apache.curator.retry.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class Z94 {
    static CuratorFramework mk(int st) { CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:7300").sessionTimeoutMs(st).retryPolicy(new ExponentialBackoffRetry(100, 5)).build(); c.start(); return c; }
    static String leader(List<LeaderLatch> ls) { for (LeaderLatch l : ls) if (l.hasLeadership()) return l.getId(); return null; }
    public static void main(String[] a) throws Exception {
        String pid = a[0];
        System.out.println("== 一:5 个 LeaderLatch 候选(同一 JVM,各自一个客户端):谁是 leader,依次 close() 当前 leader,新 leader 出现的时间");
        List<CuratorFramework> cls = new ArrayList<>(); List<LeaderLatch> ls = new ArrayList<>();
        for (int i = 0; i < 5; i++) { CuratorFramework c = mk(6000); cls.add(c); LeaderLatch l = new LeaderLatch(c, "/latch1", "C" + i); l.start(); ls.add(l); Thread.sleep(100); }
        Thread.sleep(500); System.out.println("  启动后 leader = " + leader(ls) + ";hasLeadership 为 true 的候选数 = " + ls.stream().filter(LeaderLatch::hasLeadership).count() + ";getParticipants = " + ls.get(0).getParticipants().stream().map(p -> p.getId() + (p.isLeader() ? "*" : "")).toList());
        List<Double> gaps = new ArrayList<>(); List<LeaderLatch> alive = new ArrayList<>(ls);
        for (int k = 0; k < 4; k++) {
            String cur = leader(alive); LeaderLatch lc = alive.stream().filter(x -> x.getId().equals(cur)).findFirst().get(); long t = System.nanoTime(); lc.close(); alive.remove(lc);
            String nl = null; while (nl == null && (System.nanoTime() - t) / 1e9 < 10) { nl = leader(alive); Thread.sleep(1); }
            double g = (System.nanoTime() - t) / 1e6; gaps.add(g); System.out.printf("  close() %s → 新 leader %s,%.0f ms%n", cur, nl, g);
        }
        for (LeaderLatch l : alive) l.close(); for (CuratorFramework c : cls) c.close();
        System.out.println();
        System.out.println("== 二:服务端被冻结 5 s(会话超时 6 s),单个 LeaderLatch 的 isLeader / notLeader 回调与 hasLeadership 的变化");
        CuratorFramework c = mk(6000); c.blockUntilConnected(); LeaderLatch l = new LeaderLatch(c, "/latch2", "X"); List<String> ev = Collections.synchronizedList(new ArrayList<>()); long T0 = System.nanoTime();
        l.addListener(new LeaderLatchListener() { public void isLeader() { ev.add(String.format("%.1fs isLeader", (System.nanoTime() - T0) / 1e9)); } public void notLeader() { ev.add(String.format("%.1fs notLeader", (System.nanoTime() - T0) / 1e9)); } });
        c.getConnectionStateListenable().addListener((cf, s) -> ev.add(String.format("%.1fs STATE %s", (System.nanoTime() - T0) / 1e9, s)));
        l.start(); l.await(5, TimeUnit.SECONDS); Thread.sleep(500); ev.add(String.format("%.1fs 冻结服务端 5 s", (System.nanoTime() - T0) / 1e9));
        new ProcessBuilder("kill", "-STOP", pid).start().waitFor(); Thread.sleep(5000); new ProcessBuilder("kill", "-CONT", pid).start().waitFor(); ev.add(String.format("%.1fs 解冻", (System.nanoTime() - T0) / 1e9)); Thread.sleep(6000);
        for (String s : ev) System.out.println("  " + s); System.out.println("  最后 hasLeadership = " + l.hasLeadership()); l.close(); c.close();
        System.out.println();
        System.out.println("== 三:LeaderSelector(autoRequeue):takeLeadership 持有 600 ms 后返回,3 个候选 12 秒内轮流当 leader 的次数");
        Map<String, AtomicInteger> cnt = new ConcurrentHashMap<>(); List<LeaderSelector> sels = new ArrayList<>(); List<CuratorFramework> cs = new ArrayList<>(); List<String> order = Collections.synchronizedList(new ArrayList<>());
        for (int i = 0; i < 3; i++) { final String id = "S" + i; CuratorFramework ci = mk(6000); cs.add(ci); cnt.put(id, new AtomicInteger());
            LeaderSelector s = new LeaderSelector(ci, "/sel", new LeaderSelectorListenerAdapter() { public void takeLeadership(CuratorFramework cf) throws Exception { cnt.get(id).incrementAndGet(); order.add(id); Thread.sleep(600); } }); s.autoRequeue(); s.start(); sels.add(s); }
        Thread.sleep(12000); for (LeaderSelector s : sels) s.close(); for (CuratorFramework ci : cs) ci.close();
        System.out.println("  各候选当 leader 的次数:" + new TreeMap<>(cnt) + ";前 12 次轮换顺序:" + order.subList(0, Math.min(12, order.size())));
        System.exit(0);
    }
}

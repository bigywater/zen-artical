import org.apache.curator.framework.*;
import org.apache.curator.framework.state.*;
import org.apache.curator.framework.recipes.nodes.PersistentNode;
import org.apache.curator.retry.*;
import org.apache.curator.RetryPolicy;
import org.apache.zookeeper.*;
import java.util.*;
import java.util.concurrent.*;

public class Z92 {
    static long T0;
    static String ms() { return String.format("%.1f", (System.nanoTime() - T0) / 1e9); }
    static void sh(String... c) throws Exception { new ProcessBuilder(c).start().waitFor(); }
    static CuratorFramework mk(String ns, RetryPolicy rp, int st) {
        CuratorFrameworkFactory.Builder b = CuratorFrameworkFactory.builder().connectString("127.0.0.1:7300").sessionTimeoutMs(st).connectionTimeoutMs(3000).retryPolicy(rp);
        if (ns != null) b.namespace(ns);
        CuratorFramework c = b.build(); c.start(); return c;
    }
    public static void main(String[] a) throws Exception {
        String pid = a[0];
        System.out.println("== 一:Curator 的流式 API 与 namespace:带 namespace=app1 的客户端建 /cfg/db(自动创建父节点),另一个不带 namespace 的客户端看到的真实路径");
        CuratorFramework c = mk("app1", new ExponentialBackoffRetry(200, 5), 6000);
        c.blockUntilConnected();
        c.create().creatingParentsIfNeeded().forPath("/cfg/db", "mysql://x".getBytes());
        String seq = c.create().withMode(CreateMode.EPHEMERAL_SEQUENTIAL).forPath("/cfg/job-", new byte[0]);
        System.out.println("  create EPHEMERAL_SEQUENTIAL 返回的路径(namespace 之内):" + seq);
        CuratorFramework raw = mk(null, new RetryNTimes(1, 100), 6000); raw.blockUntilConnected();
        System.out.println("  不带 namespace 的客户端 getChildren(\"/\"):" + raw.getChildren().forPath("/") + ";getChildren(\"/app1/cfg\"):" + raw.getChildren().forPath("/app1/cfg"));
        try { c.setData().withVersion(99).forPath("/cfg/db", "x".getBytes()); } catch (KeeperException.BadVersionException e) { System.out.println("  setData().withVersion(99) → " + e.getClass().getSimpleName()); }
        try { c.create().forPath("/cfg/db"); } catch (KeeperException.NodeExistsException e) { System.out.println("  create 已存在 → " + e.getClass().getSimpleName()); }
        System.out.println();
        System.out.println("== 二:同步 vs 后台(inBackground)创建 2000 个节点");
        c.create().creatingParentsIfNeeded().forPath("/s"); c.create().forPath("/b");
        long t = System.nanoTime(); for (int i = 0; i < 2000; i++) c.create().forPath("/s/n" + i, new byte[1]); double ts = (System.nanoTime() - t) / 1e9;
        CountDownLatch cl = new CountDownLatch(2000); t = System.nanoTime();
        for (int i = 0; i < 2000; i++) c.create().inBackground((cf, ev) -> cl.countDown()).forPath("/b/n" + i, new byte[1]);
        cl.await(); double tb = (System.nanoTime() - t) / 1e9;
        System.out.printf("  同步 %.0f 个/s(%.2f s);inBackground %.0f 个/s(%.2f s);%.1f 倍%n", 2000 / ts, ts, 2000 / tb, tb, ts / tb);
        System.out.println();
        for (int round = 0; round < 2; round++) {
            long freeze = round == 0 ? 5000 : 8000; String label = round == 0 ? "短中断(服务端被 SIGSTOP 冻结 5 s,会话超时 6 s)" : "长中断(冻结 12 s,超过会话超时 6 s)";
            if (round == 1) freeze = 12000;
            System.out.println("== " + (round == 0 ? "三" : "四") + ":" + label + ":ConnectionStateListener 的状态序列、中断期间的 setData、PersistentNode(临时)是否自动恢复");
            List<String> log = Collections.synchronizedList(new ArrayList<>());
            CuratorFramework cc = mk(null, new ExponentialBackoffRetry(200, 12, 2000), 6000); cc.blockUntilConnected();
            T0 = System.nanoTime();
            cc.getConnectionStateListenable().addListener((cf, s) -> log.add(ms() + "s " + s));
            PersistentNode pn = new PersistentNode(cc, CreateMode.EPHEMERAL, false, "/pn" + round, "me".getBytes()); pn.start(); pn.waitForInitialCreate(3, TimeUnit.SECONDS);
            cc.create().forPath("/plain" + round, new byte[0]); 
            long sid0 = cc.getZookeeperClient().getZooKeeper().getSessionId();
            cc.create().withMode(CreateMode.EPHEMERAL).forPath("/plain-eph" + round);
            sh("kill", "-STOP", pid); double tf = (System.nanoTime() - T0) / 1e9; Thread.sleep(300);
            long t1 = System.nanoTime(); String r;
            ExecutorService ex = Executors.newSingleThreadExecutor(); Future<String> f = ex.submit(() -> { try { cc.setData().forPath("/plain" + (a.length > 0 ? "0" : "0"), "v".getBytes()); return "成功"; } catch (Exception e) { return e.getClass().getSimpleName(); } });
            Thread.sleep(Math.max(0, freeze - 300)); sh("kill", "-CONT", pid); double tr = (System.nanoTime() - T0) / 1e9;
            try { r = f.get(30, TimeUnit.SECONDS); } catch (TimeoutException e) { r = "30 s 仍未返回"; }
            double dur = (System.nanoTime() - t1) / 1e9; double rel = (System.nanoTime() - T0) / 1e9 - tr;
            long sid1 = 0; double tPlainGone = -1, tPnNew = -1; long tw = System.nanoTime();
            while ((System.nanoTime() - tw) / 1e9 < 16) {
                sid1 = cc.getZookeeperClient().getZooKeeper().getSessionId(); double el = (System.nanoTime() - T0) / 1e9 - tr;
                if (tPlainGone < 0 && raw.checkExists().forPath("/plain-eph" + round) == null) tPlainGone = el;
                org.apache.zookeeper.data.Stat ps = raw.checkExists().forPath("/pn" + round);
                if (tPnNew < 0 && ps != null && ps.getEphemeralOwner() == sid1) tPnNew = el;
                Thread.sleep(100);
            }
            System.out.println("  冻结发生在 +" + String.format("%.1f", tf) + " s,解冻在 +" + String.format("%.1f", tr) + " s");
            System.out.println("  listener 状态序列:" + log);
            System.out.println("  中断期间发起的 setData(retry=ExponentialBackoffRetry):" + r + ",发起后 " + String.format("%.1f", dur) + " s 返回(相对解冻 +" + String.format("%.1f", rel) + " s)");
            System.out.println("  会话 id 变了:" + (sid0 != sid1) + "(旧 0x" + Long.toHexString(sid0) + ",新 0x" + Long.toHexString(sid1) + ")");
            if (sid0 == sid1) System.out.println("  会话没有变:普通临时节点一直在(" + (raw.checkExists().forPath("/plain-eph" + round) != null) + "),PersistentNode 的节点在(" + (raw.checkExists().forPath("/pn" + round) != null) + ")");
            else System.out.println("  解冻后,旧会话的普通临时节点在服务端消失于 +" + (tPlainGone < 0 ? "16 s 内未消失" : String.format("%.1f s", tPlainGone)) + ";PersistentNode 的节点属主变成新会话于 +" + (tPnNew < 0 ? "16 s 内未发生" : String.format("%.1f s", tPnNew)) + "(相对解冻)");
            pn.close(); cc.close(); ex.shutdownNow();
            System.out.println();
        }
        c.close(); raw.close(); System.exit(0);
    }
}

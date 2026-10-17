import org.apache.zookeeper.*;
import org.apache.zookeeper.data.*;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

public class Z100 {
    static String mntr(String k) throws Exception { try (Socket s = new Socket("127.0.0.1", 7300)) { s.getOutputStream().write("mntr".getBytes()); s.shutdownOutput(); for (String l : new String(s.getInputStream().readAllBytes()).split("\n")) if (l.startsWith(k + "\t")) return l.split("\t")[1]; } return "?"; }
    public static void main(String[] a) throws Exception {
        CountDownLatch up = new CountDownLatch(1); ZooKeeper z = new ZooKeeper("127.0.0.1:7300", 6000, e -> { if (e.getState() == Watcher.Event.KeeperState.SyncConnected) up.countDown(); }); up.await();
        System.out.println("== 一:持久递归 watch(addWatch(path, watcher, PERSISTENT_RECURSIVE)):不会因触发而被移除,并且子孙节点的变化也会触发祖先路径上的 watch(对应源码 triggerWatch 里 PathParentIterator 的 atParentPath 分支)");
        List<String> ev = Collections.synchronizedList(new ArrayList<>());
        z.create("/p", new byte[0], ZooDefs.Ids.OPEN_ACL_UNSAFE, CreateMode.PERSISTENT);
        String before = mntr("zk_watch_count");
        z.addWatch("/p", e -> ev.add(e.getType() + " " + e.getPath()), AddWatchMode.PERSISTENT_RECURSIVE);
        System.out.println("  注册前 zk_watch_count=" + before + ",注册后 zk_watch_count=" + mntr("zk_watch_count"));
        z.create("/p/a", new byte[0], ZooDefs.Ids.OPEN_ACL_UNSAFE, CreateMode.PERSISTENT);
        z.create("/p/a/b", new byte[0], ZooDefs.Ids.OPEN_ACL_UNSAFE, CreateMode.PERSISTENT);
        z.create("/p/a/b/c", "1".getBytes(), ZooDefs.Ids.OPEN_ACL_UNSAFE, CreateMode.PERSISTENT);
        for (int i = 0; i < 5; i++) z.setData("/p/a/b/c", ("v" + i).getBytes(), -1);
        z.delete("/p/a/b/c", -1);
        Thread.sleep(500);
        Map<String, Integer> cnt = new TreeMap<>(); for (String s : ev) cnt.merge(s.split(" ")[0], 1, Integer::sum);
        System.out.println("  一连串变化(建 3 层、改 5 次、删 1 次)共收到 " + ev.size() + " 个事件,按类型:" + cnt);
        System.out.println("  前几个事件:" + ev.subList(0, Math.min(5, ev.size())));
        System.out.println("  全部触发之后 zk_watch_count=" + mntr("zk_watch_count") + "(没有被移除)");
        System.out.println();
        System.out.println("== 二:对比标准 watch:同一条连接同一路径,exists 的 data watch 与 getChildren 的 child watch 是两个不同的 IWatchManager,各计 1");
        z.create("/d", new byte[0], ZooDefs.Ids.OPEN_ACL_UNSAFE, CreateMode.PERSISTENT);
        List<String> ev2 = Collections.synchronizedList(new ArrayList<>()); Watcher w = e -> ev2.add(e.getType() + " " + e.getPath());
        String b2 = mntr("zk_watch_count"); z.exists("/d", w); z.getChildren("/d", w);
        System.out.println("  exists(/d, w) + getChildren(/d, w)(同一个 Watcher 对象):zk_watch_count " + b2 + " → " + mntr("zk_watch_count"));
        z.delete("/d", -1); Thread.sleep(500);
        System.out.println("  delete /d 后该连接收到的事件:" + ev2 + "(客户端库自己也会对同一个 Watcher 去重,所以这一项不能说明服务端行为;服务端的验证见第五项)");
        z.close(); System.exit(0);
    }
}

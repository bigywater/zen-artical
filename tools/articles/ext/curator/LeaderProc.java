import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.leader.*;
import org.apache.curator.retry.*;
import java.io.*;
public class LeaderProc {
    static PrintWriter pw;
    static synchronized void log(String m) { pw.println(System.currentTimeMillis() / 1000.0 + " " + m); pw.flush(); }
    public static void main(String[] a) throws Exception {
        String port = a[0], id = a[1]; pw = new PrintWriter(new FileWriter(a[2], true));
        CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:" + port).sessionTimeoutMs(3000).retryPolicy(new ExponentialBackoffRetry(100, 5)).build(); c.start(); c.blockUntilConnected();
        LeaderLatch l = new LeaderLatch(c, "/latch", id);
        l.addListener(new LeaderLatchListener() { public void isLeader() { log(id + " LEADER_START"); } public void notLeader() { log(id + " LEADER_LOST"); } });
        l.start(); log(id + " UP");
        while (true) { if (l.hasLeadership()) log(id + " BEAT"); Thread.sleep(50); }
    }
}

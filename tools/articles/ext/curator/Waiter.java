import org.apache.curator.framework.*;
import org.apache.curator.framework.recipes.locks.*;
import org.apache.curator.retry.*;
public class Waiter {
    public static void main(String[] a) throws Exception {
        CuratorFramework c = CuratorFrameworkFactory.builder().connectString("127.0.0.1:" + a[0]).sessionTimeoutMs(3000).retryPolicy(new ExponentialBackoffRetry(100, 5)).build(); c.start(); c.blockUntilConnected();
        InterProcessMutex m = new InterProcessMutex(c, "/hl"); m.acquire(); System.out.println(System.currentTimeMillis() + " WAITER_ACQUIRED"); System.out.flush(); Thread.sleep(500); m.release(); c.close(); System.exit(0);
    }
}

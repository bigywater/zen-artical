import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j283'); R = {}
CP = mcp('org.apache.activemq:artemis-jakarta-server:2.37.0', 'org.apache.activemq:artemis-jakarta-client:2.37.0', 'org.slf4j:slf4j-simple:2.0.13')
MAIN = r'''
import jakarta.jms.*; import org.apache.activemq.artemis.api.core.SimpleString; import org.apache.activemq.artemis.api.core.QueueConfiguration; import org.apache.activemq.artemis.api.core.RoutingType; import org.apache.activemq.artemis.core.config.Configuration; import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl; import org.apache.activemq.artemis.core.server.ActiveMQServer; import org.apache.activemq.artemis.core.server.ActiveMQServers; import org.apache.activemq.artemis.core.settings.impl.AddressSettings; import org.apache.activemq.artemis.jms.client.ActiveMQJMSConnectionFactory;
import java.util.*; import java.util.concurrent.*; import java.util.concurrent.atomic.*;
public class Main {
  static ConnectionFactory cf; static void say(String s) { System.out.println("RES " + s); } static void sec(String s) { System.out.println("SEC " + s); }
  static void send(String q, int n) throws Exception { try (Connection c = cf.createConnection(); Session s = c.createSession(false, Session.AUTO_ACKNOWLEDGE)) { MessageProducer p = s.createProducer(s.createQueue(q)); for (int i = 1; i <= n; i++) p.send(s.createTextMessage("m" + i)); } }
  static String desc(Message m) throws Exception { return ((TextMessage) m).getText() + "(JMSRedelivered=" + m.getJMSRedelivered() + ",JMSXDeliveryCount=" + m.getIntProperty("JMSXDeliveryCount") + ")"; }
  static List<String> drain(String q, int ackMode, long waitMs) throws Exception { List<String> out = new ArrayList<>(); try (Connection c = cf.createConnection(); Session s = c.createSession(false, ackMode)) { c.start(); MessageConsumer mc = s.createConsumer(s.createQueue(q)); Message m; while ((m = mc.receive(waitMs)) != null) { out.add(desc(m)); } } return out; }
  public static void main(String[] a) throws Exception {
    Configuration cfg = new ConfigurationImpl().setPersistenceEnabled(false).setSecurityEnabled(false).setJMXManagementEnabled(false).addAcceptorConfiguration("invm", "vm://0");
    cfg.addAddressSetting("#", new AddressSettings().setMaxDeliveryAttempts(3).setDeadLetterAddress(SimpleString.of("DLQ")).setRedeliveryDelay(0));
    ActiveMQServer server = ActiveMQServers.newActiveMQServer(cfg); server.start(); server.createQueue(QueueConfiguration.of("DLQ").setAddress("DLQ").setRoutingType(RoutingType.ANYCAST).setDurable(false).setAutoCreated(false)); cf = new ActiveMQJMSConnectionFactory("vm://0");
    try {
      sec("== 一:AUTO_ACKNOWLEDGE 与 CLIENT_ACKNOWLEDGE:消费者取到第 1 条消息之后“崩溃”(关闭连接,没有处理完)");
      for (int mode : new int[]{Session.AUTO_ACKNOWLEDGE, Session.CLIENT_ACKNOWLEDGE}) { String q = "q1-" + mode; send(q, 3);
        try (Connection c = cf.createConnection(); Session s = c.createSession(false, mode)) { c.start(); MessageConsumer mc = s.createConsumer(s.createQueue(q)); Message m = mc.receive(1000); say((mode == Session.AUTO_ACKNOWLEDGE ? "AUTO_ACKNOWLEDGE" : "CLIENT_ACKNOWLEDGE") + ":消费者 A 取到 " + desc(m) + ",还没来得及处理就崩溃(直接关闭连接)"); }
        say("    之后消费者 B 能取到:" + drain(q, Session.AUTO_ACKNOWLEDGE, 800)); }
      sec("== 二:CLIENT_ACKNOWLEDGE 的 acknowledge() 确认的是这个会话已经收到的全部消息,不只是这一条");
      send("q2", 5); try (Connection c = cf.createConnection(); Session s = c.createSession(false, Session.CLIENT_ACKNOWLEDGE)) { c.start(); MessageConsumer mc = s.createConsumer(s.createQueue("q2")); Message m1 = mc.receive(1000), m2 = mc.receive(1000), m3 = mc.receive(1000); say("消费者 A 收到 m1、m2、m3,只对第 2 条 m2 调用 acknowledge()"); m2.acknowledge(); }
      say("    之后消费者 B 能取到:" + drain("q2", Session.AUTO_ACKNOWLEDGE, 800) + "(m1、m3 没有被确认过,也不会再来)");
      sec("== 三:AUTO_ACKNOWLEDGE 的 MessageListener 抛出异常:消息会被重新投递吗");
      send("q3", 1); CountDownLatch done = new CountDownLatch(1); List<String> seen = Collections.synchronizedList(new ArrayList<>()); try (Connection c = cf.createConnection(); Session s = c.createSession(false, Session.AUTO_ACKNOWLEDGE)) { MessageConsumer mc = s.createConsumer(s.createQueue("q3")); mc.setMessageListener(m -> { try { seen.add(desc(m)); if (seen.size() < 3) throw new RuntimeException("监听器处理失败(第 " + seen.size() + " 次)"); done.countDown(); } catch (Exception e) { if (e instanceof RuntimeException re) throw re; throw new RuntimeException(e); } }); c.start(); done.await(5, TimeUnit.SECONDS); Thread.sleep(300); }
      say("监听器前两次抛出 RuntimeException,第三次成功:收到的投递依次是 " + seen);
      sec("== 四:事务会话 SESSION_TRANSACTED:rollback 与 commit,以及生产者一侧的事务");
      send("q4", 1); try (Connection c = cf.createConnection(); Session s = c.createSession(true, Session.SESSION_TRANSACTED)) { c.start(); MessageConsumer mc = s.createConsumer(s.createQueue("q4")); Message m = mc.receive(1000); say("第 1 次 receive:" + desc(m)); s.rollback(); Message m2 = mc.receive(1000); say("rollback 之后立刻 receive:" + desc(m2)); s.rollback(); Message m3 = mc.receive(1000); say("再 rollback 之后 receive:" + desc(m3)); s.commit(); say("commit 之后队列里剩余:" + drain("q4", Session.AUTO_ACKNOWLEDGE, 500)); }
      try (Connection c = cf.createConnection(); Session ps = c.createSession(true, Session.SESSION_TRANSACTED)) { MessageProducer p = ps.createProducer(ps.createQueue("q4b")); p.send(ps.createTextMessage("tx1")); p.send(ps.createTextMessage("tx2")); say("生产者事务里发送了 2 条但还没 commit:另一个消费者 500 ms 内能取到 " + drain("q4b", Session.AUTO_ACKNOWLEDGE, 500)); ps.commit(); say("commit 之后:" + drain("q4b", Session.AUTO_ACKNOWLEDGE, 500)); p.send(ps.createTextMessage("tx3")); ps.rollback(); say("再发送 tx3 并 rollback:队列里 " + drain("q4b", Session.AUTO_ACKNOWLEDGE, 500)); }
      sec("== 五:反复 rollback:超过最大投递次数(这里设为 3)的消息进入死信队列 DLQ");
      send("q5", 1); try (Connection c = cf.createConnection(); Session s = c.createSession(true, Session.SESSION_TRANSACTED)) { c.start(); MessageConsumer mc = s.createConsumer(s.createQueue("q5")); int n = 0; Message m; List<String> got = new ArrayList<>(); while ((m = mc.receive(800)) != null) { n++; got.add(desc(m)); s.rollback(); } say("每次 receive 后都 rollback:共被投递 " + n + " 次:" + got + ";之后 receive 返回 null"); }
      say("原队列 q5 里剩余:" + drain("q5", Session.AUTO_ACKNOWLEDGE, 500)); List<String> dl = new ArrayList<>(); try (Connection c = cf.createConnection(); Session s = c.createSession(false, Session.AUTO_ACKNOWLEDGE)) { c.start(); MessageConsumer mc = s.createConsumer(s.createQueue("DLQ")); Message m = mc.receive(1500); if (m != null) dl.add(desc(m) + ",_AMQ_ORIG_QUEUE=" + m.getStringProperty("_AMQ_ORIG_QUEUE")); } say("死信队列 DLQ 里的消息:" + dl);
    } finally { server.stop(); }
  }
}
'''
d = jdir('j283a'); write(d, {'Main.java': MAIN}); E = jenv('21'); (d / 'out').mkdir(exist_ok=True)
rc = subprocess.run(['javac', '-d', 'out', '-cp', CP, 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:3500]); sys.exit()
r = subprocess.run(['java', '-Dorg.slf4j.simpleLogger.defaultLogLevel=error', '-cp', 'out:' + CP, 'Main'], cwd=d, env=E, capture_output=True, text=True, timeout=240)
for l in (r.stdout + r.stderr).splitlines():
    if l.startswith('SEC '): print(l[4:])
    elif l.startswith('RES '): print('  ' + l[4:])
    elif r.returncode != 0 and l.strip(): print('  ! ' + l[:220])

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from txl import *
tee('t13'); reset(); shutil.rmtree(JHOME / 'logs', ignore_errors=True)
TXLOG = JHOME / 'logs' / 'rocketmqlogs' / 'transaction.log'
CONNECTOR = TT / 'dl' / 'mysql-connector-j-26.7.0.jar'
CP = f'{RMQ_HOME}/lib/*:{CONNECTOR}'
M = MySQL('t13').start(); M.q('create database shop'); M.q('create table orders(id varchar(40) primary key, amount int)', db='shop')
M.q("create user 'app'@'127.0.0.1' identified by 'app'"); M.q("grant all on shop.* to 'app'@'127.0.0.1'")
RQ = RocketMQ('t13', broker_conf={'transactionCheckMax': 3, 'transactionCheckInterval': 3000, 'transactionTimeOut': 3000}).start()
RQ.admin('updateTopic', '-c', 'DefaultCluster', '-t', 'OrderTopic')
NS = f'127.0.0.1:{RQ.ns_port}'; URL = f'jdbc:mysql://127.0.0.1:{M.port}/shop?useSSL=false&allowPublicKeyRetrieval=true'
print(f'RocketMQ 5.5.1(官方 bin 包,NameServer {RQ.ns_port} + 单 Broker {RQ.port},Java 17,客户端 rocketmq-client 5.5.1 的 TransactionMQProducer);本地事务写 MySQL {M.q("select version()")[0][0]}(Connector/J 26.7.0);broker 配置 transactionTimeOut=3000 ms(半消息多久没有结果就开始回查)、transactionCheckInterval=3000 ms(两次回查的间隔)、transactionCheckMax=3(回查最多几次,默认 15)')
JAVA = r'''
import org.apache.rocketmq.client.consumer.*;
import org.apache.rocketmq.client.consumer.listener.*;
import org.apache.rocketmq.client.producer.*;
import org.apache.rocketmq.common.message.*;
import org.apache.rocketmq.common.consumer.ConsumeFromWhere;
import java.sql.*;
import java.util.*;

public class Tx {
  static String url, scenario, checkmode; static long T0 = System.currentTimeMillis();
  static void log(String s) { System.out.println(s); System.out.flush(); }
  static Connection db() throws Exception { return DriverManager.getConnection(url, "app", "app"); }
  static boolean orderExists(String oid) throws Exception { try (Connection c = db(); PreparedStatement ps = c.prepareStatement("select 1 from orders where id = ?")) { ps.setString(1, oid); return ps.executeQuery().next(); } }
  static void insertOrder(String oid, boolean commit) throws Exception {
    try (Connection c = db()) { c.setAutoCommit(false); try (PreparedStatement ps = c.prepareStatement("insert into orders values (?, 100)")) { ps.setString(1, oid); ps.executeUpdate(); } if (commit) c.commit(); else c.rollback(); }
  }
  public static void main(String[] a) throws Exception {
    String mode = a[0], ns = a[1]; url = a[2]; scenario = a.length > 3 ? a[3] : ""; String oid = a.length > 4 ? a[4] : ""; checkmode = a.length > 5 ? a[5] : "db"; int secs = a.length > 6 ? Integer.parseInt(a[6]) : 10;
    if (mode.equals("consumer")) {
      DefaultMQPushConsumer c = new DefaultMQPushConsumer("cg-order"); c.setNamesrvAddr(ns); c.setConsumeFromWhere(ConsumeFromWhere.CONSUME_FROM_FIRST_OFFSET);
      c.subscribe("OrderTopic", "*");
      c.registerMessageListener((MessageListenerConcurrently) (msgs, ctx) -> { for (MessageExt m : msgs) log("CONSUMED " + new String(m.getBody())); return ConsumeConcurrentlyStatus.CONSUME_SUCCESS; });
      c.start(); log("CONSUMER_STARTED"); Thread.sleep(600000); return;
    }
    boolean withTopics = a.length > 7 && a[7].equals("yes");
    TransactionMQProducer p = withTopics ? new TransactionMQProducer("pg-order", Arrays.asList("OrderTopic")) : new TransactionMQProducer("pg-order"); p.setNamesrvAddr(ns);
    p.setTransactionListener(new TransactionListener() {
      public LocalTransactionState executeLocalTransaction(Message m, Object arg) {
        String id = new String(m.getBody()); log("HALF_SENT " + id);
        try {
          switch (scenario) {
            case "commit": log("LOCAL_TX_BEGIN"); Thread.sleep(1500); insertOrder(id, true); log("LOCAL_TX_COMMITTED"); return LocalTransactionState.COMMIT_MESSAGE;
            case "rollback": log("LOCAL_TX_BEGIN"); Thread.sleep(500); insertOrder(id, false); log("LOCAL_TX_ROLLED_BACK"); return LocalTransactionState.ROLLBACK_MESSAGE;
            case "unknown": insertOrder(id, true); log("LOCAL_TX_COMMITTED (listener returns UNKNOW)"); return LocalTransactionState.UNKNOW;
            case "crash_after_db": insertOrder(id, true); log("LOCAL_TX_COMMITTED"); Thread.sleep(600000); break;
            case "crash_before_db": log("BEFORE_DB"); Thread.sleep(600000); break;
          }
        } catch (Exception e) { log("ERR " + e); return LocalTransactionState.ROLLBACK_MESSAGE; }
        return LocalTransactionState.UNKNOW;
      }
      public LocalTransactionState checkLocalTransaction(MessageExt m) {
        String id = new String(m.getBody()); String times = m.getUserProperty("TRANSACTION_CHECK_TIMES");
        try {
          if (checkmode.equals("unknown")) { log("CHECK_BACK " + id + " times=" + times + " -> UNKNOW(查不出来)"); return LocalTransactionState.UNKNOW; }
          boolean ex = orderExists(id); log("CHECK_BACK " + id + " times=" + times + " 订单存在=" + ex + " -> " + (ex ? "COMMIT" : "ROLLBACK"));
          return ex ? LocalTransactionState.COMMIT_MESSAGE : LocalTransactionState.ROLLBACK_MESSAGE;
        } catch (Exception e) { log("CHECK_ERR " + e); return LocalTransactionState.UNKNOW; }
      }
    });
    p.start(); log("PRODUCER_STARTED");
    if (!scenario.equals("checkonly")) { TransactionSendResult r = p.sendMessageInTransaction(new Message("OrderTopic", "t", oid, oid.getBytes()), null); log("SEND_RESULT " + r.getSendStatus() + " local=" + r.getLocalTransactionState()); }
    Thread.sleep(secs * 1000L); p.shutdown(); log("PRODUCER_DONE");
  }
}
'''
d = java_compile('t13', {'Tx.java': JAVA}, CP)
def jp(*args, xmx='192m'): return JProc(d, 'Tx', list(args), classpath=CP, xmx=xmx)
cons = jp('consumer', NS, URL); assert cons.wait_line('CONSUMER_STARTED', 60) is not None; time.sleep(1.5)
def n_orders(oid): return M.q('select count(*) from orders where id = %s', (oid,), db='shop')[0][0]
def show(procs, origin, pat=None):
    allv = []
    for name, pr in procs:
        for t, l in pr.lines:
            if pat is None or re.search(pat, l): allv.append((t, name, l))
    for t, name, l in sorted(allv): print(f'    {(t - origin) * 1000:7.0f} ms  [{name}] {l}')
def consumed(oid): return [t for t, l in cons.grep(rf'CONSUMED {oid}$')]

print('== 一:正常提交:半消息先发到 broker(此时消费者看不到),再执行本地事务(这里故意慢 1.5 秒),本地事务提交、返回 COMMIT_MESSAGE 之后,消费者才收到')
p = jp('producer', NS, URL, 'commit', 'o-1', 'db', 6); i = p.wait_line('SEND_RESULT', 30); origin = p.grep('HALF_SENT')[0][0]; time.sleep(1.0)
show([('生产者', p), ('消费者', cons)], origin, r'HALF_SENT|LOCAL_TX|SEND_RESULT|CONSUMED o-1')
t_c = consumed('o-1'); t_commit = p.grep('LOCAL_TX_COMMITTED')[0][0]; t_half = p.grep('HALF_SENT')[0][0]
print(f'  半消息发出后 {(t_commit - t_half) * 1000:.0f} ms 本地事务才提交,这段时间消费者什么都没收到;提交后 {(t_c[0] - t_commit) * 1000:.0f} ms 消费者收到 o-1;订单库里 o-1 有 {n_orders("o-1")} 行')
p.stop()

print('== 二:本地事务回滚(监听器返回 ROLLBACK_MESSAGE):半消息被丢弃,消费者永远收不到')
p = jp('producer', NS, URL, 'rollback', 'o-2', 'db', 5); p.wait_line('SEND_RESULT', 30); origin = p.grep('HALF_SENT')[0][0]; time.sleep(5.0)
show([('生产者', p)], origin, r'HALF_SENT|LOCAL_TX|SEND_RESULT')
print(f'  等了 5 秒:消费者收到 o-2 的次数 {len(consumed("o-2"))};订单库里 o-2 有 {n_orders("o-2")} 行')
p.stop()

print('== 三:本地事务其实提交了,但监听器返回 UNKNOW(比如提交成功、应答丢了):broker 等 transactionTimeOut 之后回查,生产者查库发现订单在,回复 COMMIT')
p = jp('producer', NS, URL, 'unknown', 'o-3', 'db', 12); p.wait_line('SEND_RESULT', 30); origin = p.grep('HALF_SENT')[0][0]
cons.wait_line('CONSUMED o-3', 30); time.sleep(1.0)
show([('生产者', p), ('消费者', cons)], origin, r'HALF_SENT|LOCAL_TX|SEND_RESULT|CHECK_BACK|CONSUMED o-3')
print(f'  回查发生在半消息发出 {(p.grep("CHECK_BACK")[0][0] - p.grep("HALF_SENT")[0][0]) * 1000:.0f} ms 之后(transactionTimeOut = 3000 ms);回查 {len(p.grep("CHECK_BACK"))} 次;消费者收到 o-3 {len(consumed("o-3"))} 次')
p.stop()

def txlog_lines(start):
    if not TXLOG.exists(): return []
    return TXLOG.read_text().splitlines()[start:]
def n_txlog(): return len(TXLOG.read_text().splitlines()) if TXLOG.exists() else 0

print('== 四:生产者在本地事务提交之后、返回结果之前被 kill -9(订单已经写进库,半消息悬在 broker 上),换一个新的生产者进程(同一个 producer group)上线。先试“新生产者只是启动、没有声明 topic”,再试“声明了 topic”')
mark = n_txlog()
p1 = jp('producer', NS, URL, 'crash_after_db', 'o-4', 'db', 60); p1.wait_line('LOCAL_TX_COMMITTED', 30); time.sleep(0.5); tk = time.time(); p1.kill()
p2 = jp('producer', NS, URL, 'checkonly', '', 'db', 22, 'no'); p2.wait_line('PRODUCER_STARTED', 30); cons.wait_line('CONSUMED o-4', 14); time.sleep(0.5)
print(f'    {0:7.0f} ms  [旧生产者] kill -9(订单已提交,事务结果没有告诉 broker)')
for t, l in p2.lines:
    if re.search(r'PRODUCER_STARTED|CHECK_BACK', l): print(f'    {(t - tk) * 1000:7.0f} ms  [新生产者(没声明 topic)] {l}')
for t in consumed('o-4'): print(f'    {(t - tk) * 1000:7.0f} ms  [消费者] CONSUMED o-4')
fail = [l for l in txlog_lines(mark) if 'Check transaction failed' in l or 'checked-too-many-time' in l]
print(f'  订单库里 o-4 有 {n_orders("o-4")} 行;消费者收到 o-4 {len(consumed("o-4"))} 次;新生产者收到回查 {len(p2.grep("CHECK_BACK"))} 次。broker 的 transaction.log 里和这条半消息有关的行({len(fail)} 行):')
for l in fail: print('    ' + re.sub(r'^\d{4}-\d\d-\d\d ', '', l)[:150])
p2.stop()
mark = n_txlog()
p1 = jp('producer', NS, URL, 'crash_after_db', 'o-4b', 'db', 60); p1.wait_line('LOCAL_TX_COMMITTED', 30); time.sleep(0.5); tk = time.time(); p1.kill()
p2 = jp('producer', NS, URL, 'checkonly', '', 'db', 20, 'yes'); p2.wait_line('PRODUCER_STARTED', 30); cons.wait_line('CONSUMED o-4b', 40); time.sleep(0.5)
print(f'    {0:7.0f} ms  [旧生产者] kill -9(o-4b,订单已提交)')
for t, l in p2.lines:
    if re.search(r'PRODUCER_STARTED|CHECK_BACK', l): print(f'    {(t - tk) * 1000:7.0f} ms  [新生产者(声明了 topic)] {l}')
for t in consumed('o-4b'): print(f'    {(t - tk) * 1000:7.0f} ms  [消费者] CONSUMED o-4b')
print(f'  订单库里 o-4b 有 {n_orders("o-4b")} 行;消费者收到 o-4b {len(consumed("o-4b"))} 次 —— 声明了 topic 的新生产者启动时就取了路由、向 broker 注册,broker 才找得到“能回查的人”;事务结果由能查本地数据库的人在回查里补上')
p2.stop()

print('== 五:生产者在本地事务提交之前被 kill -9(订单没写进库),声明了 topic 的新生产者上线后回查:库里没有订单 → ROLLBACK,消息不会发出')
p1 = jp('producer', NS, URL, 'crash_before_db', 'o-5', 'db', 60); p1.wait_line('BEFORE_DB', 30); time.sleep(0.5); tk = time.time(); p1.kill()
p2 = jp('producer', NS, URL, 'checkonly', '', 'db', 14, 'yes'); p2.wait_line('PRODUCER_STARTED', 30); p2.wait_line('CHECK_BACK', 30); time.sleep(5.0)
for t, l in p2.lines:
    if re.search(r'CHECK_BACK', l): print(f'    {(t - tk) * 1000:7.0f} ms  [新生产者] {l}')
print(f'  等了 5 秒:订单库里 o-5 有 {n_orders("o-5")} 行;消费者收到 o-5 {len(consumed("o-5"))} 次')
p2.stop()

mark = n_txlog()
print('== 六:回查一直查不出结果(一直返回 UNKNOW):broker 最多回查 transactionCheckMax 次,之后丢弃半消息(这里 broker 配成了 3 次)')
p = jp('producer', NS, URL, 'unknown', 'o-6', 'unknown', 25); p.wait_line('SEND_RESULT', 30); origin = p.grep('HALF_SENT')[0][0]; time.sleep(18.0)
show([('生产者', p)], origin, r'HALF_SENT|LOCAL_TX|SEND_RESULT|CHECK_BACK')
lg = [l for l in txlog_lines(mark) if 'checked-too-many-time' in l]
for l in lg[-1:]: print('  broker 的 transaction.log:' + re.sub(r'^\d{4}-\d\d-\d\d ', '', l)[:150])
print(f'  回查共 {len(p.grep("CHECK_BACK"))} 次;消费者收到 o-6 {len(consumed("o-6"))} 次;订单库里 o-6 有 {n_orders("o-6")} 行(本地事务其实提交了,但消息被 broker 丢掉了:本地有订单、下游收不到)')
p.stop(); cons.stop()
RQ.kill(); reset()
for n in ('my_t13', 'rmq_t13', 'j_t13'): shutil.rmtree(TT / n, ignore_errors=True)

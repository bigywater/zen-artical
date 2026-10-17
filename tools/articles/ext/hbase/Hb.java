import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.hbase.*;
import org.apache.hadoop.hbase.client.*;
import org.apache.hadoop.hbase.util.Bytes;
import java.util.*;

public class Hb {
    static Configuration conf() {
        Configuration c = HBaseConfiguration.create(); c.set("hbase.zookeeper.quorum", "127.0.0.1"); c.setInt("hbase.zookeeper.property.clientPort", 7300); c.setInt("zookeeper.session.timeout", 6000);
        c.setInt("hbase.client.operation.timeout", 4000); c.setInt("hbase.rpc.timeout", 1500); c.setInt("hbase.client.retries.number", 3); c.setInt("hbase.client.pause", 100); c.setInt("hbase.client.meta.operation.timeout", 4000); c.setInt("hbase.client.scanner.timeout.period", 4000); return c;
    }
    public static void main(String[] a) throws Exception {
        try (Connection cn = ConnectionFactory.createConnection(conf())) {
            TableName tn = TableName.valueOf("t1");
            if (a[0].equals("create")) {
                try (Admin ad = cn.getAdmin()) {
                    ad.createTable(TableDescriptorBuilder.newBuilder(tn).setColumnFamily(ColumnFamilyDescriptorBuilder.of("f")).build(), new byte[][]{Bytes.toBytes("c"), Bytes.toBytes("f"), Bytes.toBytes("k"), Bytes.toBytes("p"), Bytes.toBytes("t")});
                    Map<String, Integer> per = new TreeMap<>();
                    for (HRegionLocation l : cn.getRegionLocator(tn).getAllRegionLocations()) per.merge(l.getServerName().getPort() + "", 1, Integer::sum);
                    System.out.println("TABLE_CREATED regions per server port: " + per);
                }
                try (Table t = cn.getTable(tn)) { for (int i = 0; i < 300; i++) { Put p = new Put(Bytes.toBytes(String.format("%c-%04d", (char) ('a' + i % 26), i))); p.addColumn(Bytes.toBytes("f"), Bytes.toBytes("q"), Bytes.toBytes("v" + i)); t.put(p); } }
                System.out.println("ROWS_PUT 300");
            } else if (a[0].equals("probe")) {
                try (Table t = cn.getTable(tn)) {
                    int i = 0; String[] keys = {"a", "e", "h", "m", "q", "w"};
                    while (true) {
                        long t0 = System.currentTimeMillis(); String r;
                        try { Put p = new Put(Bytes.toBytes(keys[i % keys.length] + "-probe-" + i)); p.addColumn(Bytes.toBytes("f"), Bytes.toBytes("q"), Bytes.toBytes("x")); t.put(p); t.get(new Get(p.getRow())); r = "OK"; } catch (Exception e) { r = "ERR " + e.getClass().getSimpleName(); }
                        System.out.println(t0 + " " + r + " " + (System.currentTimeMillis() - t0)); System.out.flush(); i++; Thread.sleep(100);
                    }
                }
            }
        }
        System.exit(0);
    }
}

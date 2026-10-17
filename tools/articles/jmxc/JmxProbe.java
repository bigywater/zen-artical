import javax.management.*; import javax.management.remote.*; import java.util.*;
public class JmxProbe {
    public static void main(String[] a) throws Exception {
        JMXServiceURL u = new JMXServiceURL("service:jmx:rmi:///jndi/rmi://127.0.0.1:" + a[0] + "/jmxrmi");
        try (JMXConnector c = JMXConnectorFactory.connect(u)) {
            MBeanServerConnection m = c.getMBeanServerConnection();
            Set<ObjectName> names = new TreeSet<>(m.queryNames(new ObjectName("org.apache.ZooKeeperService:*"), null));
            if (a.length == 1) { for (ObjectName n : names) System.out.println(n.getCanonicalName()); return; }
            ObjectName n = new ObjectName(a[1]);
            if (a.length == 2) { for (MBeanAttributeInfo i : m.getMBeanInfo(n).getAttributes()) { Object v; try { v = m.getAttribute(n, i.getName()); } catch (Exception e) { v = "(unreadable)"; } System.out.println("ATTR " + i.getName() + " = " + v); } for (MBeanOperationInfo o : m.getMBeanInfo(n).getOperations()) System.out.println("OP " + o.getName()); }
        }
    }
}

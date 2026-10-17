public class GreeterImpl implements Greeter { final String id; GreeterImpl(String id) { this.id = id; } public String hi(String n) { return "hi " + n + " from " + id; } }

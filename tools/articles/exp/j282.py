import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j282'); R = {}
CP = mcp('org.glassfish.jersey.containers:jersey-container-jdk-http:3.1.9', 'org.glassfish.jersey.inject:jersey-hk2:3.1.9')
FILES = {
 'T.java': 'import jakarta.ws.rs.container.*; import java.util.*; public class T { static void add(ContainerRequestContext c, String s) { @SuppressWarnings("unchecked") List<String> l = (List<String>) c.getProperty("trace"); if (l == null) { l = new ArrayList<>(); c.setProperty("trace", l); } l.add(s); } static List<String> get(ContainerRequestContext c) { @SuppressWarnings("unchecked") List<String> l = (List<String>) c.getProperty("trace"); return l == null ? new ArrayList<>() : l; } }',
 'Filters.java': r'''
import jakarta.annotation.Priority; import jakarta.ws.rs.*; import jakarta.ws.rs.container.*; import jakarta.ws.rs.core.*; import jakarta.ws.rs.ext.*; import java.io.*; import java.nio.charset.StandardCharsets; import java.util.*;
public class Filters {
  @Provider @PreMatching @Priority(100) public static class PreA implements ContainerRequestFilter { public void filter(ContainerRequestContext c) { T.add(c, "请求:PreMatching A(100) 路径=" + c.getUriInfo().getPath()); if (c.getUriInfo().getPath().equals("legacy/hello")) { c.setRequestUri(java.net.URI.create(c.getUriInfo().getBaseUri() + "hello")); T.add(c, "  PreMatching A 把 legacy/hello 改写成 hello"); } } }
  @Provider @PreMatching @Priority(200) public static class PreB implements ContainerRequestFilter { public void filter(ContainerRequestContext c) { T.add(c, "请求:PreMatching B(200) 方法=" + c.getMethod()); if ("POST".equals(c.getMethod()) && "true".equals(c.getHeaderString("X-Method-Override"))) { c.setMethod("PUT"); T.add(c, "  PreMatching B 把 POST 改成 PUT"); } } }
  @Provider @Priority(300) public static class PostA implements ContainerRequestFilter { @Context ResourceInfo ri; public void filter(ContainerRequestContext c) { T.add(c, "请求:Post A(300) 已匹配资源方法=" + (ri.getResourceMethod() == null ? "无" : ri.getResourceMethod().getName())); } }
  @Provider @Priority(100) public static class PostFirst implements ContainerRequestFilter { public void filter(ContainerRequestContext c) { T.add(c, "请求:Post First(100)"); if ("deny".equals(c.getHeaderString("X-Mode"))) { T.add(c, "  Post First 调用 abortWith(403)"); c.abortWith(Response.status(403).entity("被过滤器拒绝").build()); } } }
  @Provider @Priority(400) public static class PostLast implements ContainerRequestFilter { public void filter(ContainerRequestContext c) { T.add(c, "请求:Post Last(400)"); if ("throw".equals(c.getHeaderString("X-Mode"))) { T.add(c, "  Post Last 抛出 IllegalStateException"); throw new IllegalStateException("请求过滤器抛出"); } } }
  @Provider @Priority(100) public static class RespFirst implements ContainerResponseFilter { public void filter(ContainerRequestContext q, ContainerResponseContext r) { T.add(q, "响应:Resp(100) 状态=" + r.getStatus() + (r.hasEntity() ? ",实体=" + r.getEntity() : "")); } }
  @Provider @Priority(300) public static class RespSecond implements ContainerResponseFilter { public void filter(ContainerRequestContext q, ContainerResponseContext r) { T.add(q, "响应:Resp(300) 状态=" + r.getStatus()); } }
  @Provider @Priority(10) public static class TraceEmit implements ContainerResponseFilter { public void filter(ContainerRequestContext q, ContainerResponseContext r) { T.add(q, "响应:TraceEmit(10) 写出 X-Trace(响应过滤器按优先级从大到小执行,10 最后)"); r.getHeaders().putSingle("X-Trace", String.join(" | ", T.get(q)).replaceAll("[^\\x20-\\x7E]", "?")); r.getHeaders().putSingle("X-Trace-Utf8", java.util.Base64.getEncoder().encodeToString(String.join("\n", T.get(q)).getBytes(StandardCharsets.UTF_8))); } }
  @Provider public static class Boom implements ExceptionMapper<IllegalStateException> { public Response toResponse(IllegalStateException e) { return Response.status(500).entity("映射后的异常:" + e.getMessage()).build(); } }
  @NameBinding @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.RUNTIME) @java.lang.annotation.Target({java.lang.annotation.ElementType.TYPE, java.lang.annotation.ElementType.METHOD}) public @interface Audited {}
  @Provider @Audited @Priority(500) public static class AuditFilter implements ContainerRequestFilter { public void filter(ContainerRequestContext c) { T.add(c, "请求:Audit 过滤器(名字绑定 @Audited)"); } }
  @Provider @Priority(250) public static class BodyPeek implements ContainerRequestFilter { public void filter(ContainerRequestContext c) throws IOException { if (c.getHeaderString("X-Peek") != null) { byte[] b = c.getEntityStream().readAllBytes(); T.add(c, "请求:BodyPeek 读取了请求体 " + b.length + " 字节"); if (c.getHeaderString("X-Peek").equals("restore")) { c.setEntityStream(new ByteArrayInputStream(b)); T.add(c, "  BodyPeek 把读出来的字节重新放回实体流"); } } } }
}''',
 'Res.java': r'''
import jakarta.ws.rs.*; import jakarta.ws.rs.container.*; import jakarta.ws.rs.core.*; import java.io.*; import java.nio.charset.StandardCharsets;
@Path("/") public class Res {
  @GET @Path("hello") @Produces("text/plain; charset=UTF-8") public String hello(@Context ContainerRequestContext c) { T.add(c, "资源:hello() 被调用"); return "hello"; }
  @GET @Path("audited") @Filters.Audited @Produces("text/plain") public String audited(@Context ContainerRequestContext c) { T.add(c, "资源:audited() 被调用"); return "audited"; }
  @PUT @Path("echo") @Consumes("text/plain") @Produces("text/plain; charset=UTF-8") public String put(@Context ContainerRequestContext c, String body) { T.add(c, "资源:put() 被调用,body 长度 " + body.length()); return "put:" + body; }
  @POST @Path("echo") @Consumes("text/plain") @Produces("text/plain; charset=UTF-8") public String post(@Context ContainerRequestContext c, String body) { T.add(c, "资源:post() 被调用,body 长度 " + body.length()); return "post:" + body; }
  @GET @Path("boom") @Produces("text/plain") public String boom(@Context ContainerRequestContext c) { T.add(c, "资源:boom() 抛出 IllegalStateException"); throw new IllegalStateException("资源抛出"); }
}''',
 'Main.java': r'''
import jakarta.ws.rs.core.*; import org.glassfish.jersey.jdkhttp.JdkHttpServerFactory; import org.glassfish.jersey.server.ResourceConfig; import java.net.*; import java.net.http.*; import java.nio.charset.StandardCharsets; import java.util.*;
public class Main {
  static void say(String s) { System.out.println("RES " + s); } static void sec(String s) { System.out.println("SEC " + s); }
  static HttpClient hc = HttpClient.newHttpClient();
  static void call(String label, String method, String path, String body, String... headers) throws Exception { HttpRequest.Builder b = HttpRequest.newBuilder(URI.create("http://127.0.0.1:9780" + path)); for (int i = 0; i < headers.length; i += 2) b.header(headers[i], headers[i + 1]); b.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body));
    HttpResponse<String> r = hc.send(b.build(), HttpResponse.BodyHandlers.ofString()); say(label + " → HTTP " + r.statusCode() + ",响应体 " + r.body().replace("\n", " ")); String tr = r.headers().firstValue("X-Trace-Utf8").map(x -> new String(Base64.getDecoder().decode(x), StandardCharsets.UTF_8)).orElse(null); if (tr != null) for (String l : tr.split("\n")) say("      " + l); else say("      (没有 X-Trace:响应过滤器没有运行)"); }
  public static void main(String[] a) throws Exception {
    ResourceConfig rc = new ResourceConfig().register(Res.class).register(Filters.PreA.class).register(Filters.PreB.class).register(Filters.PostA.class).register(Filters.PostFirst.class).register(Filters.PostLast.class).register(Filters.RespFirst.class).register(Filters.RespSecond.class).register(Filters.TraceEmit.class).register(Filters.Boom.class).register(Filters.AuditFilter.class).register(Filters.BodyPeek.class);
    var server = JdkHttpServerFactory.createHttpServer(URI.create("http://127.0.0.1:9780/"), rc);
    try {
      sec("== 一:一个普通请求 GET /hello:各过滤器的执行顺序(过滤器注册的顺序是随意的,执行顺序由 @Priority 决定)");
      call("GET /hello", "GET", "/hello", null);
      sec("== 二:@PreMatching 能改写路径与方法,Post 过滤器能看到匹配到的资源方法");
      call("GET /legacy/hello(PreMatching A 改写路径)", "GET", "/legacy/hello", null); call("POST /echo + X-Method-Override(PreMatching B 把 POST 改成 PUT)", "POST", "/echo", "abc", "Content-Type", "text/plain", "X-Method-Override", "true");
      call("GET /nope(没有匹配的资源)", "GET", "/nope", null);
      sec("== 三:abortWith 与异常");
      call("GET /hello + X-Mode: deny(Post First 调用 abortWith)", "GET", "/hello", null, "X-Mode", "deny"); call("GET /hello + X-Mode: throw(Post Last 抛异常)", "GET", "/hello", null, "X-Mode", "throw"); call("GET /boom(资源抛异常,有 ExceptionMapper)", "GET", "/boom", null);
      sec("== 四:名字绑定与读取请求体");
      call("GET /audited(@Audited 绑定的过滤器)", "GET", "/audited", null); call("GET /hello(没有 @Audited,不会运行 Audit 过滤器)", "GET", "/hello", null);
      call("PUT /echo,过滤器读取了请求体但没放回", "PUT", "/echo", "payload-123", "Content-Type", "text/plain", "X-Peek", "consume"); call("PUT /echo,过滤器读取后又把字节放回", "PUT", "/echo", "payload-123", "Content-Type", "text/plain", "X-Peek", "restore");
    } finally { server.stop(0); }
  }
}
'''}
d = jdir('j282a'); write(d, {k: v for k, v in FILES.items()}); E = jenv('21'); (d / 'out').mkdir(exist_ok=True)
rc = subprocess.run(['javac', '-parameters', '-d', 'out', '-cp', CP, *[str(p) for p in d.rglob('*.java')]], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:3500]); sys.exit()
r = subprocess.run(['java', '-cp', 'out:' + CP, 'Main'], cwd=d, env=E, capture_output=True, text=True, timeout=180)
for l in (r.stdout + r.stderr).splitlines():
    if l.startswith('SEC '): print(l[4:])
    elif l.startswith('RES '): print('  ' + l[4:])
    elif r.returncode != 0 and not l.startswith('INFO') and l.strip(): print('  ! ' + l[:200])

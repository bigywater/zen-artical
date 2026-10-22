import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x16'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.io.*; import java.nio.charset.StandardCharsets; import java.nio.file.*; import java.util.*;
import org.springframework.core.io.*; import org.springframework.core.io.support.*; import org.springframework.context.support.*; import org.springframework.context.annotation.*;
public class Main {
  static String s(Resource r) { try { return r.getClass().getSimpleName() + " exists=" + r.exists() + (r.exists() ? " 内容=" + new String(r.getInputStream().readAllBytes(), StandardCharsets.UTF_8).strip() : ""); } catch (IOException e) { return r.getClass().getSimpleName() + " ✗ " + e.getClass().getSimpleName(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    switch (m) {
      case "prefix" -> {
        ResourceLoader rl = new DefaultResourceLoader(); Path tmp = Files.createTempFile("res", ".txt"); Files.writeString(tmp, "来自文件系统");
        System.out.println("RES classpath:conf/a.txt → " + s(rl.getResource("classpath:conf/a.txt")));
        System.out.println("RES file:<绝对路径> → " + s(rl.getResource(tmp.toUri().toString())));
        System.out.println("RES 没有前缀的 conf/a.txt(DefaultResourceLoader)→ " + s(rl.getResource("conf/a.txt")));
        try { System.out.println("RES 没有前缀的绝对路径 → " + s(rl.getResource(tmp.toString()))); } catch (Exception e) { System.out.println("RES 没有前缀的绝对路径 ✗ " + e); }
        System.out.println("RES 没有前缀的相对路径 other.txt(工作目录里没有这个文件)→ " + s(rl.getResource("other.txt")));
        System.out.println("RES https 前缀(只看类型,不联网)→ " + rl.getResource("https://example.com/x").getClass().getSimpleName());
        ApplicationContext0 c = new ApplicationContext0(); System.out.println("RES 在 ApplicationContext 里没有前缀的 conf/a.txt → " + s(c.getResource("conf/a.txt")) + "(上下文会按自己的类型决定;GenericApplicationContext 的默认是 classpath)");
        System.out.println("RES 在 ApplicationContext 里 file:conf/a.txt(相对工作目录)→ " + s(c.getResource("file:conf/a.txt")));
      }
      case "star" -> {
        PathMatchingResourcePatternResolver r = new PathMatchingResourcePatternResolver();
        for (String p : new String[]{"classpath:conf/*.txt", "classpath:conf/**/*.txt", "classpath:META-INF/spring.factories", "classpath*:META-INF/spring.factories", "classpath*:META-INF/spring/*.imports", "classpath:META-INF/spring/*.imports"}) {
          Resource[] rs = r.getResources(p); Set<String> src = new LinkedHashSet<>(); for (Resource x : rs) { String u = x.getURL().toString(); src.add(u.contains("!/") ? u.substring(u.lastIndexOf('/', u.indexOf("!/")) + 1, u.indexOf("!/")) + "!" + u.substring(u.indexOf("!/") + 1).replaceAll(".*/", ".../") : u.replaceAll(".*/out/", "out/")); }
          System.out.println("RES " + String.format("%-42s → %d 个:%s", p, rs.length, String.join(" ; ", src).length() > 330 ? String.join(" ; ", src).substring(0, 327) + "…" : String.join(" ; ", src))); }
      }
      case "jar" -> {
        Resource r = new ClassPathResource("conf/a.txt"); System.out.println("RES ClassPathResource(conf/a.txt) getFile() → " + tryF(r));
        Resource j = new ClassPathResource("META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports"); System.out.println("RES jar 里的资源 URL 前缀 → " + j.getURL().getProtocol() + ";isFile() = " + j.isFile() + ";getFile() → " + tryF(j) + ";getInputStream() 正常 = " + (j.getInputStream().read() >= 0));
        System.out.println("RES contentLength = " + j.contentLength() + ";lastModified > 0 = " + (j.lastModified() > 0) + ";getFilename() = " + j.getFilename());
      }
      case "write" -> {
        Path tmp = Files.createTempFile("w", ".txt"); WritableResource w = new FileSystemResource(tmp); try (OutputStream o = w.getOutputStream()) { o.write("写进去的".getBytes(StandardCharsets.UTF_8)); } System.out.println("RES FileSystemResource 可写:" + Files.readString(tmp) + ";isWritable = " + w.isWritable());
        Resource cp = new ClassPathResource("conf/a.txt"); System.out.println("RES ClassPathResource 实现 WritableResource?" + (cp instanceof WritableResource));
        Resource ba = new ByteArrayResource("内存里的".getBytes(StandardCharsets.UTF_8), "mem"); System.out.println("RES ByteArrayResource:" + s(ba) + ";getFilename = " + ba.getFilename());
        Resource in = new InputStreamResource(new ByteArrayInputStream("流".getBytes())); System.out.println("RES InputStreamResource 第一次读 " + in.getInputStream().readAllBytes().length + " 字节;第二次读 → " + tryRead(in)); }
    }
  }
  static String tryF(Resource r) { try { return r.getFile().toString().replaceAll(".*/out/", "out/"); } catch (Exception e) { return "✗ " + e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).replaceAll("\\S*/jtmp/\\S*", "<路径>").replaceAll("\\S*\\.m2\\S*", "<m2>"); } }
  static String tryRead(Resource r) { try { return r.getInputStream().readAllBytes().length + " 字节"; } catch (Exception e) { return "✗ " + e.getClass().getSimpleName() + ": " + e.getMessage(); } }
  static class ApplicationContext0 extends GenericApplicationContext { }
}
'''
b = sbuild('x16', {'src/demo/Main.java': MAIN, 'conf/a.txt': '来自 classpath 的 conf/a.txt\n', 'conf/sub/b.txt': 'b\n', 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
(b['dir'] / 'work').mkdir(exist_ok=True)
def run(m): r = srun(b, 'demo.Main', args=[m], cwd=b['dir'] / 'work'); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-700:]]
print('Spring Framework 7.0.9。Resource 抽象:classpath:、file:、classpath*:')
print('== 一:位置字符串的前缀决定用哪种 Resource(工作目录是一个空目录,里面没有 conf/a.txt 也没有 other.txt;conf/a.txt 只在 classpath 里)')
[print('  ' + l) for l in run('prefix')]
print('== 二:通配符。PathMatchingResourcePatternResolver 解析 classpath: 与 classpath*: 的区别')
[print('  ' + l) for l in run('star')]
print('== 三:类路径资源在 jar 里时')
[print('  ' + l) for l in run('jar')]
print('== 四:不同的 Resource 实现能做什么')
[print('  ' + l) for l in run('write')]

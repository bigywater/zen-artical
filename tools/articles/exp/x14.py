import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x14'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.util.*;
import org.springframework.beans.factory.annotation.Value; import org.springframework.context.annotation.*; import org.springframework.expression.*; import org.springframework.expression.spel.standard.SpelExpressionParser; import org.springframework.expression.spel.support.*;
import org.springframework.expression.spel.SpelCompilerMode; import org.springframework.expression.spel.SpelParserConfiguration;
public class Main {
  public static class User { public String name = "alice"; public int age = 30; public List<String> tags = List.of("a", "b", "c"); public Map<String, Integer> score = Map.of("math", 90); public User friend; public String hello(String x) { return "hello " + x + " from " + name; } private String secret = "s"; }
  public static class Holder { @Value("#{user.name.toUpperCase()}") String upper; @Value("#{user.age > 18 ? '成年' : '未成年'}") String adult; @Value("#{user.tags[1]}") String second; @Value("#{user.score['math'] + 10}") int math; @Value("#{systemProperties['user.language']}") String lang; @Value("#{T(java.lang.Math).max(3, 7)}") int max; @Value("#{user?.friend?.name}") String friendName; @Value("${missing:#{user.name}}") String dflt; }
  @Configuration static class Conf { @Bean User user() { return new User(); } @Bean Holder holder() { return new Holder(); } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    switch (m) {
      case "value" -> { AnnotationConfigApplicationContext c = new AnnotationConfigApplicationContext(Conf.class); Holder h = c.getBean(Holder.class);
        System.out.println("RES upper=" + h.upper + " | adult=" + h.adult + " | second=" + h.second + " | math+10=" + h.math + " | lang=" + h.lang + " | T(Math).max=" + h.max + " | user?.friend?.name=" + h.friendName + " | ${missing:#{user.name}}=" + h.dflt); }
      case "parse" -> {
        ExpressionParser p = new SpelExpressionParser(); User u = new User(); StandardEvaluationContext ctx = new StandardEvaluationContext(u);
        String[] es = {"name", "name.length()", "age * 2 + 1", "tags.size() > 2", "tags[0] + tags[2]", "score['math']", "hello('bob')", "friend?.name", "friend.name", "new String('x').toUpperCase()", "T(java.lang.System).currentTimeMillis() > 0", "tags.![toUpperCase()]", "tags.?[#this != 'b']", "'abc' matches '[a-c]+'", "#root.age", "secret", "nope"};
        for (String e : es) { String r; try { r = String.valueOf(p.parseExpression(e).getValue(ctx)); } catch (Exception ex) { r = "✗ " + ex.getClass().getSimpleName() + ": " + String.valueOf(ex.getMessage()).split("\n")[0]; } System.out.println("RES " + String.format("%-46s → %s", e, r.length() > 130 ? r.substring(0, 127) + "…" : r)); }
      }
      case "safe" -> {
        ExpressionParser p = new SpelExpressionParser();
        String evil = "T(java.lang.Runtime).getRuntime().availableProcessors()";
        Object a = p.parseExpression(evil).getValue(new StandardEvaluationContext()); System.out.println("RES StandardEvaluationContext 下 " + evil + " → " + a + "(能调任意类的静态方法)");
        try { Object b = p.parseExpression(evil).getValue(SimpleEvaluationContext.forReadOnlyDataBinding().build()); System.out.println("RES SimpleEvaluationContext 下 → " + b); } catch (Exception ex) { System.out.println("RES SimpleEvaluationContext.forReadOnlyDataBinding() 下同一个表达式 → ✗ " + ex.getClass().getSimpleName() + ": " + String.valueOf(ex.getMessage()).split("\n")[0]); }
        User u = new User(); try { System.out.println("RES SimpleEvaluationContext 读 name → " + p.parseExpression("name").getValue(SimpleEvaluationContext.forReadOnlyDataBinding().build(), u)); } catch (Exception ex) { System.out.println("RES SimpleEvaluationContext 读 name → ✗ " + ex.getMessage()); }
        try { p.parseExpression("name = 'x'").getValue(SimpleEvaluationContext.forReadOnlyDataBinding().build(), u); System.out.println("RES 只读上下文赋值成功?"); } catch (Exception ex) { System.out.println("RES 只读上下文里赋值 name = 'x' → ✗ " + ex.getClass().getSimpleName() + ": " + String.valueOf(ex.getMessage()).split("\n")[0]); }
      }
      case "perf" -> {
        ExpressionParser p = new SpelExpressionParser(); User u = new User(); StandardEvaluationContext ctx = new StandardEvaluationContext(u); int N = 1_000_000;
        // 1 每次都解析
        for (int i = 0; i < 20000; i++) p.parseExpression("age * 2 + 1").getValue(ctx); long t = System.nanoTime(); for (int i = 0; i < 200_000; i++) p.parseExpression("age * 2 + 1").getValue(ctx); double reparse = (System.nanoTime() - t) / 200_000.0;
        // 2 解析一次
        Expression ex = p.parseExpression("age * 2 + 1"); for (int i = 0; i < 100000; i++) ex.getValue(ctx); t = System.nanoTime(); for (int i = 0; i < N; i++) ex.getValue(ctx); double once = (System.nanoTime() - t) / (double) N;
        // 3 编译模式
        SpelExpressionParser cp = new SpelExpressionParser(new SpelParserConfiguration(SpelCompilerMode.IMMEDIATE, Main.class.getClassLoader())); Expression ce = cp.parseExpression("age * 2 + 1"); for (int i = 0; i < 100000; i++) ce.getValue(u); t = System.nanoTime(); for (int i = 0; i < N; i++) ce.getValue(u); double compiled = (System.nanoTime() - t) / (double) N;
        // 4 直接调用
        long s = 0; t = System.nanoTime(); for (int i = 0; i < N; i++) s += u.age * 2 + 1; double direct = (System.nanoTime() - t) / (double) N;
        System.out.println(String.format("RES 每次 parseExpression 加求值:%.0f ns/次;解析一次后反复求值:%.0f ns/次;编译模式(IMMEDIATE):%.1f ns/次;直接写 Java:%.2f ns/次(s=%d 防止被优化掉)", reparse, once, compiled, direct, s));
      }
    }
  }
}
'''
b = sbuild('x14', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m, jopts=()): r = srun(b, 'demo.Main', args=[m], jopts=jopts); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-600:]]
print('Spring Framework 7.0.9。Spring 表达式语言(SpEL)')
print('== 一:@Value("#{...}") 里的表达式(user 是容器里的一个 User Bean:name=alice、age=30、tags=[a,b,c]、score={math:90}、friend=null)')
[print('  ' + l) for l in run('value')]
print('== 二:SpEL 的语法一览:用 ExpressionParser 对一个 User 求值,左边是表达式,右边是结果或错误')
[print('  ' + l) for l in run('parse')]
print('== 三:谁来求值很重要。StandardEvaluationContext 可以访问任意类型和方法;SimpleEvaluationContext 是受限版本')
[print('  ' + l) for l in run('safe')]
print('== 四:求值的成本。同一个表达式 age * 2 + 1,四种做法各自每次要多少纳秒(单线程,预热之后)')
for _ in range(3): [print('  ' + l) for l in run('perf')]

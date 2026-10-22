import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x15'); CP = scp('org.springframework.boot:spring-boot-starter')
LOG = '<configuration><root level="OFF"/></configuration>'
MAIN = r'''
package demo;
import java.beans.PropertyEditorSupport; import java.math.BigDecimal; import java.time.Duration; import java.time.LocalDate; import java.util.Arrays; import java.util.List; import java.util.Locale;
import org.springframework.beans.*; import org.springframework.core.convert.*; import org.springframework.core.convert.converter.*; import org.springframework.core.convert.support.*;
import org.springframework.format.*; import org.springframework.format.annotation.*; import org.springframework.format.support.*; import org.springframework.format.datetime.standard.*;
import org.springframework.validation.*;
public class Main {
  public record Point(int x, int y) { }
  public enum Color { RED, GREEN }
  public static class Form { public LocalDate day; public BigDecimal price; public int count; public Color color; public Point pt; public List<Integer> nums; public Duration timeout;
    @DateTimeFormat(pattern = "yyyy/MM/dd") public LocalDate formatted; @NumberFormat(pattern = "#,##0.00") public BigDecimal money; }
  public static class StringToPoint implements Converter<String, Point> { public Point convert(String s) { String[] p = s.split(","); return new Point(Integer.parseInt(p[0].trim()), Integer.parseInt(p[1].trim())); } }
  public static class PointFormatter implements org.springframework.format.Formatter<Point> {
    public Point parse(String t, Locale l) { String[] p = t.replace("(", "").replace(")", "").split(";"); return new Point(Integer.parseInt(p[0]), Integer.parseInt(p[1])); }
    public String print(Point p, Locale l) { return "(" + p.x() + ";" + p.y() + ")"; } }
  static String t(java.util.concurrent.Callable<Object> c) { try { Object o = c.call(); return o == null ? "null" : o.getClass().getSimpleName() + ":" + (o.getClass().isArray() ? Arrays.toString((int[]) o) : o); } catch (Exception e) { Throwable r = e; return e.getClass().getSimpleName() + (e.getCause() != null ? " ← " + e.getCause().getClass().getSimpleName() : "") + ": " + String.valueOf(e.getMessage()).split("\n")[0]; } }
  public static void main(String[] args) throws Exception {
    String m = args[0];
    switch (m) {
      case "default" -> { DefaultConversionService cs = new DefaultConversionService();
        String[][] cases = {{"42", "Integer"}, {"true", "Boolean"}, {"yes", "Boolean"}, {"RED", "Color"}, {"red", "Color"}, {"1,2,3", "int[]"}, {"1,2,3", "List<Integer>"}, {"PT1M30S", "Duration"}, {"30s", "Duration"}, {"2026-10-19", "LocalDate"}, {"3.14", "BigDecimal"}, {"a", "Character"}, {"zh-CN", "Locale"}, {"1,2", "Point"}};
        for (String[] c : cases) {
          Object r; String desc;
          try { switch (c[1]) { case "Integer" -> r = cs.convert(c[0], Integer.class); case "Boolean" -> r = cs.convert(c[0], Boolean.class); case "Color" -> r = cs.convert(c[0], Color.class); case "int[]" -> r = cs.convert(c[0], int[].class);
            case "List<Integer>" -> r = cs.convert(c[0], TypeDescriptor.valueOf(String.class), new TypeDescriptor(org.springframework.core.ResolvableType.forClassWithGenerics(List.class, Integer.class), null, null)); case "Duration" -> r = cs.convert(c[0], Duration.class); case "LocalDate" -> r = cs.convert(c[0], LocalDate.class);
            case "BigDecimal" -> r = cs.convert(c[0], BigDecimal.class); case "Character" -> r = cs.convert(c[0], Character.class); case "Locale" -> r = cs.convert(c[0], Locale.class); default -> r = cs.convert(c[0], Point.class); }
            desc = r instanceof int[] ia ? "int[]" + Arrays.toString(ia) : r.getClass().getSimpleName() + ":" + r; }
          catch (Exception e) { desc = "✗ " + e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).split("\n")[0]; }
          System.out.println("RES " + String.format("%-8s → %-14s %s", "\"" + c[0] + "\"", c[1], desc.length() > 150 ? desc.substring(0, 147) + "…" : desc)); } }
      case "custom" -> { DefaultFormattingConversionService fs = new DefaultFormattingConversionService(); fs.addConverter(new StringToPoint());
        System.out.println("RES 注册 Converter<String, Point> 后 convert(\"3, 4\", Point) → " + fs.convert("3, 4", Point.class) + ";canConvert(String→Point) = " + fs.canConvert(String.class, Point.class) + ";canConvert(Point→String) = " + fs.canConvert(Point.class, String.class));
        System.out.println("RES Point → String(没有反向转换器):" + t(() -> fs.convert(new Point(1, 2), String.class)));
        DefaultFormattingConversionService f2 = new DefaultFormattingConversionService(); f2.addFormatter(new PointFormatter());
        System.out.println("RES 注册 Formatter<Point> 后:\"(5;6)\" → " + f2.convert("(5;6)", Point.class) + ";Point(5,6) → String:" + f2.convert(new Point(5, 6), String.class) + "(一个 Formatter 同时注册了两个方向)");
        DefaultConversionService d = new DefaultConversionService(); System.out.println("RES 没有注册任何转换器的 DefaultConversionService:" + t(() -> d.convert("1,2", Point.class))); }
      case "bind" -> {
        Form f = new Form(); DataBinder b = new DataBinder(f); b.initDirectFieldAccess(); DefaultFormattingConversionService fs = new DefaultFormattingConversionService(); fs.addConverter(new StringToPoint());
        DateTimeFormatterRegistrar r = new DateTimeFormatterRegistrar(); r.setDateFormatter(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd")); r.registerFormatters(fs); b.setConversionService(fs);
        MutablePropertyValues pv = new MutablePropertyValues(); pv.add("day", "2026-10-19"); pv.add("price", "9.90"); pv.add("count", "7"); pv.add("color", "GREEN"); pv.add("pt", "10, 20"); pv.add("nums", "4,5,6"); pv.add("formatted", "2026/10/19"); pv.add("money", "1,234.50"); pv.add("timeout", "PT5S");
        b.bind(pv); BindingResult br = b.getBindingResult();
        System.out.println("RES 绑定成功的字段:day=" + f.day + " price=" + f.price + " count=" + f.count + " color=" + f.color + " pt=" + f.pt + " nums=" + f.nums + " timeout=" + f.timeout + " formatted(@DateTimeFormat yyyy/MM/dd)=" + f.formatted + " money(@NumberFormat #,##0.00)=" + f.money + ";错误数 " + br.getErrorCount());
        Form g = new Form(); DataBinder b2 = new DataBinder(g); b2.initDirectFieldAccess(); b2.setConversionService(fs); MutablePropertyValues bad = new MutablePropertyValues(); bad.add("day", "19/10/2026"); bad.add("count", "seven"); bad.add("color", "BLUE"); bad.add("pt", "1;2"); bad.add("price", "9.9.9");
        b2.bind(bad); System.out.println("RES 全部写错的输入:错误数 " + b2.getBindingResult().getErrorCount());
        for (FieldError e : b2.getBindingResult().getFieldErrors()) System.out.println("RES   字段 " + e.getField() + ":code=" + e.getCode() + " 被拒绝的值=" + e.getRejectedValue());
        System.out.println("RES 出错的字段没有被赋值:g.day=" + g.day + " g.count=" + g.count + " g.color=" + g.color + "(保持默认值)");
      }
      case "editor" -> {
        class UpperEditor extends PropertyEditorSupport { public void setAsText(String s) { setValue(new Point(-1, -1)); } }
        Form f = new Form(); DataBinder b = new DataBinder(f); b.initDirectFieldAccess(); DefaultFormattingConversionService fs = new DefaultFormattingConversionService(); fs.addConverter(new StringToPoint()); b.setConversionService(fs);
        MutablePropertyValues pv = new MutablePropertyValues(); pv.add("pt", "3,4"); b.bind(pv); System.out.println("RES 只有 ConversionService:pt = " + f.pt);
        Form g = new Form(); DataBinder b2 = new DataBinder(g); b2.initDirectFieldAccess(); b2.setConversionService(fs); b2.registerCustomEditor(Point.class, new UpperEditor()); b2.bind(pv); System.out.println("RES 同时有 ConversionService 和给 Point 注册的 PropertyEditor(它总是产生 Point(-1,-1)):pt = " + g.pt + "(谁优先)");
      }
    }
  }
}
'''
b = sbuild('x15', {'src/demo/Main.java': MAIN, 'logback.xml': LOG}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
def run(m): r = srun(b, 'demo.Main', args=[m]); return [l[4:] for l in r['out'].splitlines() if l.startswith('RES ')] or [r['out'][-700:]]
print('Spring Framework 7.0.9。类型转换:ConversionService、Converter、Formatter、PropertyEditor 与数据绑定')
print('== 一:DefaultConversionService 开箱就会转什么。左边是输入字符串和目标类型,右边是结果或错误')
[print('  ' + l) for l in run('default')]
print('== 二:自己注册转换器。Converter<String, Point> 只管一个方向;Formatter<Point> 同时管 parse 与 print')
[print('  ' + l) for l in run('custom')]
print('== 三:DataBinder 绑定一个表单对象。(a)全部正确的输入;(b)全部写错的输入。看每个字段被转成了什么、错误是什么')
[print('  ' + l) for l in run('bind')]
print('== 四:PropertyEditor 与 ConversionService 同时存在时谁优先')
[print('  ' + l) for l in run('editor')]

import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j289'); R = {}
MAIN = r'''
import java.text.*; import java.time.*; import java.time.format.*; import java.util.*;
public class Main {
  static final Clock CAPTURED = Clock.systemDefaultZone();
  static void say(String s) { System.out.println("RES " + s); }
  static String cp(String s) { StringBuilder b = new StringBuilder(); for (char c : s.toCharArray()) { if (c > 127) b.append(String.format("\\u%04X", (int) c)); else b.append(c); } return b.toString(); }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("defaults")) {
      say("启动时 Locale.getDefault() = " + Locale.getDefault() + ",TimeZone.getDefault() = " + TimeZone.getDefault().getID() + ",user.language = " + System.getProperty("user.language") + ",user.timezone = " + System.getProperty("user.timezone"));
      String before = String.format("%.2f", 1234.5) + " | " + "title".toUpperCase() + " | " + NumberFormat.getInstance().format(1234.5);
      System.setProperty("user.language", "tr"); System.setProperty("user.country", "TR"); say("System.setProperty(user.language=tr, user.country=TR) 之后:Locale.getDefault() = " + Locale.getDefault() + ",\"title\".toUpperCase() = " + "title".toUpperCase() + "(没有变化,默认 Locale 在启动时读取并缓存)");
      System.setProperty("user.timezone", "Asia/Tokyo"); say("System.setProperty(user.timezone=Asia/Tokyo) 之后:TimeZone.getDefault() = " + TimeZone.getDefault().getID() + "(没有变化)");
      Locale.setDefault(Locale.forLanguageTag("tr-TR")); say("Locale.setDefault(tr-TR) 之后:Locale.getDefault() = " + Locale.getDefault() + ",\"title\".toUpperCase() = " + "title".toUpperCase() + ",String.format(\"%.2f\", 1234.5) = " + String.format("%.2f", 1234.5) + ",NumberFormat.getInstance().format(1234.5) = " + NumberFormat.getInstance().format(1234.5) + "(这些都是在调用时读取默认 Locale,立即生效)");
      Locale.setDefault(Locale.Category.FORMAT, Locale.GERMANY); say("只设置 Category.FORMAT 为 de-DE:getDefault(FORMAT) = " + Locale.getDefault(Locale.Category.FORMAT) + ",getDefault(DISPLAY) = " + Locale.getDefault(Locale.Category.DISPLAY) + ",getDefault() = " + Locale.getDefault() + ",String.format(\"%.2f\", 1234.5) = " + String.format("%.2f", 1234.5) + ",Locale.FRANCE.getDisplayCountry() = " + Locale.FRANCE.getDisplayCountry());
      Locale.setDefault(Locale.US); say("Locale.setDefault(Locale.US) 之后 \"title\".toUpperCase() = " + "title".toUpperCase() + ",String.format(\"%.2f\", 1234.5) = " + String.format("%.2f", 1234.5));
      say("显式传 Locale 就不依赖默认值:\"title\".toUpperCase(Locale.ROOT) = " + "title".toUpperCase(Locale.ROOT) + ",String.format(Locale.ROOT, \"%.2f\", 1234.5) = " + String.format(Locale.ROOT, "%.2f", 1234.5) + ",NumberFormat.getInstance(Locale.GERMANY).format(1234.5) = " + NumberFormat.getInstance(Locale.GERMANY).format(1234.5));
    } else if (mode.equals("tz")) {
      TimeZone.setDefault(TimeZone.getTimeZone("UTC")); Clock lateCaptured = Clock.systemDefaultZone(); Instant fixed = Instant.parse("2026-10-05T16:30:00Z");
      TimeZone.setDefault(TimeZone.getTimeZone("Asia/Tokyo")); say("默认时区 = Asia/Tokyo:ZoneId.systemDefault() = " + ZoneId.systemDefault() + ",LocalDateTime.ofInstant(fixed, ZoneId.systemDefault()) = " + LocalDateTime.ofInstant(fixed, ZoneId.systemDefault()) + ",new Date(fixed).toString() = " + new Date(fixed.toEpochMilli()));
      TimeZone.setDefault(TimeZone.getTimeZone("America/Los_Angeles")); say("默认时区改成 America/Los_Angeles:LocalDateTime.ofInstant(fixed, ZoneId.systemDefault()) = " + LocalDateTime.ofInstant(fixed, ZoneId.systemDefault()) + ";在 UTC 默认时区下创建并缓存的 Clock.systemDefaultZone().getZone() = " + lateCaptured.getZone() + ",用它算出的 LocalDateTime = " + LocalDateTime.ofInstant(fixed, lateCaptured.getZone()) + "(缓存了旧时区)");
      say("类静态字段 Clock CAPTURED 在 JVM 启动时创建(默认时区 " + CAPTURED.getZone() + "),现在默认时区是 " + ZoneId.systemDefault() + ",CAPTURED.getZone() = " + CAPTURED.getZone());
      say("LocalDateTime.now() 用的是调用时的默认时区,现在是几点:LocalDateTime.now().getHour() = " + LocalDateTime.now().getHour() + " 时,LocalDateTime.now(CAPTURED).getHour() = " + LocalDateTime.now(CAPTURED).getHour() + " 时,LocalDateTime.now(ZoneId.of(\"Asia/Tokyo\")).getHour() = " + LocalDateTime.now(ZoneId.of("Asia/Tokyo")).getHour() + " 时");
      ZoneId ny = ZoneId.of("America/New_York"); ZonedDateTime gap = ZonedDateTime.of(2026, 3, 8, 2, 30, 0, 0, ny); say("夏令时开始(2026-03-08 02:00 → 03:00):ZonedDateTime.of(2026-03-08 02:30 America/New_York) = " + gap + "(不存在的时间被推后 1 小时)");
      ZonedDateTime fall1 = ZonedDateTime.of(2026, 11, 1, 1, 30, 0, 0, ny); say("夏令时结束(2026-11-01 02:00 → 01:00):ZonedDateTime.of(2026-11-01 01:30 America/New_York) = " + fall1 + "(模糊的时间默认取较早的偏移量),withLaterOffsetAtOverlap() = " + fall1.withLaterOffsetAtOverlap());
      ZonedDateTime d0 = ZonedDateTime.of(2026, 3, 7, 12, 0, 0, 0, ny); say("跨夏令时的加法:2026-03-07 12:00 plusDays(1) = " + d0.plusDays(1) + ",plusHours(24) = " + d0.plusHours(24) + ",Duration.between(d0, d0.plusDays(1)) = " + Duration.between(d0, d0.plusDays(1)).toHours() + " 小时");
      LocalDate start = LocalDate.of(2026, 3, 8); say("一天的长度:2026-03-08 在 America/New_York 有 " + Duration.between(start.atStartOfDay(ny), start.plusDays(1).atStartOfDay(ny)).toHours() + " 小时,2026-11-01 有 " + Duration.between(LocalDate.of(2026, 11, 1).atStartOfDay(ny), LocalDate.of(2026, 11, 2).atStartOfDay(ny)).toHours() + " 小时");
      SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm z"); say("SimpleDateFormat 使用默认时区(现在是 America/Los_Angeles):" + sdf.format(new Date(fixed.toEpochMilli())) + ";另一个 SimpleDateFormat 在创建之后 TimeZone.setDefault(UTC)(已创建的实例不受影响):"); TimeZone.setDefault(TimeZone.getTimeZone("UTC")); say("    原来那个 sdf 仍然格式化为 " + sdf.format(new Date(fixed.toEpochMilli())) + ",新建的 SimpleDateFormat 格式化为 " + new SimpleDateFormat("yyyy-MM-dd HH:mm z").format(new Date(fixed.toEpochMilli())));
    } else if (mode.equals("data")) {
      Locale[] ls = {Locale.FRANCE, Locale.GERMANY, new Locale("pt", "BR"), Locale.forLanguageTag("hi-IN"), Locale.forLanguageTag("ar-EG"), Locale.JAPAN};
      for (Locale l : ls) say(String.format("%-6s NumberFormat(1234567.89) = %s;货币 = %s;日期 MEDIUM = %s;时间 SHORT = %s", l.toLanguageTag(), cp(NumberFormat.getInstance(l).format(1234567.89)), cp(NumberFormat.getCurrencyInstance(l).format(1234.5)), cp(DateFormat.getDateInstance(DateFormat.MEDIUM, l).format(new Date(0))), cp(DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT).withLocale(l).format(LocalTime.of(15, 4)))));
      say("java.locale.providers = " + System.getProperty("java.locale.providers") + ",Locale.US 的 \"Sep\" 缩写:" + new DateFormatSymbols(Locale.US).getShortMonths()[8] + ",en-GB 的 \"Sep\" 缩写:" + new DateFormatSymbols(Locale.UK).getShortMonths()[8]);
    }
  }
}
'''
d = jdir('j289a'); (d / 'Main.java').write_text(MAIN)
for jdk in ('17', '21', '27'):
    rc = subprocess.run([JDKS[jdk] + '/bin/javac', '-d', f'out{jdk}', 'Main.java'], cwd=d, env=jenv(jdk), capture_output=True, text=True)
    if rc.returncode: print(rc.stderr[:1500]); sys.exit()
def jv(mode, jdk='21', flags=(), env=None):
    r = subprocess.run([JDKS[jdk] + '/bin/java', *flags, '-cp', f'out{jdk}', 'Main', mode], cwd=d, env=jenv(jdk, **(env or {})), capture_output=True, text=True, timeout=120); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')] or [(r.stdout + r.stderr).strip()[:400]]
print('== 一:默认 Locale 在什么时候读取:启动时缓存,还是调用时读取(JDK 21,以 -Duser.language=en -Duser.country=US -Duser.timezone=UTC 启动)')
for l in jv('defaults', flags=('-Duser.language=en', '-Duser.country=US', '-Duser.timezone=UTC')): print('  ' + l)
print('== 二:时区:默认时区的缓存、夏令时的缺口与重叠、一天不是 24 小时(JDK 21)')
for l in jv('tz', flags=('-Duser.timezone=UTC',)): print('  ' + l)
print('== 三:同一段代码在 JDK 17 / 21 / 27 上的本地化输出(Unicode 码点转义显示不可见字符,\\\\u202F 是窄不换行空格,\\\\u00A0 是不换行空格)')
outs = {}
for jdk in ('17', '21', '27'):
    outs[jdk] = jv('data', jdk, ('-Duser.language=en', '-Duser.country=US')); print(f'  [JDK {jdk}]'); [print('      ' + l[:420]) for l in outs[jdk]]
diff = [i for i in range(len(outs['21'])) if i < len(outs['17']) and outs['21'][i] != outs['17'][i]]; diff2 = [i for i in range(len(outs['21'])) if i < len(outs['27']) and outs['21'][i] != outs['27'][i]]
print(f'  JDK 17 与 JDK 21 输出不同的行数 {len(diff)} / {len(outs["21"])};JDK 21 与 JDK 27 不同的行数 {len(diff2)} / {len(outs["21"])}')
print('  [JDK 21 + -Djava.locale.providers=COMPAT]'); [print('      ' + l[:420]) for l in jv('data', '21', ('-Duser.language=en', '-Duser.country=US', '-Djava.locale.providers=COMPAT'))]

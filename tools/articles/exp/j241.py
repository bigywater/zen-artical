import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j241'); R = {}
MAIN = r'''
import java.time.*; import java.time.temporal.ChronoUnit; import java.util.*; import java.util.function.*;
public class Main {
  // ---------- 一:依赖当前时间的夹具 ----------
  static long businessDays(LocalDate from, LocalDate to) { long n = 0; for (LocalDate d = from.plusDays(1); !d.isAfter(to); d = d.plusDays(1)) if (d.getDayOfWeek() != DayOfWeek.SATURDAY && d.getDayOfWeek() != DayOfWeek.SUNDAY) n++; return n; }
  static boolean testWithinOneMonth(LocalDate today) { LocalDate created = today.minusDays(30); return ChronoUnit.MONTHS.between(created, today) < 1; }   // 夹具:30 天前,断言“一个月以内”
  static boolean testYesterdayIsOneBusinessDay(LocalDate today) { return businessDays(today.minusDays(1), today) == 1; }                                     // 夹具:昨天,断言“相差 1 个工作日”
  static boolean testFixedDate1(LocalDate ignored) { LocalDate today = LocalDate.of(2025, 4, 16), created = today.minusDays(30); return ChronoUnit.MONTHS.between(created, today) < 1; }
  static boolean testFixedDate2(LocalDate ignored) { LocalDate today = LocalDate.of(2025, 4, 16); return businessDays(today.minusDays(1), today) == 1; }
  // ---------- 二:随机夹具 ----------
  static long expectedPrice(int qty) { long base = qty * 1000L; return qty >= 50 ? base * 95 / 100 : base; }
  static long buggyPrice(int qty) { long base = qty * 1000L; long p = qty >= 50 ? base * 95 / 100 : base; if (qty >= 97) p -= 5; return p; }   // 一个只在 97..100 出现的 bug
  static boolean randomTest(long seed) { Random r = new Random(seed); int qty = 1 + r.nextInt(100); return buggyPrice(qty) == expectedPrice(qty); }
  // ---------- 三:订单夹具 ----------
  enum Tier { STANDARD(0), SILVER(2), GOLD(10); final int pct; Tier(int p) { pct = p; } }
  record Order(Tier tier, String country, long itemCents, String coupon, boolean gift) {
    Order withTier(Tier t) { return new Order(t, country, itemCents, coupon, gift); } Order withCountry(String c) { return new Order(tier, c, itemCents, coupon, gift); }
    Order withItem(long c) { return new Order(tier, country, c, coupon, gift); } Order withCoupon(String c) { return new Order(tier, country, itemCents, c, gift); } Order withGift(boolean g) { return new Order(tier, country, itemCents, coupon, g); } }
  static Map<String, Long> SHIP = new HashMap<>(); static Tier DEFAULT_TIER = Tier.STANDARD; static String DEFAULT_COUNTRY = "CN"; static long DEFAULT_ITEM = 10000;
  static void resetConfig() { SHIP.clear(); SHIP.put("CN", 1000L); SHIP.put("DE", 2500L); DEFAULT_TIER = Tier.STANDARD; DEFAULT_COUNTRY = "CN"; DEFAULT_ITEM = 10000; }
  static Order base() { return new Order(DEFAULT_TIER, DEFAULT_COUNTRY, DEFAULT_ITEM, null, false); }
  record Bd(long items, long discount, long shipping, long gift, long total) {}
  static Bd price(Order o) { long disc = o.itemCents() * o.tier().pct / 100; if ("SAVE10".equals(o.coupon())) disc += o.itemCents() / 10; long ship = o.itemCents() >= 15000 ? 0 : SHIP.get(o.country()); long g = o.gift() ? 500 : 0; return new Bd(o.itemCents(), disc, ship, g, o.itemCents() - disc + ship + g); }
  // 设计 A:每个测试断言“总价”的绝对值(夹具默认值烤进了期望值)。设计 B:每个测试只断言它要验证的那一项。
  static Map<String, BooleanSupplier> designA() { Map<String, BooleanSupplier> m = new LinkedHashMap<>();
    m.put("A1 默认订单总价", () -> price(base()).total() == 11000); m.put("A2 金牌 9 折", () -> price(base().withTier(Tier.GOLD)).total() == 10000);
    m.put("A3 优惠券 SAVE10", () -> price(base().withCoupon("SAVE10")).total() == 10000); m.put("A4 满 150 免运费", () -> price(base().withItem(15000)).total() == 15000);
    m.put("A5 德国运费", () -> price(base().withCountry("DE")).total() == 12500); m.put("A6 礼品包装 +5", () -> price(base().withGift(true)).total() == 11500); return m; }
  static Map<String, BooleanSupplier> designB() { Map<String, BooleanSupplier> m = new LinkedHashMap<>();
    m.put("B1 默认订单商品额", () -> price(base()).items() == DEFAULT_ITEM); m.put("B2 金牌折扣 = 商品额的 10%", () -> price(base().withTier(Tier.GOLD)).discount() == DEFAULT_ITEM / 10);
    m.put("B3 优惠券折扣 = 商品额的 10%", () -> price(base().withCoupon("SAVE10")).discount() == DEFAULT_ITEM / 10); m.put("B4 满 150 运费为 0", () -> price(base().withItem(15000)).shipping() == 0);
    m.put("B5 德国运费 = 德国运费表", () -> price(base().withCountry("DE")).shipping() == SHIP.get("DE")); m.put("B6 礼品包装 = 500", () -> price(base().withGift(true)).gift() == 500); return m; }
  static List<String> failures(Map<String, BooleanSupplier> m) { List<String> f = new ArrayList<>(); for (var e : m.entrySet()) { boolean ok; try { ok = e.getValue().getAsBoolean(); } catch (Exception x) { ok = false; } if (!ok) f.add(e.getKey().split(" ")[0]); } return f; }
  // ---------- 四:夹具成本 ----------
  record Line(int sku, long cents, String name) {} record BigOrder(List<Line> lines, Map<String, String> meta) {}
  static BigOrder heavy() { List<Line> l = new ArrayList<>(); for (int i = 0; i < 500; i++) l.add(new Line(i, 100L + i, "商品-" + i)); Map<String, String> m = new HashMap<>(); for (int i = 0; i < 100; i++) m.put("k" + i, "v" + i); return new BigOrder(l, m); }
  static BigOrder light() { return new BigOrder(List.of(new Line(1, 100, "商品-1")), Map.of()); }
  static long sink; static final Object[] keep = new Object[64];
  public static void main(String[] a) {
    System.out.println("== 一:夹具里用“现在”:同一个测试在 2024-01-01 到 2025-12-31 的每一天各跑一次(用注入的 Clock 模拟“今天”)");
    LocalDate d0 = LocalDate.of(2024, 1, 1); int days = 0; List<LocalDate> f1 = new ArrayList<>(), f2 = new ArrayList<>(), g1 = new ArrayList<>(), g2 = new ArrayList<>();
    for (LocalDate d = d0; !d.isAfter(LocalDate.of(2025, 12, 31)); d = d.plusDays(1)) { days++; if (!testWithinOneMonth(d)) f1.add(d); if (!testYesterdayIsOneBusinessDay(d)) f2.add(d); if (!testFixedDate1(d)) g1.add(d); if (!testFixedDate2(d)) g2.add(d); }
    Map<DayOfWeek, Long> wk = new TreeMap<>(); for (LocalDate d : f2) wk.merge(d.getDayOfWeek(), 1L, Long::sum); Map<Month, Long> mo = new TreeMap<>(); for (LocalDate d : f1) mo.merge(d.getMonth(), 1L, Long::sum);
    System.out.println("  共 " + days + " 天");
    System.out.println("  夹具 now().minusDays(30),断言“相差不到 1 个月”:失败 " + f1.size() + " 天;集中在 " + mo + ";例如 " + f1.subList(0, 3));
    System.out.println("  夹具 now().minusDays(1),断言“相差 1 个工作日”:失败 " + f2.size() + " 天;按星期 " + wk + ";例如 " + f2.subList(0, 3));
    System.out.println("  同样两个测试改用固定日期 2025-04-16(星期三):失败 " + g1.size() + " + " + g2.size() + " 天");
    System.out.println("== 二:夹具里用随机数(数量 1..100,代码在数量 >= 97 时有 bug)");
    int fails = 0; List<Long> failSeeds = new ArrayList<>(); for (long s = 1; s <= 1000; s++) if (!randomTest(s)) { fails++; if (failSeeds.size() < 5) failSeeds.add(s); }
    System.out.println("  种子 1..1000 各跑一次:失败 " + fails + " 次(" + (fails / 10.0) + "%);前 5 个失败种子 " + failSeeds);
    long seed = failSeeds.get(0); int same = 0; for (int i = 0; i < 10; i++) if (!randomTest(seed)) same++; System.out.println("  记录下失败种子 " + seed + " 后重放 10 次:失败 " + same + " 次(每次数量都是 " + (1 + new Random(seed).nextInt(100)) + ")");
    Random trial = new Random(42); StringBuilder sb = new StringBuilder();
    for (int n : new int[]{1, 3, 10, 50, 100}) { int found = 0, T = 4000; for (int t = 0; t < T; t++) { boolean hit = false; for (int k = 0; k < n && !hit; k++) if (!randomTest(trial.nextLong())) hit = true; if (hit) found++; } sb.append("连续跑 " + n + " 次发现 bug 的概率 " + String.format("%.1f%%", 100.0 * found / T) + ";"); }
    System.out.println("  每个测试用全新随机种子," + sb);
    System.out.println("== 三:“默认夹具”的值被烤进期望值:改一个默认值/配置,6 个测试里坏几个?(设计 A 断言总价,设计 B 只断言各自要验证的那一项)");
    resetConfig(); System.out.println("  基线:A 失败 " + failures(designA()) + ",B 失败 " + failures(designB()));
    String[] names = {"国内运费 1000 → 1200", "默认国家 CN → DE", "默认商品额 10000 → 12000", "默认等级 STANDARD → SILVER"};
    for (int c = 0; c < 4; c++) { resetConfig(); switch (c) { case 0 -> SHIP.put("CN", 1200L); case 1 -> DEFAULT_COUNTRY = "DE"; case 2 -> DEFAULT_ITEM = 12000; case 3 -> DEFAULT_TIER = Tier.SILVER; }
      List<String> fa = failures(designA()), fb = failures(designB()); System.out.println("  " + names[c] + ":A 失败 " + fa.size() + " 个 " + fa + ";B 失败 " + fb.size() + " 个 " + fb); }
    System.out.println("== 四:夹具的构造成本:每个测试的 @BeforeEach 构造一个“什么都有”的订单(500 行商品 + 100 项元数据)与一个只含一行的订单");
    for (int w = 0; w < 20000; w++) { keep[w & 63] = heavy(); keep[(w + 1) & 63] = light(); }
    int N = 5000; long[] h = new long[7], l = new long[7];
    for (int r = 0; r < 7; r++) { long t0 = System.nanoTime(); for (int i = 0; i < N; i++) keep[i & 63] = heavy(); h[r] = System.nanoTime() - t0; t0 = System.nanoTime(); for (int i = 0; i < N; i++) keep[i & 63] = light(); l[r] = System.nanoTime() - t0; }
    Arrays.sort(h); Arrays.sort(l); double hu = h[3] / (double) N / 1000, lu = l[3] / (double) N / 1000;
    System.out.println(String.format("  %d 个测试各构造一次(7 轮取中位数):重夹具每次 %.1f 微秒(共 %.0f ms),轻夹具每次 %.2f 微秒(共 %.1f ms),约 %.0f 倍", N, hu, h[3] / 1e6, lu, l[3] / 1e6, hu / lu));
    System.out.println(String.format("  按 2 万个测试估算:重夹具 %.0f ms,轻夹具 %.0f ms(只是对象构造,不含数据库或文件)", hu * 20000 / 1000, lu * 20000 / 1000));
    if (sink == 42 || keep[0] == null) System.out.println();
  }
}
'''
r = jrun('j241a', {'Main.java': MAIN}, timeout=180)
if r['crc'] != 0: print(r['cout'][:2500]); sys.exit()
print(r['out'])

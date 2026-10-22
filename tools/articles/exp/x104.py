import sys, os, re, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spl import *
tee('x104'); CP = scp('org.springframework.security:spring-security-crypto', 'org.bouncycastle:bcprov-jdk18on', 'commons-logging:commons-logging')
MAIN = r'''
package demo;
import org.springframework.security.crypto.bcrypt.*; import org.springframework.security.crypto.factory.PasswordEncoderFactories; import org.springframework.security.crypto.password.*; import org.springframework.security.crypto.argon2.Argon2PasswordEncoder; import org.springframework.security.crypto.scrypt.SCryptPasswordEncoder; import java.util.*;
public class Main {
  static void r(String s) { System.out.println("RES " + s); }
  static double med(Runnable c, int n) { double[] x = new double[n]; for (int i = 0; i < n; i++) { long t = System.nanoTime(); c.run(); x[i] = (System.nanoTime() - t) / 1e6; } Arrays.sort(x); return x[n / 2]; }
  static String ex(Throwable t) { return t.getClass().getSimpleName() + ":" + t.getMessage(); }
  public static void main(String[] a) {
    r("== 一:BCrypt 的 strength(cost)与耗时");
    for (int i = 0; i < 3; i++) new BCryptPasswordEncoder(10).encode("warm");
    BCryptPasswordEncoder d = new BCryptPasswordEncoder(); String h1 = d.encode("secret"), h2 = d.encode("secret");
    r("  默认 strength = 10;同一个密码编码两次:" + h1 + " 与 " + h2 + ";长度 " + h1.length() + ";两个值相同:" + h1.equals(h2) + ";都能 matches:" + (d.matches("secret", h1) && d.matches("secret", h2)));
    for (int s = 4; s <= 14; s += 2) { BCryptPasswordEncoder e = new BCryptPasswordEncoder(s); String h = e.encode("secret"); double en = med(() -> e.encode("secret"), s >= 13 ? 3 : 5), mt = med(() -> e.matches("secret", h), s >= 13 ? 3 : 5); r(String.format("  strength=%2d:encode 中位 %7.1f ms,matches 中位 %7.1f ms,哈希前缀 %s", s, en, mt, h.substring(0, 7))); }
    r("  strength 取值范围:");
    for (int s : new int[]{3, 32}) { try { new BCryptPasswordEncoder(s).encode("x"); r("    strength=" + s + ":可以"); } catch (Throwable t) { r("    strength=" + s + ":" + ex(t)); } }
    r("== 二:DelegatingPasswordEncoder");
    PasswordEncoder dp = PasswordEncoderFactories.createDelegatingPasswordEncoder(); String dh = dp.encode("secret");
    r("  encode(\"secret\") = " + dh);
    r("  matches 带前缀的各种哈希(同一个明文 secret):");
    Map<String, String> m = new LinkedHashMap<>(); m.put("{noop}", "{noop}secret"); m.put("{bcrypt}", "{bcrypt}" + new BCryptPasswordEncoder().encode("secret")); m.put("{pbkdf2@SpringSecurity_v5_8}", "{pbkdf2@SpringSecurity_v5_8}" + Pbkdf2PasswordEncoder.defaultsForSpringSecurity_v5_8().encode("secret")); m.put("{scrypt@SpringSecurity_v5_8}", "{scrypt@SpringSecurity_v5_8}" + SCryptPasswordEncoder.defaultsForSpringSecurity_v5_8().encode("secret")); m.put("{argon2@SpringSecurity_v5_8}", "{argon2@SpringSecurity_v5_8}" + Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8().encode("secret"));
    m.forEach((k, v) -> r("    " + k + " → matches=" + dp.matches("secret", v) + ",哈希长度 " + v.length()));
    r("  没有前缀的哈希(例如直接从旧库里读出来的 BCrypt):");
    try { r("    matches → " + dp.matches("secret", new BCryptPasswordEncoder().encode("secret"))); } catch (Throwable t) { r("    抛 " + ex(t)); }
    DelegatingPasswordEncoder dpe = (DelegatingPasswordEncoder) PasswordEncoderFactories.createDelegatingPasswordEncoder(); dpe.setDefaultPasswordEncoderForMatches(new BCryptPasswordEncoder());
    r("    setDefaultPasswordEncoderForMatches(BCrypt) 之后 matches → " + dpe.matches("secret", new BCryptPasswordEncoder().encode("secret")));
    r("  upgradeEncoding(是否需要用新参数重新编码):");
    r("    {bcrypt} strength 4 → " + dp.upgradeEncoding("{bcrypt}" + new BCryptPasswordEncoder(4).encode("secret")) + ";{bcrypt} strength 10(默认)→ " + dp.upgradeEncoding(dh) + ";{noop} → " + dp.upgradeEncoding("{noop}secret") + ";{bcrypt} strength 12 → " + dp.upgradeEncoding("{bcrypt}" + new BCryptPasswordEncoder(12).encode("secret")));
    r("== 三:边界");
    BCryptPasswordEncoder e = new BCryptPasswordEncoder(4); String p72 = "a".repeat(72), p80 = "a".repeat(72) + "TAIL-DIFFERENT"; String h72 = e.encode(p72);
    try { r("  只在第 72 个字节之后不同的两个密码:matches(" + p72.length() + " 字节原文, 哈希)=" + e.matches(p72, h72) + ",matches(" + p80.length() + " 字节、前 72 字节相同, 同一个哈希)=" + e.matches(p80, h72)); } catch (Throwable t) { r("  72 字节以上的密码:抛 " + ex(t)); }
    try { e.encode("a".repeat(73)); r("  encode(73 字节的密码):成功"); } catch (Throwable t) { r("  encode(73 字节的密码):抛 " + ex(t)); }
    try { e.matches(null, h72); r("  matches(null, 哈希) 成功"); } catch (Throwable t) { r("  matches(null, 哈希):抛 " + ex(t)); }
    try { r("  matches(\"\", 空密码的哈希):" + e.matches("", e.encode(""))); } catch (Throwable t) { r("  空密码:抛 " + ex(t)); }
    try { r("  matches(\"secret\", \"not-a-hash\"):" + e.matches("secret", "not-a-hash")); } catch (Throwable t) { r("  matches(\"secret\", \"not-a-hash\"):抛 " + ex(t)); }
    r("== 四:几种算法的默认参数,编码耗时与哈希长度(各取 5 次中位数)");
    Object[][] algs = {{"BCrypt 默认(strength 10)", new BCryptPasswordEncoder()}, {"Pbkdf2 defaultsForSpringSecurity_v5_8", Pbkdf2PasswordEncoder.defaultsForSpringSecurity_v5_8()}, {"SCrypt defaultsForSpringSecurity_v5_8", SCryptPasswordEncoder.defaultsForSpringSecurity_v5_8()}, {"Argon2 defaultsForSpringSecurity_v5_8", Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8()}};
    for (Object[] al : algs) { PasswordEncoder pe = (PasswordEncoder) al[1]; pe.encode("warm"); String h = pe.encode("secret"); double en = med(() -> pe.encode("secret"), 5), mt = med(() -> pe.matches("secret", h), 5); r(String.format("  %s:encode 中位 %.1f ms,matches 中位 %.1f ms,哈希长度 %d", al[0], en, mt, h.length())); }
  }
}
'''
b = sbuild('x104', {'src/demo/Main.java': MAIN}, CP)
if b['crc'] != 0: print(b['cout']); sys.exit()
print('Spring Security 7 的 spring-security-crypto(随 Boot 4.0.8 管理版本)+ BouncyCastle(Argon2 需要);本机 macOS arm64 / OpenJDK 21;单进程,各项取中位数')
r = srun(b, 'demo.Main', timeout=600)
for l in res(r): print(l)
if not res(r): print(r['out'][-2500:])

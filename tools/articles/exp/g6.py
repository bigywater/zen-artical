import sys, os, re, time, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g6')
SRC = r'''
package main

import (
	"fmt"
	"sort"
	"testing"
	"unicode/utf16"
	"unicode/utf8"
)

var sink int

func main() {
	s := "a好😀é"
	fmt.Printf("  s = %q:len(s) = %d 字节,utf8.RuneCountInString = %d 个 rune\n", s, len(s), utf8.RuneCountInString(s))
	fmt.Print("  按下标遍历 for i := 0; i < len(s); i++:")
	for i := 0; i < len(s); i++ {
		fmt.Printf(" s[%d]=0x%02x", i, s[i])
	}
	fmt.Println()
	fmt.Print("  for i, r := range s:")
	for i, r := range s {
		fmt.Printf(" [i=%d r=U+%04X %q 占 %d 字节]", i, r, r, utf8.RuneLen(r))
	}
	fmt.Println()
	rs := []rune(s)
	fmt.Printf("  []rune(s):len = %d,rs[2] = U+%04X;string(rs[1:3]) = %q\n", len(rs), rs[2], string(rs[1:3]))
	for _, r := range []rune{'a', 'é', '好', '😀', 0x10FFFF, 0xD800, 0x110000} {
		buf := make([]byte, 4)
		n := utf8.EncodeRune(buf, r)
		fmt.Printf("  EncodeRune(U+%04X) → %d 字节 % x;utf8.ValidRune = %v\n", r, n, buf[:n], utf8.ValidRune(r))
	}
	fmt.Printf("  'a' 的类型是 %T(无类型 rune 常量,默认类型 int32);\"😀\" 在 UTF-16 里是 %X\n", 'a', utf16.Encode([]rune("😀")))

	fmt.Println("== 二:非法 UTF-8 与截断:range 不会 panic,而是给出 U+FFFD,宽度 1")
	bad := "ab\xffcd\xe5\xa5"
	fmt.Printf("  bad = %q(含孤立的 0xff 和被截断的 0xe5 0xa5);ValidString = %v\n", bad, utf8.ValidString(bad))
	fmt.Print("  for i, r := range bad:")
	for i, r := range bad {
		fmt.Printf(" [i=%d U+%04X]", i, r)
	}
	fmt.Println()
	fmt.Printf("  []rune(bad) 的长度 = %d(每个坏字节各变成一个 U+FFFD);string([]rune(bad)) = %q,与 bad 相等?%v\n", len([]rune(bad)), string([]rune(bad)), string([]rune(bad)) == bad)
	h := "好"
	fmt.Printf("  \"好\" 是 %d 字节;h[:2] 是否合法 UTF-8?%v(在字节边界上切开了一个字符)\n", len(h), utf8.ValidString(h[:2]))
	t := "你好世界"
	cut := func(s string, n int) string {
		if len(s) <= n { return s }
		for n > 0 && !utf8.RuneStart(s[n]) { n-- }
		return s[:n]
	}
	fmt.Printf("  按字节截 \"你好世界\"[:4] = %q(合法?%v);用 RuneStart 回退的 cut(s, 4) = %q(合法?%v)\n", t[:4], utf8.ValidString(t[:4]), cut(t, 4), utf8.ValidString(cut(t, 4)))
	fmt.Printf("  string(rune(0xD800)) = %q;string(rune(-1)) = %q\n", string(rune(0xD800)), string(rune(-1)))

	fmt.Println("== 三:“看起来一样”的字符串:预组合的 é 与 e + 组合重音符号")
	e1, e2 := "é", "é"
	fmt.Printf("  %q 与 %q:显示相同,== 比较 %v;len = %d / %d 字节,rune 数 = %d / %d\n", e1, e2, e1 == e2, len(e1), len(e2), utf8.RuneCountInString(e1), utf8.RuneCountInString(e2))
	flag := "🇨🇳"
	fmt.Printf("  国旗 \"🇨🇳\":%d 字节,%d 个 rune(两个区域指示符),len([]rune) 不等于看到的字符数\n", len(flag), utf8.RuneCountInString(flag))
	fam := "👨‍👩‍👧"
	fmt.Printf("  家庭 emoji(用零宽连接符拼成):%d 字节,%d 个 rune\n", len(fam), utf8.RuneCountInString(fam))

	fmt.Println("== 四:遍历方式的成本:1000 个汉字(3000 字节)的字符串,7 轮取中位数")
	big := make([]rune, 1000)
	for i := range big { big[i] = rune(0x4e00 + i) }
	str := string(big)
	bench("for range str(逐个 rune)", func(b *testing.B) { for i := 0; i < b.N; i++ { n := 0; for _, r := range str { n += int(r) }; sink += n } })
	bench("for i := 0; i < len(str); i++(逐字节)", func(b *testing.B) { for i := 0; i < b.N; i++ { n := 0; for j := 0; j < len(str); j++ { n += int(str[j]) }; sink += n } })
	bench("for range []rune(str)(先转换)", func(b *testing.B) { for i := 0; i < b.N; i++ { n := 0; for _, r := range []rune(str) { n += int(r) }; sink += n } })
	bench("utf8.RuneCountInString(str)", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += utf8.RuneCountInString(str) } })
	bench("len([]rune(str))", func(b *testing.B) { for i := 0; i < b.N; i++ { sink += len([]rune(str)) } })
	fmt.Printf("  AllocsPerRun:for range str %.0f 次;[]rune(str) 后遍历 %.0f 次;len([]rune(str)) %.0f 次\n",
		testing.AllocsPerRun(100, func() { n := 0; for _, r := range str { n += int(r) }; sink += n }),
		testing.AllocsPerRun(100, func() { n := 0; for _, r := range []rune(str) { n += int(r) }; sink += n }),
		testing.AllocsPerRun(100, func() { sink += len([]rune(str)) }))
}
''' + GBENCH
print('== 一:一个字符串的字节与 rune(Go 1.27.1,arm64):下标遍历看到字节,range 看到 rune')
r = grun('u1', {'main.go': SRC})
print(r['out'] if r['crc'] == 0 else r['cout'])
V = r'''
package main

import "fmt"

func main() {
	n := 65
	s := string(n)
	fmt.Println(s)
}
'''
rv = grun('u2', {'main.go': V})
rc, o = go(rv['d'], 'vet', '.')
print(f'== 五:go vet 对 string(int) 的警告(把整数当 rune 转字符串是常见的误用)\n  源码:n := 65; s := string(n)\n  go build:rc={0 if rv["crc"] == 0 else rv["crc"]},运行输出 {rv["out"]!r};go vet:rc={rc},输出:{o}')

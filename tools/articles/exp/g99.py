import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g99')
FILES = {
'v.go': '''
package lab

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"sync"
	"time"
)

type T struct {
	mu sync.Mutex
	n  int
}

func Printf() {
	fmt.Printf("%d\\n", "字符串")          // printf: 动词与参数类型不符
	fmt.Println("done\\n")                // printf: Println 末尾带了换行
	fmt.Printf("%s %s\\n", "只给了一个")    // printf: 参数个数不够
}

func CopyLock(t T) int { return t.n }   // copylocks: 按值传递含 Mutex 的结构体

func Lost() {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second) // lostcancel: 有的路径上没调用 cancel
	if time.Now().Unix()%2 == 0 {
		cancel()
	}
	_ = ctx
}

func SelfAssign() {
	x := 1
	x = x // assign: 自赋值
	_ = x
}

func Unreachable() int {
	return 1
	fmt.Println("永远执行不到") // unreachable
	return 0
}

func Tags() {
	type S struct {
		A int `json:"a" json:"b"` // structtag: 重复的 key
		B int `json: "b"`          // structtag: 冒号后有空格
	}
	_ = S{}
}

func Shift(x int32) int32 { return x << 40 } // shift: 位移量超过类型宽度

func Bools(a int) bool { return a == 1 || a == 1 } // bools: 重复的条件

func StrInt(n int) string { return string(n) } // stringintconv: int 转 string 是码点

func HTTP() {
	resp, err := http.Get("http://example.invalid")
	defer resp.Body.Close() // httpresponse: 在检查 err 之前就 defer
	if err != nil {
		return
	}
}

func ErrAs(err error) bool {
	var e os.PathError
	return errors.As(err, e) // errorsas: 第二个参数必须是指针
}

func UnusedResult() {
	fmt.Sprintf("%d", 1) // unusedresult: 结果被丢弃
}

func WG() {
	var wg sync.WaitGroup
	for i := 0; i < 3; i++ {
		go func() {
			wg.Add(1) // waitgroup: Add 应该在启动 goroutine 之前调用
			defer wg.Done()
		}()
	}
	wg.Wait()
}
''',
'v_test.go': '''
package lab

import "testing"

func TestOK(t *testing.T) {}
''',
}
d = gdir('vt1'); write(d, FILES); mod(d, go='1.27')
rc, o = go(d, 'vet', './...')
print('== 一:一个故意写了各种问题的文件,go vet 的输出(Go 1.27.1)')
msgs = [re.sub(r'^\./', '', l) for l in o.split('\n') if l.strip() and not l.startswith('#')]
print(f'  退出码 {rc};共 {len(msgs)} 条报告:')
for l in msgs: print('    ' + l.replace('v.go:', 'v.go 第 ').replace(': ', ' 行: ', 1) if False else '    ' + l)
print('== 二:vet 里有多少个检查器(go tool vet help)')
r = subprocess.run([GO, 'tool', 'vet', 'help'], capture_output=True, text=True, env=genv(), cwd=d)
t = r.stdout + r.stderr
names = re.findall(r'^\s{4}(\w+)\s', t, re.M)
print(f'  go tool vet help 列出的检查器共 {len(names)} 个:' + ' '.join(sorted(set(names))))
print('== 三:go test 自带的 vet 只跑一小部分检查')
(d / 'v.go').write_text('''package lab

import (
	"fmt"
	"sync"
)

type T struct {
	mu sync.Mutex
	n  int
}

func CopyLock(t T) int { return t.n }

func Printf() { fmt.Printf("%d\\n", "字符串") }
''')
rc, o = go(d, 'test', '-count=1', '.')
print(f'  只有 printf 问题和 copylocks 问题时 go test:退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if l.strip())[:300])
(d / 'v.go').write_text('''package lab

import "sync"

type T struct {
	mu sync.Mutex
	n  int
}

func CopyLock(t T) int { return t.n }
''')
rc, o = go(d, 'test', '-count=1', '.')
print(f'  只有 copylocks 问题时 go test:退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if l.strip())[:200])
rc, o = go(d, 'vet', '.')
print(f'  同样的代码 go vet:退出码 {rc};' + ' | '.join(l.strip() for l in o.split('\n') if l.strip() and not l.startswith('#'))[:200])
print('== 四:go help test 里 vet 的说明')
r = subprocess.run([GO, 'help', 'test'], capture_output=True, text=True, env=genv())
ls = r.stdout.split('\n')
i = next(i for i, l in enumerate(ls) if "go test runs go vet" in l)
print('  ' + ' '.join(x.strip() for x in ls[i:i + 8]))

import sys, os, re, time, statistics, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gl import *
tee('g83')
SRC = r'''
package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sort"
	"strings"
	"time"
)

func ps(pid int) string {
	out, _ := exec.Command("ps", "-o", "pid=,stat=,comm=", "-p", fmt.Sprint(pid)).Output()
	s := strings.TrimSpace(string(out))
	if s == "" { return "(进程表里已经没有这个 pid)" }
	return s
}

func ms(t0 time.Time) string { return fmt.Sprintf("%.0f ms", float64(time.Since(t0).Microseconds())/1000) }

func main() {
	switch os.Args[1] {
	case "zombie":
		cmd := exec.Command("/bin/sh", "-c", "exit 0")
		cmd.Start()
		pid := cmd.Process.Pid
		time.Sleep(200 * time.Millisecond)
		fmt.Printf("  Start 之后不调用 Wait,子进程已经退出 200 ms:ps 显示 %s\n", ps(pid))
		cmd.Wait()
		fmt.Printf("  调用 cmd.Wait() 之后:ps 显示 %s\n", ps(pid))
	case "pipe-after-wait":
		cmd := exec.Command("/bin/sh", "-c", "echo hello; echo world")
		out, _ := cmd.StdoutPipe()
		cmd.Start()
		cmd.Wait()
		b, err := io.ReadAll(out)
		fmt.Printf("  先 Wait 再读 StdoutPipe:读到 %q,err = %v\n", string(b), err)
		cmd2 := exec.Command("/bin/sh", "-c", "echo hello; echo world")
		out2, _ := cmd2.StdoutPipe()
		cmd2.Start()
		b2, err2 := io.ReadAll(out2)
		err3 := cmd2.Wait()
		fmt.Printf("  先读完 StdoutPipe 再 Wait:读到 %q,读 err = %v,Wait err = %v\n", string(b2), err2, err3)
	case "full-pipe":
		cmd := exec.Command("/bin/sh", "-c", "head -c 200000 /dev/zero")
		out, _ := cmd.StdoutPipe()
		cmd.Start()
		done := make(chan error, 1)
		go func() { done <- cmd.Wait() }()
		select {
		case err := <-done: fmt.Printf("  Wait 返回了:%v\n", err)
		case <-time.After(1500 * time.Millisecond):
			fmt.Printf("  子进程写 200000 字节,父进程没人读管道:1.5 秒后 Wait 仍然没有返回(子进程卡在 write 上:%s)\n", ps(cmd.Process.Pid))
			cmd.Process.Kill()
			<-done
		}
		_ = out
	case "output":
		t0 := time.Now()
		out, err := exec.Command("/bin/sh", "-c", "echo hi; sleep 1 &").Output()
		fmt.Printf("  sh 立刻退出,但留下一个后台 sleep 1 抱着 stdout:cmd.Output() 用了 %s 才返回,输出 %q,err = %v\n", ms(t0), string(out), err)
		t0 = time.Now()
		cmd := exec.Command("/bin/sh", "-c", "echo hi; sleep 1 &")
		cmd.WaitDelay = 200 * time.Millisecond
		var buf bytes.Buffer
		cmd.Stdout = &buf
		err = cmd.Run()
		fmt.Printf("  同样的命令设 cmd.WaitDelay = 200 ms:%s 返回,输出 %q,err = %v(是 ErrWaitDelay:%v)\n", ms(t0), buf.String(), err, errors.Is(err, exec.ErrWaitDelay))
	case "ctx":
		ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
		defer cancel()
		t0 := time.Now()
		cmd := exec.CommandContext(ctx, "/bin/sh", "-c", "sleep 2; echo done")
		out, err := cmd.Output()
		fmt.Printf("  CommandContext(超时 200 ms),sh -c 'sleep 2; echo done':%s 后返回,输出 %q,err = %v\n", ms(t0), string(out), err)
		ctx2, cancel2 := context.WithTimeout(context.Background(), 200*time.Millisecond)
		defer cancel2()
		t0 = time.Now()
		cmd2 := exec.CommandContext(ctx2, "/bin/sh", "-c", "sleep 2 & wait")
		out2, err2 := cmd2.Output()
		fmt.Printf("  CommandContext(超时 200 ms),sh -c 'sleep 2 & wait':%s 后返回,输出 %q,err = %v(sh 被杀了,孙进程 sleep 还抱着 stdout)\n", ms(t0), string(out2), err2)
	case "cost":
		var xs []float64
		for i := 0; i < 50; i++ { t0 := time.Now(); exec.Command("/usr/bin/true").Run(); xs = append(xs, float64(time.Since(t0).Microseconds())/1000) }
		sort.Float64s(xs)
		fmt.Printf("  exec.Command(\"/usr/bin/true\").Run() 50 次:最小 %.1f ms / 中位 %.1f ms / 最大 %.1f ms\n", xs[0], xs[25], xs[49])
	}
}
'''
d = gdir('ex1'); write(d, {'main.go': SRC}); mod(d)
rc, o = go(d, 'build', '-o', 'app'); assert rc == 0, o
def run(m):
    p = subprocess.run([str(d / 'app'), m], capture_output=True, text=True, timeout=120)
    return tidy(p.stdout + p.stderr)
print('== 一:不 Wait 会留下僵尸进程(Go 1.27.1,macOS)')
print(run('zombie'))
print('== 二:StdoutPipe 必须在 Wait 之前读完')
print(run('pipe-after-wait'))
print('== 三:管道写满了没人读')
print(run('full-pipe'))
print('== 四:孙进程抱着管道,Output / Run 迟迟不返回')
print(run('output'))
print('== 五:CommandContext 只杀直接的子进程')
print(run('ctx'))
print('== 六:启动一个进程要多久')
print(run('cost'))
print('== 七:文档:Cmd.WaitDelay 与 StdoutPipe')
r, o = go(gdir('doc1'), 'doc', 'os/exec.Cmd.StdoutPipe')
print('  ' + ' '.join(l.strip() for l in o.split('\n')[3:12] if l.strip()))
r, o = go(gdir('doc1'), 'doc', 'os/exec.Cmd')
ls = [l.strip() for l in o.split('\n')]
i = next(i for i, l in enumerate(ls) if l.startswith('// If WaitDelay is non-zero, it bounds the time spent'))
print('  ' + ' '.join(x.replace('// ', '', 1) for x in ls[i:i + 4] if x))
i = next(i for i, l in enumerate(ls) if l.startswith('// If WaitDelay is zero (the default)'))
print('  ' + ' '.join(x.replace('// ', '', 1) for x in ls[i:i + 3] if x))

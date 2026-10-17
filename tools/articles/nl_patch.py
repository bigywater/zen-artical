"""生成 gtmp/gin_patched:Gin v1.12.0 源码的副本 + zz_dump.go(只读地打印路由树内部结构,不改变任何行为)。
需要看 Engine 内部(trees / node)的实验用 gin(..., patched=True),go.mod 里 replace 指向这份副本。"""
import shutil, os
from nl import *
DUMP = '''package gin

import (
	"fmt"
	"strings"
)

var nodeTypeNames = map[nodeType]string{static: "static", root: "root", param: "param", catchAll: "catchAll"}

// DumpTree 只读地打印某个 HTTP 方法的路由树(实验用)。
func (e *Engine) DumpTree(method string) string {
	var sb strings.Builder
	for _, t := range e.trees {
		if t.method == method {
			dumpNode(&sb, t.root, 0)
		}
	}
	return sb.String()
}

func dumpNode(sb *strings.Builder, n *node, depth int) {
	h := ""
	if n.handlers != nil {
		h = fmt.Sprintf(" handlers=%d full=%q", len(n.handlers), n.fullPath)
	}
	w := ""
	if n.wildChild {
		w = " wildChild"
	}
	fmt.Fprintf(sb, "%s%q [%s prio=%d indices=%q%s]%s\\n", strings.Repeat("  ", depth), n.path, nodeTypeNames[n.nType], n.priority, n.indices, w, h)
	for _, c := range n.children {
		dumpNode(sb, c, depth+1)
	}
}

// TreeMethods 按创建顺序返回已有路由树的方法。
func (e *Engine) TreeMethods() []string {
	var r []string
	for _, t := range e.trees {
		r = append(r, t.method)
	}
	return r
}
'''
def make():
    dst = GT / 'gin_patched'
    if dst.exists(): subprocess.run(['chmod', '-R', 'u+w', str(dst)])
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(GINSRC, dst, ignore=shutil.ignore_patterns('*_test.go', 'docs', 'examples', 'testdata', '.git*'))
    for r, ds, fs in os.walk(dst):
        os.chmod(r, 0o755)
        for f in fs: os.chmod(os.path.join(r, f), 0o644)
    (dst / 'zz_dump.go').write_text(DUMP)
if __name__ == '__main__': make()

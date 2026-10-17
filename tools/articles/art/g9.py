from lib import *
S = SS('g9')
steps = [
    step("赋值、传参、结构体里的数组都是值拷贝。b := a 之后改 b[0],a 仍是 [1 2 3];modify(a) 里写 a[0] = 100,调用者的 a 还是 [1 2 3];modifyPtr(&a) 才改到调用者的 a(变成 [100 2 3])。unsafe.Sizeof:[3]int = 24、[0]int = 0、[4096]int = 32768、Pair{string, [2]int} = 32 字节。p2 := p1 后改 p2.Pos[0],p1.Pos 不变,p1 == p2 为 false。[...]int{5: 1, 2, 3: 7} 是 [0 0 0 7 0 1 2](len 7)。", t=tl(S(1)), done=lidx(S(1), 'b := a', 'modify(a)', 'unsafe.Sizeof'), mark=lidx(S(1), 'modifyPtr(&a)', '结构体里的数组也是值'), kv=KV([['b := a', '拷贝整个数组,改 b 不影响 a'], ['modify(a)', '传参拷贝,调用者不变'], ['modifyPtr(&a)', '改到调用者的 a'], ['[4096]int', '32768 字节'], ['结构体里的数组', '一起被拷贝']], ['modify(a)'])),
    step("range 数组会先拷贝整个数组:循环里把 arr[2] 改成 100,for i, v := range arr 打印的 v 仍是 1、2、3,循环后 arr = [1 2 100];range arr[:](切片)与 range &arr(数组指针)打印 1、2、100;只要下标 for i := range arr 读 arr[i] 也是 1、2、100(不拷贝)。", t=tl(S(2)), done=lidx(S(2), 'range arr(循环里'), mark=lidx(S(2), 'range arr[:]', 'range &arr', '只要下标'), kv=KV([['range arr(带 v)', '先拷贝数组,v 是 1、2、3'], ['range arr[:]', 'v 是 1、2、100(看得到修改)'], ['range &arr', 'v 是 1、2、100'], ['for i := range arr', '不拷贝']], ['range arr(带 v)'])),
    step("数组可以用 ==:[2]int{1,2} == [2]int{1,2} 为 true;可以做 map 的键:map[[2]int]string 里查 {1,2} 得到 \"a\",查 {9,9} 得到空串;[2]int 与 [3]int 是不同的类型。", t=tl(S(3)), done=lidx(S(3), '[2]int{1,2}'), kv=KV([['数组 ==', '逐元素比较,true'], ['map[[2]int]string', '数组可以做键'], ['[2]int 与 [3]int', '不同类型']], ['map[[2]int]string'])),
    step("传 32 KiB 的大数组(//go:noinline 的求和函数,7 轮取中位数):按值传 2039.13 ns/op;传指针 1199.74 ns/op;传切片 1190.99 ns/op。按值比传指针多出约 840 ns,这就是每次调用拷贝 32 KiB 的代价。", t=tl(S(4)), done=lidx(S(4), 'sumPtr', 'sumSlice'), mark=lidx(S(4), 'sumVal'), b=bars([['按值传 ns/op', 2039.13, '2039'], ['传指针 ns/op', 1199.74, '1200'], ['传切片 ns/op', 1190.99, '1191']], 2039.13, done=[1, 2], mark=[0]), kv=KV([['按值传 [4096]int', '2039.13 ns/op'], ['传指针', '1199.74 ns/op'], ['传切片', '1190.99 ns/op'], ['差值', '约 840 ns(拷贝 32 KiB)']], ['按值传 [4096]int'])),
    step("编译器对不合法比较的报错:长度不同的数组 a == b:invalid operation: a == b (mismatched types [3]int and [4]int);切片之间 s1 == s2:slice can only be compared to nil;切片做 map 键:invalid map key type []int。", t=tl(S(5)), mark=lidx(S(5), 'mismatched types', 'slice can only be compared to nil', 'invalid map key type'), kv=KV([['[3]int == [4]int', 'mismatched types'], ['[]int == []int', 'slice can only be compared to nil'], ['map[[]int]int', 'invalid map key type []int']], ['[]int == []int'])),
]
A = mkartg('g9', 9, 'Go,数组,值语义,range,真实验证,动画演示',
    '用 Go 1.27.1 实测数组的值语义:赋值、传参、结构体里的数组都会拷贝;range 数组会先拷贝(循环里改元素 v 看不到),range 切片或数组指针看得到;数组可以 == 和做 map 的键,长度不同是不同类型;传 32 KiB 数组按值 2039 ns、传指针 1200 ns;切片与切片不能比较、不能做键。',
    '数组在 Go 里是值,不是指针。这带来几个直接后果:赋值与传参都会整块拷贝,range 数组会先拷贝一份,数组的长度是类型的一部分。这篇逐项用真实输出验证,并量一量传大数组的拷贝代价。',
    [('24 字节', '[3]int 的大小;[4096]int 是 32768 字节,传参时整块拷贝'), ('v 是 1、2、3', 'range 数组时循环里改 arr[2],v 仍是旧值;range arr[:] 则看到 100'), ('2039 ns vs 1200 ns', '传 32 KiB 数组按值与按指针')],
    [('值语义', '<p>数组变量代表整块内存:<code>b := a</code> 与函数传参都拷贝所有元素,结构体里的数组字段也一样。要在函数里修改调用者的数组,必须传指针(或者传切片)。零长度数组 <code>[0]int</code> 大小是 0。</p>'),
     ('range 与拷贝', '<p><code>for i, v := range arr</code> 对数组 <code>arr</code> 会先求值并拷贝整个数组,循环里对 <code>arr</code> 的修改不会反映到 <code>v</code> 上;只写 <code>for i := range arr</code> 或者 <code>range &arr</code>、<code>range arr[:]</code> 就没有这个拷贝。语言规范里对此有明确说明,这里用实验验证了结果。编译器是否在某些情况下把拷贝优化掉,我没有检查。</p>'),
     ('比较与做键', '<p>数组的元素类型可比较时,数组就可比较,因此可以做 map 的键(<code>map[[2]int]string</code>)——这是用切片做不到的。长度是类型的一部分,<code>[2]int</code> 与 <code>[3]int</code> 是不同的类型,不能互相赋值或比较。</p>'),
     ('传大数组的代价', '<p>按值传 32 KiB 数组比传指针多约 840 ns,与求和本身的 1200 ns 相比是显著的。这只是 <code>//go:noinline</code> 函数的数字;如果函数被内联,编译器可能不需要真的拷贝,这种情况我没有测。</p>'),
     ('编译器的报错', '<p>三个典型的编译错误:长度不同的数组比较(<code>mismatched types</code>)、切片只能和 <code>nil</code> 比较、切片不能做 map 键。需要比较切片内容时用 <code>slices.Equal</code>(本文没有运行)。</p>')],
    steps,
    [ENV_G + '。基准测试 7 轮取中位数,函数都 //go:noinline;编译错误是 go build 的原样输出',
     '没有验证:函数内联后传大数组是否还拷贝、range 数组的拷贝是否会被编译器优化掉、amd64 上的耗时、多维数组的内存布局、slices.Equal 的行为'],
    '数组的值语义')

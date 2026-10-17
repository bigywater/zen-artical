import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nl import *
r = gin('hello', '''
package main
import ("fmt"; "net/http"; "net/http/httptest"; "github.com/gin-gonic/gin")
func main() {
	r := gin.New()
	r.GET("/ping", func(c *gin.Context) { c.String(200, "pong") })
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest("GET", "/ping", nil))
	fmt.Println(w.Code, w.Body.String(), http.StatusText(w.Code), gin.Version)
}
''')
out_lines(r)
gsrcl('tree.go', 1, 3)

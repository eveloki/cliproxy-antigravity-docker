// Command prepare-plugin applies distribution safeguards by Go syntax, not diff context.
package main

import (
	"bytes"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/printer"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type edit struct {
	start, end int
	text       string
}
type editor struct {
	source []byte
	set    *token.FileSet
	file   *ast.File
	edits  []edit
}

func parse(source []byte) (*editor, error) {
	set := token.NewFileSet()
	file, err := parser.ParseFile(set, "source.go", source, parser.ParseComments)
	return &editor{source: source, set: set, file: file}, err
}
func (e *editor) change(start, end token.Pos, text string) {
	e.edits = append(e.edits, edit{e.set.Position(start).Offset, e.set.Position(end).Offset, text})
}
func expr(n ast.Node) string {
	var b bytes.Buffer
	_ = printer.Fprint(&b, token.NewFileSet(), n)
	return b.String()
}
func exactly(label string, count int) error {
	if count != 1 {
		return fmt.Errorf("%s: expected one syntax target, found %d; review upstream changes", label, count)
	}
	return nil
}
func (e *editor) function(name string) (*ast.FuncDecl, error) {
	var result *ast.FuncDecl
	count := 0
	for _, d := range e.file.Decls {
		if f, ok := d.(*ast.FuncDecl); ok && f.Name.Name == name {
			result = f
			count++
		}
	}
	return result, exactly(name, count)
}
func (e *editor) addReason(name string) error {
	count := 0
	ast.Inspect(e.file, func(n ast.Node) bool {
		t, ok := n.(*ast.TypeSpec)
		if !ok || t.Name.Name != name {
			return true
		}
		s, ok := t.Type.(*ast.StructType)
		if !ok {
			return true
		}
		for _, f := range s.Fields.List {
			for _, n := range f.Names {
				if n.Name == "FinishedReason" {
					return false
				}
			}
		}
		e.change(s.Fields.Opening+1, s.Fields.Opening+1, "\nFinishedReason string `json:\"finished_reason\"`\n")
		count++
		return false
	})
	return exactly(name+" unfinished-result field", count)
}
func (e *editor) guard(function, variable, guard string) error {
	f, err := e.function(function)
	if err != nil {
		return err
	}
	count := 0
	for _, s := range f.Body.List {
		if condition, ok := s.(*ast.IfStmt); ok && expr(condition.Cond) == "!strings.EqualFold("+variable+".Status, \"SUCCESS\")" {
			e.change(s.Pos(), s.Pos(), guard+"\n")
			count++
		}
	}
	return exactly(function+" success guard", count)
}
func (e *editor) legacyReason() error {
	f, err := e.function("executeStream")
	if err != nil {
		return err
	}
	count := 0
	ast.Inspect(f, func(n ast.Node) bool {
		c, ok := n.(*ast.CompositeLit)
		if !ok || expr(c.Type) != "agyResult" {
			return true
		}
		legacy := false
		hasReason := false
		for _, element := range c.Elts {
			if kv, ok := element.(*ast.KeyValueExpr); ok {
				if expr(kv.Key) == "Status" && expr(kv.Value) == "event.Status" {
					legacy = true
				}
				if expr(kv.Key) == "FinishedReason" {
					hasReason = true
				}
			}
		}
		if legacy && !hasReason {
			e.change(c.Lbrace+1, c.Lbrace+1, "FinishedReason: event.FinishedReason, ")
			count++
		}
		return true
	})
	return exactly("legacy flat stream result", count)
}
func (e *editor) dispatch() error {
	f, err := e.function("handleMethod")
	if err != nil {
		return err
	}
	counts := map[string]int{"methodModelRegister": 0, "methodModelStatic": 0, "methodModelRoute": 0}
	ast.Inspect(f, func(n ast.Node) bool {
		c, ok := n.(*ast.CaseClause)
		if !ok {
			return true
		}
		for _, name := range c.List {
			label := expr(name)
			if _, ok := counts[label]; !ok {
				continue
			}
			for _, s := range c.Body {
				ast.Inspect(s, func(n ast.Node) bool {
					call, ok := n.(*ast.CallExpr)
					if !ok {
						return true
					}
					if label == "methodModelRoute" && expr(call) == "routeModel(req)" {
						e.change(call.Fun.Pos(), call.Fun.End(), "distributionRouteModel")
						counts[label]++
						return false
					}
					if label != "methodModelRoute" && expr(call) == "discoverModels(currentConfig())" {
						e.change(call.Pos(), call.End(), "distributionModels("+expr(call)+")")
						counts[label]++
						return false
					}
					return true
				})
			}
		}
		return true
	})
	for _, label := range []string{"methodModelRegister", "methodModelStatic", "methodModelRoute"} {
		if err := exactly(label, counts[label]); err != nil {
			return err
		}
	}
	return nil
}
func (e *editor) stamp(expected string) error {
	count := 0
	var mismatch error
	ast.Inspect(e.file, func(n ast.Node) bool {
		v, ok := n.(*ast.ValueSpec)
		if !ok {
			return true
		}
		for i, name := range v.Names {
			if name.Name == "pluginVersion" {
				if i >= len(v.Values) {
					mismatch = fmt.Errorf("pluginVersion has no literal")
					return false
				}
				literal, ok := v.Values[i].(*ast.BasicLit)
				if !ok {
					mismatch = fmt.Errorf("pluginVersion is not a literal")
					return false
				}
				actual, err := strconv.Unquote(literal.Value)
				if err != nil || actual != expected {
					mismatch = fmt.Errorf("source pluginVersion %q differs from pinned %q", actual, expected)
					return false
				}
				e.change(literal.Pos(), literal.End(), strconv.Quote(expected+"+dist1"))
				count++
			}
		}
		return true
	})
	if mismatch != nil {
		return mismatch
	}
	return exactly("pluginVersion", count)
}
func (e *editor) render() ([]byte, error) {
	sort.Slice(e.edits, func(i, j int) bool { return e.edits[i].start > e.edits[j].start })
	result := append([]byte(nil), e.source...)
	last := len(result) + 1
	for _, edit := range e.edits {
		if edit.end > last {
			return nil, fmt.Errorf("overlapping source edits")
		}
		result = append(append(append([]byte(nil), result[:edit.start]...), []byte(edit.text)...), result[edit.end:]...)
		last = edit.start
	}
	return format.Source(result)
}
func prepare(agy, plugin []byte, version string) ([]byte, []byte, error) {
	version = strings.TrimPrefix(version, "v")
	parts := strings.Split(version, ".")
	if len(parts) != 3 {
		return nil, nil, fmt.Errorf("expected stable plugin version")
	}
	for _, part := range parts {
		if part == "" {
			return nil, nil, fmt.Errorf("invalid version")
		}
		for _, c := range part {
			if c < '0' || c > '9' {
				return nil, nil, fmt.Errorf("expected stable plugin version")
			}
		}
	}
	a, err := parse(agy)
	if err != nil {
		return nil, nil, err
	}
	p, err := parse(plugin)
	if err != nil {
		return nil, nil, err
	}
	for _, name := range []string{"agyResult", "agyStreamEvent"} {
		if err := a.addReason(name); err != nil {
			return nil, nil, err
		}
	}
	if err := a.guard("runAgyJSON", "result", "if err := distributionResultError(result); err != nil { return result, stderr.String(), err }"); err != nil {
		return nil, nil, err
	}
	if err := a.guard("executeStream", "terminal", "if err := distributionResultError(*terminal); err != nil { closePluginStream(streamID, err); return }"); err != nil {
		return nil, nil, err
	}
	if err := a.legacyReason(); err != nil {
		return nil, nil, err
	}
	if err := p.dispatch(); err != nil {
		return nil, nil, err
	}
	if err := p.stamp(version); err != nil {
		return nil, nil, err
	}
	outA, err := a.render()
	if err != nil {
		return nil, nil, err
	}
	outP, err := p.render()
	return outA, outP, err
}
func run(directory, version string) error {
	aPath, pPath := filepath.Join(directory, "agy.go"), filepath.Join(directory, "plugin.go")
	a, err := os.ReadFile(aPath)
	if err != nil {
		return err
	}
	p, err := os.ReadFile(pPath)
	if err != nil {
		return err
	}
	// Validate every edit in memory before changing either source file.
	outA, outP, err := prepare(a, p, version)
	if err != nil {
		return err
	}
	if err := os.WriteFile(aPath, outA, 0644); err != nil {
		return err
	}
	return os.WriteFile(pPath, outP, 0644)
}
func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: prepare-plugin DIRECTORY PINNED_VERSION")
		os.Exit(2)
	}
	if err := run(os.Args[1], os.Args[2]); err != nil {
		fmt.Fprintln(os.Stderr, "Plugin safeguards not applied:", err)
		os.Exit(1)
	}
}

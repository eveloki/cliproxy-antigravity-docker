package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const agyFixture = `package main
 type agyResult struct { Status string }
 type agyStreamEvent struct { Status string }
 func runAgyJSON(cfg any) {
  result := getResult()
  if !strings.EqualFold(result.Status, "SUCCESS") { fail() }
 }
 func executeStream(req any, run agyExecution) {
  // Account-bound resume logic can change around the terminal assignment.
  updateConversationID(event.ConversationID)
  terminal := &agyResult{Status:event.Status}
  updateConversationID(event.ConversationID)
  if !strings.EqualFold(terminal.Status, "SUCCESS") { fail() }
 }
`
const pluginFixture = `package main
 const pluginVersion = "0.4.0"
 func handleMethod(method string,request []byte) {
  switch method {
  case methodModelRegister: models := discoverModels(currentConfig());use(models)
  case methodModelStatic: models := discoverModels(currentConfig());use(models)
  case methodModelRoute: decode(request);return okEnvelope(routeModel(req))
  case methodSchedulerPick: pickConversationAccount(req)
  }
 }
`

func TestSyntaxEditsSurviveLayoutAndSessionChanges(t *testing.T) {
	for _, source := range []string{agyFixture, strings.ReplaceAll(agyFixture, "\n", "\n\n")} {
		for _, version := range []string{"0.3.1", "0.3.2", "0.4.0"} {
			plugin := strings.ReplaceAll(pluginFixture, "0.4.0", version)
			a, p, err := prepare([]byte(source), []byte(plugin), "v"+version)
			if err != nil {
				t.Fatal(err)
			}
			for _, want := range []string{"FinishedReason", "distributionResultError(result)", "distributionResultError(*terminal)", "event.FinishedReason", "updateConversationID(event.ConversationID)"} {
				if !strings.Contains(string(a), want) {
					t.Fatalf("missing %s", want)
				}
			}
			for _, want := range []string{version + "+dist1", "distributionModels(discoverModels(currentConfig()))", "distributionRouteModel(req)", "pickConversationAccount(req)"} {
				if !strings.Contains(string(p), want) {
					t.Fatalf("missing %s", want)
				}
			}
			if _, _, err := prepare(a, p, version); err == nil {
				t.Fatal("unexpected repeated transformation accepted")
			}
		}
	}
}
func TestUnknownStructureNeverWritesPartialSources(t *testing.T) {
	for _, mutate := range []func(string) string{
		func(s string) string { return strings.ReplaceAll(s, "routeModel(req)", "routeNewModel(req)") },
		func(s string) string { return strings.ReplaceAll(s, "decode(request)", "routeModel(req)") },
		func(s string) string { return strings.ReplaceAll(s, "0.4.0", "0.4.1") },
	} {
		dir := t.TempDir()
		aPath, pPath := filepath.Join(dir, "agy.go"), filepath.Join(dir, "plugin.go")
		plugin := mutate(pluginFixture)
		if err := os.WriteFile(aPath, []byte(agyFixture), 0600); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(pPath, []byte(plugin), 0600); err != nil {
			t.Fatal(err)
		}
		if err := run(dir, "v0.4.0"); err == nil {
			t.Fatal("unreviewed source accepted")
		}
		a, _ := os.ReadFile(aPath)
		p, _ := os.ReadFile(pPath)
		if string(a) != agyFixture || string(p) != plugin {
			t.Fatal("failed check changed source")
		}
	}
}
func TestChangedTerminalContractFailsClosed(t *testing.T) {
	for _, source := range []string{
		strings.ReplaceAll(agyFixture, "terminal.Status", "terminal.State"),
		strings.ReplaceAll(agyFixture, "event.Status", "event.State"),
		strings.Replace(agyFixture, "Status string", "FinishedReason string; Status string", 1),
	} {
		if _, _, err := prepare([]byte(source), []byte(pluginFixture), "v0.4.0"); err == nil {
			t.Fatal("changed result contract accepted")
		}
	}
}

package main

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestDistributionRejectsEarlyJSONResults(t *testing.T) {
	for _, reason := range []string{"", "print_timeout", "interrupted", "error", "future_reason"} {
		t.Run(reason, func(t *testing.T) {
			dir := t.TempDir()
			binary := filepath.Join(dir, "agy")
			raw, _ := json.Marshal(map[string]string{"status": "SUCCESS", "response": "partial", "finished_reason": reason})
			// The mock deliberately exits 0: the field must be checked independently.
			script := "#!/bin/sh\ncat >/dev/null\ncat <<'END'\n" + string(raw) + "\nEND\n"
			if err := os.WriteFile(binary, []byte(script), 0700); err != nil {
				t.Fatal(err)
			}
			cfg := defaultConfig()
			cfg.BinaryPath = binary
			cfg.Workdir = dir
			_, _, err := runAgyJSON(cfg, agyOptions{}, "hello")
			if reason == "" {
				if err != nil {
					t.Fatal(err)
				}
				return
			}
			var pe *pluginError
			if !errors.As(err, &pe) {
				t.Fatalf("reason %q accepted: %v", reason, err)
			}
			want := 502
			if reason == "print_timeout" {
				want = 504
			}
			if pe.HTTPStatus != want {
				t.Fatalf("status = %d, want %d", pe.HTTPStatus, want)
			}
		})
	}
}

func TestDistributionReadsWrappedAndLegacyStreamResults(t *testing.T) {
	for _, raw := range []string{
		`{"event":"result","result":{"status":"SUCCESS","finished_reason":"print_timeout"}}`,
		`{"status":"SUCCESS","finished_reason":"print_timeout"}`,
	} {
		var event agyStreamEvent
		if err := json.Unmarshal([]byte(raw), &event); err != nil {
			t.Fatal(err)
		}
		terminal := event.Result
		if terminal == nil {
			terminal = &agyResult{Status: event.Status, FinishedReason: event.FinishedReason}
		}
		if distributionResultError(*terminal) == nil {
			t.Fatal("partial stream accepted")
		}
	}
}

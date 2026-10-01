package main

import (
	"encoding/json"
	"testing"
)

func TestDistributionModelRouterABI(t *testing.T) {
	if !pluginRegistration().Capabilities.ModelRouter {
		t.Fatal("model_router capability is not advertised")
	}
	for _, model := range []string{"agy/gemini-3.8-flash", "agy/default", " agy/gemini-3.8-flash "} {
		for _, stream := range []bool{false, true} {
			raw, _ := json.Marshal(map[string]any{"RequestedModel": model, "Stream": stream, "SourceFormat": "openai"})
			payload, err := handleMethod("model.route", raw)
			if err != nil {
				t.Fatal(err)
			}
			var reply struct {
				OK bool `json:"ok"`
				Result struct { Handled bool; TargetKind string; TargetModel string } `json:"result"`
			}
			if err := json.Unmarshal(payload, &reply); err != nil {
				t.Fatal(err)
			}
			if !reply.OK || !reply.Result.Handled || reply.Result.TargetKind != "self" || reply.Result.TargetModel != "" {
				t.Fatalf("wrong route for %q stream=%v: %s", model, stream, payload)
			}
		}
	}
}

func TestDistributionRouterDoesNotCaptureNativeProviders(t *testing.T) {
	for _, model := range []string{"", "agy/", "agy/  ", "gemini-3.8-flash", "antigravity/gemini-3.8-flash", "codex/model", "not-agy/model"} {
		raw, _ := json.Marshal(map[string]string{"RequestedModel": model})
		payload, err := handleMethod("model.route", raw)
		if err != nil { t.Fatal(err) }
		var reply struct { Result struct { Handled bool; TargetKind string } `json:"result"` }
		if err := json.Unmarshal(payload, &reply); err != nil { t.Fatal(err) }
		if reply.Result.Handled || reply.Result.TargetKind != "" {
			t.Fatalf("unexpected route for %q: %s", model, payload)
		}
	}
	if _, err := handleMethod("model.route", []byte(`{"RequestedModel":`)); err == nil {
		t.Fatal("invalid RPC JSON was accepted")
	}
}

func TestDistributionStreamDoesNotDoubleFrame(t *testing.T) {
	frame := makeSSEChunk("test", 1, "agy/gemini-3.8-flash", map[string]any{"content": "mock response"}, nil, nil, "")
	data := distributionStreamPayload(frame)
	if !json.Valid(data) { t.Fatalf("expected bare JSON, got %q", data) }
	if string(distributionStreamPayload(data)) != string(data) { t.Fatal("raw JSON changed") }
	for _, done := range []string{"data: [DONE]\n\n", "[DONE]"} {
		if len(distributionStreamPayload([]byte(done))) != 0 { t.Fatal("plugin must leave DONE to CPA") }
	}
}

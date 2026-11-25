package main

import (
	"encoding/json"
	"testing"
)

func TestDistributionNamespace(t *testing.T) {
	for _, model := range []string{"gemini-3.8-flash", "antigravity/default", "gpt-5.5", "agy/", "agy/ "} {
		if distributionRouteModel(modelRouteRequest{RequestedModel: model}).Handled {
			t.Fatalf("claimed %q", model)
		}
	}
	if !distributionRouteModel(modelRouteRequest{RequestedModel: "agy/gemini-3.8-flash"}).Handled {
		t.Fatal("agy route missing")
	}
	if distributionRouteModel(modelRouteRequest{RequestedModel: "agy/gemini-3.8-flash", AvailableProviders: []string{"agy"}}).Handled {
		t.Fatal("native agy auth scheduling was overridden")
	}
	for _, m := range distributionModels(standardBuiltinModels()) {
		if len(m.ID) < 4 || m.ID[:4] != "agy/" {
			t.Fatalf("bare published model %q", m.ID)
		}
	}
}

func TestDistributionRouteABI(t *testing.T) {
	for _, tc := range []struct {
		model string
		self  bool
	}{
		{"agy/gemini-3.8-flash:max", true},
		{"agy/gemini-3.8-flash(xhigh)", true},
		{"gemini-3.8-flash:max", false},
		{"antigravity/gemini-3.8-flash:max", false},
	} {
		t.Run(tc.model, func(t *testing.T) {
			request, err := json.Marshal(modelRouteRequest{RequestedModel: tc.model})
			if err != nil {
				t.Fatal(err)
			}
			response, err := handleMethod(methodModelRoute, request)
			if err != nil {
				t.Fatal(err)
			}
			var decoded struct {
				OK     bool
				Result modelRouteResponse
			}
			if err := json.Unmarshal(response, &decoded); err != nil {
				t.Fatal(err)
			}
			if !decoded.OK || decoded.Result.Handled != tc.self || (decoded.Result.TargetKind == "self") != tc.self {
				t.Fatalf("want self route=%t, got %s", tc.self, response)
			}
		})
	}
}

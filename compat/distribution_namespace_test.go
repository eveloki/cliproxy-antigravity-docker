package main

import "testing"

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

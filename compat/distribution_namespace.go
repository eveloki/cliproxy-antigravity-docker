package main

import "strings"

// Preserve this distribution's explicit agy/ namespace. Upstream also claims
// published bare names and antigravity/; those remain reserved for native CPA here.
func distributionRouteModel(req modelRouteRequest) modelRouteResponse {
	model := strings.TrimSpace(req.RequestedModel)
	if !strings.HasPrefix(model, "agy/") || strings.TrimSpace(strings.TrimPrefix(model, "agy/")) == "" {
		return modelRouteResponse{}
	}
	return routeModel(req)
}

func distributionModels(models []modelInfo) []modelInfo {
	result := make([]modelInfo, 0, len(models))
	seen := make(map[string]bool)
	for _, model := range models {
		if !strings.HasPrefix(model.ID, "agy/") {
			model.ID = "agy/" + model.ID
		}
		if !seen[model.ID] {
			result = append(result, model)
			seen[model.ID] = true
		}
	}
	return result
}

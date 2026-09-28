package main

import (
	"bytes"
	"encoding/json"
	"strings"
)

// The upstream plugin builds complete SSE frames, but CPA's chat handler adds
// its own data prefix and final DONE. Send just JSON over the plugin ABI.
func distributionStreamPayload(payload []byte) []byte {
	payload = bytes.TrimSpace(payload)
	payload = bytes.TrimSpace(bytes.TrimPrefix(payload, []byte("data:")))
	if bytes.Equal(payload, []byte("[DONE]")) {
		return nil
	}
	return payload
}

// CPA v8's static plugin executors need an explicit ModelRouter self route
// when the official CLI, rather than CPA's provider auth pool, owns login.
// Match only the explicit agy namespace so native provider models keep their
// normal credential selection. The host still validates the client API key.
func routeModelRequest(request []byte) ([]byte, error) {
	var req struct {
		RequestedModel string
	}
	if err := json.Unmarshal(request, &req); err != nil {
		return nil, pError("invalid_request", "could not decode model route request", 400)
	}
	model := strings.TrimSpace(req.RequestedModel)
	handled := strings.HasPrefix(model, "agy/") && strings.TrimSpace(strings.TrimPrefix(model, "agy/")) != ""
	target := ""
	if handled {
		target = "self"
	}
	return okEnvelope(struct {
		Handled    bool
		TargetKind string
	}{Handled: handled, TargetKind: target})
}

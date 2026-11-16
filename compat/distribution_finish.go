package main

import (
	"net/http"
	"strings"
)

// CLI >=1.4.11 can mark partial results independently of status and exit code.
// Never turn an incomplete turn into a successful OpenAI completion.
func distributionResultError(result agyResult) error {
	reason := strings.TrimSpace(result.FinishedReason)
	if reason == "" {
		return nil
	}
	message := "Antigravity CLI ended early: " + reason
	switch reason {
	case "print_timeout":
		return pError("agy_timeout", message, http.StatusGatewayTimeout)
	case "interrupted":
		return pError("agy_interrupted", message, http.StatusBadGateway)
	default:
		return pError("agy_incomplete_response", message, http.StatusBadGateway)
	}
}

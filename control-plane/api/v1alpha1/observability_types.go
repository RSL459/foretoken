// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

// Defines workload-owned alert selection without coupling monitoring to serving readiness.

package v1alpha1

// FrontendObservability selects observations owned by one FrontendService.
type FrontendObservability struct {
	// +optional
	Alerts *FrontendAlerts `json:"alerts,omitempty"`
}

// FrontendAlerts selects only frontend-scoped rules; omitted rules remain disabled.
type FrontendAlerts struct {
	// +optional
	// +listType=set
	// +kubebuilder:validation:items:Enum=ForetokenMetricsTargetDown;ForetokenFrontendHTTPResponseStart5xxRatioHigh
	Rules []string `json:"rules,omitempty"`
}

// ModelObservability selects observations owned by one ModelService.
type ModelObservability struct {
	// +optional
	Alerts *ModelAlerts `json:"alerts,omitempty"`
}

// ModelAlerts selects rules for a model's owned execution groups.
// +kubebuilder:validation:XValidation:rule="!has(self.rules) || !self.rules.exists(rule, rule == 'ForetokenNVIDIAGPUPowerUsageHigh') || (has(self.thresholds) && has(self.thresholds.nvidiaPowerWatts))",message="the power alert requires an explicit positive nvidiaPowerWatts threshold"
type ModelAlerts struct {
	// +optional
	// +listType=set
	// +kubebuilder:validation:MaxItems=3
	// +kubebuilder:validation:items:Enum=ForetokenMetricsTargetDown;ForetokenNVIDIAGPUTemperatureHigh;ForetokenNVIDIAGPUPowerUsageHigh
	Rules []string `json:"rules,omitempty"`

	// +optional
	// +kubebuilder:default={}
	Thresholds *ModelAlertThresholds `json:"thresholds,omitempty"`
}

// ModelAlertThresholds configures the selected model rules, not their activation.
type ModelAlertThresholds struct {
	// +optional
	// +kubebuilder:default=85
	// +kubebuilder:validation:Minimum=0
	NVIDIATemperatureCelsius *float64 `json:"nvidiaTemperatureCelsius,omitempty"`

	// +optional
	// +kubebuilder:validation:Minimum=0
	// +kubebuilder:validation:ExclusiveMinimum=true
	NVIDIAPowerWatts *float64 `json:"nvidiaPowerWatts,omitempty"`
}

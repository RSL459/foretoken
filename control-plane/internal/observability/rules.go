// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

// Renders the built-in alert catalogue for a controller-verified workload scope.

package observability

import (
	_ "embed"
	"fmt"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"sync"

	monitoringv1 "github.com/prometheus-operator/prometheus-operator/pkg/apis/monitoring/v1"
	inferencev1alpha1 "github.com/shiweijiezero/foretoken/control-plane/api/v1alpha1"
	"k8s.io/apimachinery/pkg/util/intstr"
	"sigs.k8s.io/yaml"
)

//go:embed rules.yaml
var catalogueYAML []byte

var catalogue = sync.OnceValues(func() (map[string]monitoringv1.Rule, error) {
	var spec monitoringv1.PrometheusRuleSpec
	if err := yaml.UnmarshalStrict(catalogueYAML, &spec); err != nil {
		return nil, fmt.Errorf("decode alert catalogue: %w", err)
	}
	rules := make(map[string]monitoringv1.Rule)
	for _, group := range spec.Groups {
		for _, rule := range group.Rules {
			rules[rule.Alert] = rule
		}
	}
	return rules, nil
})

// Scope identifies one frontend or the execution groups currently owned by one model service.
type Scope struct {
	Namespace   string
	Frontend    string
	ModelGroups []string
}

// Render returns only selected rules, scoped to the owner's current resources.
// Threshold defaults come from API admission; this compiler never guesses missing values.
func Render(selected []string, scope Scope, thresholds *inferencev1alpha1.ModelAlertThresholds) (monitoringv1.PrometheusRuleSpec, error) {
	templates, err := catalogue()
	if err != nil {
		return monitoringv1.PrometheusRuleSpec{}, err
	}
	groups := slices.Clone(scope.ModelGroups)
	slices.Sort(groups)
	for index := range groups {
		groups[index] = regexp.QuoteMeta(groups[index])
	}
	groupPattern := "a^" // The empty ownership set must match no series.
	if len(groups) != 0 {
		groupPattern = "^(?:" + strings.Join(groups, "|") + ")$"
	}
	// Scope values are quoted as PromQL strings, not interpolated as query syntax.
	scopeValues := strings.NewReplacer(
		strconv.Quote("foretoken_alert_namespace"), strconv.Quote(scope.Namespace),
		strconv.Quote("foretoken_alert_frontend"), strconv.Quote(scope.Frontend),
		strconv.Quote("foretoken_alert_model_groups"), strconv.Quote(groupPattern),
	)
	values := map[string]*float64{}
	if thresholds != nil {
		values["foretoken_alert_threshold_nvidia_temperature_celsius"] = thresholds.NVIDIATemperatureCelsius
		values["foretoken_alert_threshold_nvidia_power_watts"] = thresholds.NVIDIAPowerWatts
	}
	rules := make([]monitoringv1.Rule, 0, len(selected))
	for _, name := range selected {
		template, found := templates[name]
		if !found {
			return monitoringv1.PrometheusRuleSpec{}, fmt.Errorf("unknown alert rule %q", name)
		}
		rule := template.DeepCopy()
		expression := scopeValues.Replace(rule.Expr.String())
		for token, value := range values {
			if !strings.Contains(expression, token) {
				continue
			}
			if value == nil {
				return monitoringv1.PrometheusRuleSpec{}, fmt.Errorf("alert %s requires its threshold", name)
			}
			number := strconv.FormatFloat(*value, 'g', -1, 64)
			replace := strings.NewReplacer(strconv.Quote(token), number, token, number)
			expression = replace.Replace(expression)
			for key, annotation := range rule.Annotations {
				rule.Annotations[key] = replace.Replace(annotation)
			}
		}
		if strings.Contains(expression, "foretoken_alert_threshold_") {
			return monitoringv1.PrometheusRuleSpec{}, fmt.Errorf("alert %s requires model thresholds", name)
		}
		rule.Expr = intstr.FromString(expression)
		rules = append(rules, *rule)
	}
	return monitoringv1.PrometheusRuleSpec{Groups: []monitoringv1.RuleGroup{{Name: "foretoken.alerting", Rules: rules}}}, nil
}

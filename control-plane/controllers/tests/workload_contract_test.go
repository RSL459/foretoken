// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

package tests

import (
	"context"
	"testing"

	inferencev1alpha1 "github.com/shiweijiezero/foretoken/control-plane/api/v1alpha1"
	"github.com/shiweijiezero/foretoken/control-plane/controllers"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

func TestModelGroupWorkloadContract(t *testing.T) {
	ctx := context.Background()
	service := modelService("model", 1)
	pool := modelPool(service, "model-default", 1)
	group := modelGroup(pool, "model-r1-0", 0)
	group.Spec.Accelerator.RuntimeClassName = "nvidia"
	c := controllerClient(t, service, pool, group)
	reconciler := &controllers.ModelGroupReconciler{Client: c, ControlPlaneNamespace: "foretoken-system", ImagePullSecrets: []corev1.LocalObjectReference{{Name: "registry"}}}
	request := ctrl.Request{NamespacedName: client.ObjectKeyFromObject(group)}

	if _, err := reconciler.Reconcile(ctx, request); err != nil {
		t.Fatal(err)
	}

	deployment := get(t, ctx, c, request.NamespacedName, new(appsv1.Deployment))
	pod := deployment.Spec.Template.Spec
	container := pod.Containers[0]
	if deployment.Spec.Replicas == nil || *deployment.Spec.Replicas != 1 || pod.AutomountServiceAccountToken == nil || *pod.AutomountServiceAccountToken || pod.RuntimeClassName == nil || *pod.RuntimeClassName != "nvidia" || len(pod.ImagePullSecrets) != 1 || pod.ImagePullSecrets[0].Name != "registry" || container.Image != "vllm:test" || container.ReadinessProbe == nil {
		t.Fatalf("deployment contract = %#v", deployment.Spec)
	}
	for _, variable := range container.Env {
		if variable.Name == "HOME" || variable.Name == "HF_HOME" || variable.Name == "XDG_CACHE_HOME" {
			t.Fatalf("workload overrides inference engine cache environment: %#v", container.Env)
		}
	}
	serviceObject := get(t, ctx, c, request.NamespacedName, new(corev1.Service))
	if !metav1.IsControlledBy(serviceObject, group) || serviceObject.Spec.Selector["inference.foretoken.io/model-group"] != group.Name {
		t.Fatalf("service contract = %#v", serviceObject)
	}
	policy := get(t, ctx, c, request.NamespacedName, new(networkingv1.NetworkPolicy))
	if !metav1.IsControlledBy(policy, group) || len(policy.Spec.Ingress) != 1 || len(policy.Spec.Ingress[0].From) != 1 {
		t.Fatalf("network policy = %#v", policy.Spec)
	}
	current := get(t, ctx, c, request.NamespacedName, new(inferencev1alpha1.ModelGroup))
	if condition := meta.FindStatusCondition(current.Status.Conditions, "WorkloadMaterialized"); condition == nil || condition.Status != metav1.ConditionTrue {
		t.Fatalf("group status = %#v", current.Status)
	}
}

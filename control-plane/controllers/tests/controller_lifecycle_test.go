// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

package tests

import (
	"context"
	"testing"

	inferencev1alpha1 "github.com/shiweijiezero/foretoken/control-plane/api/v1alpha1"
	"github.com/shiweijiezero/foretoken/control-plane/controllers"
	"github.com/shiweijiezero/foretoken/control-plane/internal/resolver"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

func TestModelServingControllerLifecycle(t *testing.T) {
	ctx := context.Background()
	t.Run("ModelService materializes a ready owned Pool", func(t *testing.T) {
		service := modelService("chat", 1)
		c := controllerClient(t, service)
		reconciler := &controllers.ModelServiceReconciler{Client: c}
		request := ctrl.Request{NamespacedName: client.ObjectKeyFromObject(service)}
		for range 2 {
			if _, err := reconciler.Reconcile(ctx, request); err != nil {
				t.Fatal(err)
			}
		}
		pool := get(t, ctx, c, client.ObjectKey{Namespace: service.Namespace, Name: "chat-default"}, new(inferencev1alpha1.ModelPool))
		if !metav1.IsControlledBy(pool, service) || pool.Spec.ModelServiceRef.UID != string(service.UID) || pool.Spec.DesiredGroups != 1 || pool.Spec.Template.Tokenizer != service.Spec.Model || pool.Spec.Template.ModelRevision != "main" || pool.Spec.Template.TokenizerRevision != "main" {
			t.Fatalf("materialized pool = %#v", pool)
		}
		meta.SetStatusCondition(&pool.Status.Conditions, metav1.Condition{Type: readyCondition, Status: metav1.ConditionTrue, ObservedGeneration: pool.Generation})
		pool.Status.ObservedGeneration = pool.Generation
		if err := c.Status().Update(ctx, pool); err != nil {
			t.Fatal(err)
		}
		if _, err := reconciler.Reconcile(ctx, request); err != nil {
			t.Fatal(err)
		}
		current := get(t, ctx, c, request.NamespacedName, new(inferencev1alpha1.ModelService))
		if condition := meta.FindStatusCondition(current.Status.Conditions, readyCondition); condition == nil || condition.Status != metav1.ConditionTrue {
			t.Fatalf("service readiness = %#v", current.Status)
		}
	})

	t.Run("ModelPool cuts over only after the resolved Group is ready", func(t *testing.T) {
		service := modelService("rollout", 1)
		pool := modelPool(service, "rollout-default", 1)
		c := controllerClient(t, service, pool)
		reconciler := &controllers.ModelPoolReconciler{Client: c, TemplateResolver: resolver.StaticModelPoolResolver{RuntimeProfile: resolver.RuntimeProfile{
			Revision: "default", Image: "vllm:test", ModelServerPort: 9000,
			DeviceResourceName: "nvidia.com/gpu",
		}}}
		request := ctrl.Request{NamespacedName: client.ObjectKeyFromObject(pool)}
		if _, err := reconciler.Reconcile(ctx, request); err != nil {
			t.Fatal(err)
		}
		var groups inferencev1alpha1.ModelGroupList
		if err := c.List(ctx, &groups, client.InNamespace(pool.Namespace)); err != nil {
			t.Fatal(err)
		}
		if len(groups.Items) != 1 || !metav1.IsControlledBy(&groups.Items[0], pool) {
			t.Fatalf("initial groups = %#v", groups.Items)
		}
		markGroupReady(&groups.Items[0])
		if err := c.Status().Update(ctx, &groups.Items[0]); err != nil {
			t.Fatal(err)
		}
		if _, err := reconciler.Reconcile(ctx, request); err != nil {
			t.Fatal(err)
		}
		current := get(t, ctx, c, request.NamespacedName, new(inferencev1alpha1.ModelPool))
		oldRevision := current.Status.ActiveRevision
		current.Spec.Template.ModelRevision = "next"
		current.Generation++
		if err := c.Update(ctx, current); err != nil {
			t.Fatal(err)
		}
		if _, err := reconciler.Reconcile(ctx, request); err != nil {
			t.Fatal(err)
		}
		if err := c.List(ctx, &groups, client.InNamespace(pool.Namespace)); err != nil {
			t.Fatal(err)
		}
		if len(groups.Items) != 2 {
			t.Fatalf("rollout groups = %#v", groups.Items)
		}
		current = get(t, ctx, c, request.NamespacedName, new(inferencev1alpha1.ModelPool))
		if current.Status.ActiveRevision != oldRevision {
			t.Fatalf("active revision changed before readiness: %#v", current.Status)
		}
		for index := range groups.Items {
			if groups.Items[index].Spec.Revision != oldRevision {
				markGroupReady(&groups.Items[index])
				if err := c.Status().Update(ctx, &groups.Items[index]); err != nil {
					t.Fatal(err)
				}
			}
		}
		if _, err := reconciler.Reconcile(ctx, request); err != nil {
			t.Fatal(err)
		}
		current = get(t, ctx, c, request.NamespacedName, new(inferencev1alpha1.ModelPool))
		if current.Status.ActiveRevision == oldRevision {
			t.Fatalf("ready target did not become active: %#v", current.Status)
		}
	})
}

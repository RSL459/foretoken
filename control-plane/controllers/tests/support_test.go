// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

package tests

import (
	"context"
	"testing"

	inferencev1alpha1 "github.com/shiweijiezero/foretoken/control-plane/api/v1alpha1"
	appsv1 "k8s.io/api/apps/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/apimachinery/pkg/util/managedfields"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
)

const readyCondition = "Ready"

func pointer[T any](value T) *T { return &value }

func controllerClient(t *testing.T, objects ...client.Object) client.Client {
	t.Helper()
	scheme := runtime.NewScheme()
	if err := clientgoscheme.AddToScheme(scheme); err != nil {
		t.Fatal(err)
	}
	if err := inferencev1alpha1.AddToScheme(scheme); err != nil {
		t.Fatal(err)
	}
	return fake.NewClientBuilder().WithScheme(scheme).WithTypeConverters(managedfields.NewDeducedTypeConverter()).WithStatusSubresource(
		&inferencev1alpha1.ModelService{}, &inferencev1alpha1.ModelPool{},
		&inferencev1alpha1.ModelGroup{}, &appsv1.Deployment{},
	).WithObjects(objects...).Build()
}

func modelService(name string, replicas int32) *inferencev1alpha1.ModelService {
	resources := inferencev1alpha1.ModelResources{Requests: inferencev1alpha1.ModelResourceRequests{
		ComputeResourceRequests: inferencev1alpha1.ComputeResourceRequests{CPU: "1", Memory: "1Gi"},
		GPU:                     inferencev1alpha1.GPURequest{Type: "auto", Count: 1},
	}}
	return &inferencev1alpha1.ModelService{
		TypeMeta:   metav1.TypeMeta{APIVersion: inferencev1alpha1.GroupVersion.String(), Kind: "ModelService"},
		ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: "default", UID: types.UID(name + "-uid"), Generation: 1},
		Spec: inferencev1alpha1.ModelServiceSpec{
			Model: "Qwen/Qwen3-0.6B", ModelRevision: "model-revision", Backend: "vllm", Replicas: &replicas,
			Resources:   &resources,
			Parallelism: &inferencev1alpha1.Parallelism{TP: 1, PP: 1, PCP: 1, DCP: 1},
			Timeouts:    inferencev1alpha1.ModelTimeouts{Startup: "10m", Drain: "2m"},
		},
	}
}

func modelPool(service *inferencev1alpha1.ModelService, name string, desired int32) *inferencev1alpha1.ModelPool {
	return &inferencev1alpha1.ModelPool{
		TypeMeta: metav1.TypeMeta{APIVersion: inferencev1alpha1.GroupVersion.String(), Kind: "ModelPool"},
		ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: service.Namespace, UID: types.UID(name + "-uid"), Generation: 1, OwnerReferences: []metav1.OwnerReference{{
			APIVersion: service.APIVersion, Kind: service.Kind, Name: service.Name, UID: service.UID, Controller: pointer(true),
		}}},
		Spec: inferencev1alpha1.ModelPoolSpec{
			ModelServiceRef: inferencev1alpha1.LocalObjectReference{Name: service.Name, UID: string(service.UID)},
			PoolName:        "default", DesiredGroups: desired,
			Template: inferencev1alpha1.NormalizedPoolTemplate{
				Model: service.Spec.Model, ModelRevision: service.Spec.ModelRevision, Backend: "vllm",
				Role: inferencev1alpha1.ModelRoleAggregate, NodeCount: 1, MemberCount: 1,
				Resources:   *service.Spec.Resources,
				Parallelism: inferencev1alpha1.CompiledParallelism{TP: 1, PP: 1, DP: 1, PCP: 1, DCP: 1},
				Timeouts:    service.Spec.Timeouts,
			},
		},
	}
}

func modelGroup(pool *inferencev1alpha1.ModelPool, name string, ordinal int32) *inferencev1alpha1.ModelGroup {
	return &inferencev1alpha1.ModelGroup{
		TypeMeta: metav1.TypeMeta{APIVersion: inferencev1alpha1.GroupVersion.String(), Kind: "ModelGroup"},
		ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: pool.Namespace, UID: types.UID(name + "-uid"), Generation: 1, OwnerReferences: []metav1.OwnerReference{{
			APIVersion: pool.APIVersion, Kind: pool.Kind, Name: pool.Name, UID: pool.UID, Controller: pointer(true),
		}}},
		Spec: inferencev1alpha1.ModelGroupSpec{
			ModelPoolRef: inferencev1alpha1.LocalObjectReference{Name: pool.Name, UID: string(pool.UID)},
			Revision:     "r1", Ordinal: ordinal, Role: pool.Spec.Template.Role,
			Artifacts: inferencev1alpha1.ModelGroupArtifacts{Model: pool.Spec.Template.Model, ModelRevision: pool.Spec.Template.ModelRevision, Tokenizer: pool.Spec.Template.Model, TokenizerRevision: pool.Spec.Template.ModelRevision},
			Runtime: inferencev1alpha1.ModelGroupRuntime{
				Backend:                               "vllm",
				Image:                                 "vllm:test",
				Port:                                  9000,
				InternalGenerateRequestBodyLimitBytes: inferencev1alpha1.DefaultInternalGenerateRequestBodyLimitBytes,
			},
			Resources: pool.Spec.Template.Resources, Timeouts: pool.Spec.Template.Timeouts,
			NodeCount: 1, MemberCount: 1, Parallelism: pool.Spec.Template.Parallelism,
			Accelerator: inferencev1alpha1.ModelGroupAccelerator{DeviceResourceName: "nvidia.com/gpu", NodeSelector: map[string]string{"nvidia.com/gpu.product": "NVIDIA-H100-80GB-HBM3"}},
		},
	}
}

func markGroupReady(group *inferencev1alpha1.ModelGroup) {
	group.Status.ReadyMembers = group.Spec.MemberCount
	meta.SetStatusCondition(&group.Status.Conditions, metav1.Condition{Type: readyCondition, Status: metav1.ConditionTrue, Reason: "Available", ObservedGeneration: group.Generation})
}

func get[T client.Object](t *testing.T, ctx context.Context, c client.Client, key client.ObjectKey, object T) T {
	t.Helper()
	if err := c.Get(ctx, key, object); err != nil {
		t.Fatal(err)
	}
	return object
}

// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

package controllers

import (
	"fmt"

	inferencev1alpha1 "github.com/shiweijiezero/foretoken/control-plane/api/v1alpha1"
	resourcevalidation "github.com/shiweijiezero/foretoken/control-plane/internal/resources"
)

func validateGroupProfile(group *inferencev1alpha1.ModelGroup) error {
	if err := validateGroupRuntime(group); err != nil {
		return err
	}
	if err := validateGroupKVRuntime(group); err != nil {
		return err
	}
	return validateGroupRole(group)
}

func validateGroupRuntime(group *inferencev1alpha1.ModelGroup) error {
	if group.Spec.NodeCount != 1 || group.Spec.MemberCount != 1 || group.Spec.Runtime.Backend != "vllm" {
		return fmt.Errorf("only single-member vLLM Groups are currently supported")
	}
	return nil
}

func validateGroupKVRuntime(group *inferencev1alpha1.ModelGroup) error {
	runtime := group.Spec.KVRuntime
	if runtime == nil {
		return nil
	}
	if (runtime.Offload == nil) == (runtime.MooncakeStore == nil) {
		return fmt.Errorf("KV runtime must select exactly one storage mode")
	}
	if runtime.Offload != nil {
		if runtime.Offload.CPUBytes < 1 {
			return fmt.Errorf("KV offload CPU bytes must be greater than zero")
		}
		return nil
	}
	return validateMooncakeStoreRuntime(group, runtime.MooncakeStore)
}

func validateMooncakeStoreRuntime(group *inferencev1alpha1.ModelGroup, store *inferencev1alpha1.ModelGroupMooncakeStoreRuntime) error {
	if store.ProfileName == "" || store.ProfileRevision == "" || store.ConfigMapName == "" || store.ConfigMapKey == "" || store.PythonHashSeed == "" {
		return fmt.Errorf("Mooncake Store runtime config is incomplete")
	}
	if store.KVServiceUID != "" && store.RequesterBufferBytes < 1 {
		return fmt.Errorf("managed Mooncake Store requester buffer is incomplete")
	}
	if store.RequesterBufferBytes > 0 {
		if err := resourcevalidation.ValidateRequesterBufferBudget(group.Spec.Resources, store.RequesterBufferBytes); err != nil {
			return fmt.Errorf("managed Mooncake Store requester buffer: %w", err)
		}
	}
	return nil
}

func validateGroupRole(group *inferencev1alpha1.ModelGroup) error {
	if group.Spec.Role != inferencev1alpha1.ModelRoleAggregate {
		return fmt.Errorf("ModelGroup role %q is not enabled by the aggregate runtime profile", group.Spec.Role)
	}
	if group.Spec.PDRuntime != nil || group.Spec.ECRuntime != nil {
		return fmt.Errorf("aggregate Groups must not have split runtime configs")
	}
	return nil
}

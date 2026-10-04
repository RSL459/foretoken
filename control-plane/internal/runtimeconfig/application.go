// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

// Projects platform-selected application files into workload startup.
package runtimeconfig

import (
	"maps"
	"path"

	corev1 "k8s.io/api/core/v1"
)

// ApplicationFiles contains the platform's download tools and application mount layout.
// Controllers use it to prepare immutable application versions before starting a workload.
type ApplicationFiles struct {
	Image     string `json:"image"`
	Script    string `json:"script"`
	MountPath string `json:"mountPath"`
}

// Configure prepares the selected files in a Pod-local volume and starts its executable.
// The Pod owns the volume; application storage and compiler caches remain independent.
func (files ApplicationFiles) Configure(template *corev1.PodTemplateSpec, container *corev1.Container, reference, executable string) {
	if reference == "" {
		return
	}
	template.Labels = maps.Clone(template.Labels)
	if template.Labels == nil {
		template.Labels = make(map[string]string)
	}
	template.Labels["foretoken.io/application-files"] = "consumer"
	template.Annotations = maps.Clone(template.Annotations)
	if template.Annotations == nil {
		template.Annotations = make(map[string]string)
	}
	template.Annotations["inference.foretoken.io/application-url"] = reference
	pod := &template.Spec
	identity := int64(65532)
	noEscalation, readOnly := false, true
	pod.Volumes = append(pod.Volumes, corev1.Volume{
		Name: "application", VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}},
	})
	pod.InitContainers = append(pod.InitContainers, corev1.Container{
		Name: "application-files", Image: files.Image, ImagePullPolicy: corev1.PullIfNotPresent,
		Command:      []string{"python", "-c", files.Script, reference, files.MountPath},
		VolumeMounts: []corev1.VolumeMount{{Name: "application", MountPath: files.MountPath}},
		SecurityContext: &corev1.SecurityContext{
			RunAsUser: &identity, RunAsGroup: &identity,
			AllowPrivilegeEscalation: &noEscalation, ReadOnlyRootFilesystem: &readOnly,
			Capabilities: &corev1.Capabilities{Drop: []corev1.Capability{"ALL"}},
		},
	})
	container.VolumeMounts = append(container.VolumeMounts, corev1.VolumeMount{
		Name: "application", MountPath: files.MountPath, ReadOnly: true,
	})
	container.Command[0] = path.Join(files.MountPath, "current", "bin", executable)
}

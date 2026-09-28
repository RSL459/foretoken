// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

// Reconciles durable VideoTask intent into one controller-owned worker Job.
package controllers

import (
	"context"
	"encoding/json"
	"fmt"
	"path/filepath"
	"time"

	api "github.com/shiweijiezero/foretoken/control-plane/api/v1alpha1"
	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
)

const (
	videoTaskFinalizer   = "inference.foretoken.io/video-task-cleanup"
	videoTaskContract    = "v1"
	videoTaskOutputMount = "/foretoken/output"
)

// VideoTaskReconciler owns the worker Job lifecycle and publishes durable task state.
// The worker owns inference execution and must write the requested artifact before exiting successfully.
type VideoTaskReconciler struct {
	client.Client
	APIReader client.Reader
}

// SetupWithManager registers VideoTask reconciliation and watches its worker Jobs.
func (r *VideoTaskReconciler) SetupWithManager(manager ctrl.Manager) error {
	r.APIReader = manager.GetAPIReader()
	return ctrl.NewControllerManagedBy(manager).
		For(&api.VideoTask{}).
		Owns(&batchv1.Job{}).
		Complete(r)
}

// Reconcile persists a fixed serving plan before creating the worker Job, then observes that Job until completion.
func (r *VideoTaskReconciler) Reconcile(ctx context.Context, request ctrl.Request) (ctrl.Result, error) {
	task := new(api.VideoTask)
	if err := r.APIReader.Get(ctx, request.NamespacedName, task); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	// A terminal task without a planned Job has no external work left to clean up.
	// Planned tasks retain the finalizer during deletion until their Job is gone.
	if videoTaskTerminal(task.Status.Phase) && (task.DeletionTimestamp.IsZero() || task.Status.Plan == nil) {
		return ctrl.Result{}, r.removeVideoTaskFinalizer(ctx, task)
	}
	if task.Status.Plan == nil {
		if !controllerutil.ContainsFinalizer(task, videoTaskFinalizer) {
			base := task.DeepCopy()
			controllerutil.AddFinalizer(task, videoTaskFinalizer)
			return ctrl.Result{Requeue: true}, r.Patch(ctx, task, client.MergeFrom(base))
		}
		if !task.DeletionTimestamp.IsZero() {
			task.Status.Phase = "Cancelled"
			task.Status.Reason = "DeletedBeforeStart"
			task.Status.Message = "VideoTask was deleted before its worker Job was created"
			return ctrl.Result{}, r.writeVideoTaskStatus(ctx, task)
		}
		plan, err := r.prepareVideoTask(ctx, task)
		if err != nil {
			task.Status.Phase, task.Status.Reason, task.Status.Message = "Failed", "TargetUnavailable", err.Error()
			return ctrl.Result{}, r.writeVideoTaskStatus(ctx, task)
		}
		task.Status.Plan = &plan
		task.Status.Phase = "Starting"
		return ctrl.Result{Requeue: true}, r.writeVideoTaskStatus(ctx, task)
	}

	plan := *task.Status.Plan
	job := new(batchv1.Job)
	err := r.APIReader.Get(ctx, client.ObjectKey{Namespace: task.Namespace, Name: plan.JobName}, job)
	if !task.DeletionTimestamp.IsZero() {
		if apierrors.IsNotFound(err) {
			return ctrl.Result{}, r.removeVideoTaskFinalizer(ctx, task)
		}
		if err != nil {
			return ctrl.Result{}, err
		}
		if err := r.Delete(ctx, job, client.PropagationPolicy(metav1.DeletePropagationForeground)); err != nil && !apierrors.IsNotFound(err) {
			return ctrl.Result{}, err
		}
		task.Status.Phase, task.Status.Reason, task.Status.Message = "Cancelled", "DeletionRequested", "worker Job deletion is pending"
		return ctrl.Result{RequeueAfter: time.Second}, r.writeVideoTaskStatus(ctx, task)
	}
	if err != nil && !apierrors.IsNotFound(err) {
		return ctrl.Result{}, err
	}
	if apierrors.IsNotFound(err) {
		service := new(api.ModelService)
		if err := r.APIReader.Get(ctx, client.ObjectKey{Namespace: task.Namespace, Name: task.Spec.ModelServiceRef.Name}, service); err != nil {
			return ctrl.Result{}, err
		}
		if service.Status.ServingGeneration != plan.ServingGeneration || string(service.UID) != plan.ServiceUID {
			task.Status.Phase, task.Status.Reason, task.Status.Message = "Failed", "TargetChanged", "ModelService serving identity changed before worker creation"
			return ctrl.Result{}, r.writeVideoTaskStatus(ctx, task)
		}
		job, err = r.newVideoWorkerJob(task, plan)
		if err != nil {
			task.Status.Phase, task.Status.Reason, task.Status.Message = "Failed", "InvalidWorkerContract", err.Error()
			return ctrl.Result{}, r.writeVideoTaskStatus(ctx, task)
		}
		if err := r.Create(ctx, job); err != nil {
			return ctrl.Result{}, err
		}
		task.Status.JobName = job.Name
		task.Status.Phase = "Running"
		return ctrl.Result{RequeueAfter: time.Second}, r.writeVideoTaskStatus(ctx, task)
	}
	if !metav1.IsControlledBy(job, task) {
		task.Status.Phase, task.Status.Reason, task.Status.Message = "Failed", "JobConflict", "the planned worker Job is not controlled by this VideoTask"
		return ctrl.Result{}, r.writeVideoTaskStatus(ctx, task)
	}
	if task.Status.JobUID == "" {
		task.Status.JobUID = string(job.UID)
	}
	if task.Status.JobUID != string(job.UID) {
		task.Status.Phase, task.Status.Reason, task.Status.Message = "Failed", "JobReplaced", "the planned worker Job was replaced"
		return ctrl.Result{}, r.writeVideoTaskStatus(ctx, task)
	}
	if task.Status.StartedAt == nil && job.Status.StartTime != nil {
		started := job.Status.StartTime.DeepCopy()
		task.Status.StartedAt = started
	}
	switch {
	case job.Status.Succeeded > 0:
		now := metav1.Now()
		task.Status.Phase = "Succeeded"
		task.Status.FinishedAt = &now
		task.Status.Artifact = &api.VideoArtifactReference{ClaimName: plan.OutputClaimName, Path: plan.OutputPath}
		task.Status.Message = "worker Job completed and is contractually responsible for the retained artifact"
	case job.Status.Failed > 0:
		now := metav1.Now()
		task.Status.Phase = "Failed"
		task.Status.Reason = "WorkerFailed"
		task.Status.FinishedAt = &now
		task.Status.Message = "worker Job failed before publishing a successful artifact"
	default:
		task.Status.Phase = "Running"
	}
	if videoTaskTerminal(task.Status.Phase) {
		return ctrl.Result{}, r.writeVideoTaskStatus(ctx, task)
	}
	return ctrl.Result{RequeueAfter: time.Second}, r.writeVideoTaskStatus(ctx, task)
}

// prepareVideoTask snapshots the ready ModelService identity used by the worker contract.
func (r *VideoTaskReconciler) prepareVideoTask(ctx context.Context, task *api.VideoTask) (api.VideoExecutionPlan, error) {
	service := new(api.ModelService)
	if err := r.APIReader.Get(ctx, client.ObjectKey{Namespace: task.Namespace, Name: task.Spec.ModelServiceRef.Name}, service); err != nil {
		return api.VideoExecutionPlan{}, err
	}
	if !modelServiceReady(service) || !meta.IsStatusConditionTrue(service.Status.Conditions, conditionReady) {
		return api.VideoExecutionPlan{}, fmt.Errorf("ModelService must already be Ready")
	}
	if task.Spec.Worker.Image == "" || task.Spec.Worker.Endpoint == "" || task.Spec.Worker.OutputClaimName == "" || task.Spec.Worker.OutputPath == "" {
		return api.VideoExecutionPlan{}, fmt.Errorf("worker image, endpoint, outputClaimName and outputPath are required")
	}
	if filepath.IsAbs(task.Spec.Worker.OutputPath) || filepath.Clean(task.Spec.Worker.OutputPath) == "." || filepath.Clean(task.Spec.Worker.OutputPath) == ".." || len(filepath.Clean(task.Spec.Worker.OutputPath)) >= 256 {
		return api.VideoExecutionPlan{}, fmt.Errorf("outputPath must be a relative path below the worker output mount")
	}
	return api.VideoExecutionPlan{
		Model:             service.Spec.Model,
		ServiceUID:        string(service.UID),
		ServingGeneration: service.Status.ServingGeneration,
		Revisions:         append([]api.ServingPoolRevision(nil), service.Status.ServingPoolRevisions...),
		JobName:           task.Name,
		OutputClaimName:   task.Spec.Worker.OutputClaimName,
		OutputPath:        task.Spec.Worker.OutputPath,
	}, nil
}

// newVideoWorkerJob materializes the stable worker contract. The worker must read the JSON request,
// call the named ModelService, write outputPath on the mounted PVC, and exit zero only after persistence.
func (r *VideoTaskReconciler) newVideoWorkerJob(task *api.VideoTask, plan api.VideoExecutionPlan) (*batchv1.Job, error) {
	requestJSON, err := json.Marshal(task.Spec.Request)
	if err != nil {
		return nil, err
	}
	labels := map[string]string{"inference.foretoken.io/video-task": task.Name}
	job := &batchv1.Job{
		ObjectMeta: metav1.ObjectMeta{Name: plan.JobName, Namespace: task.Namespace, Labels: labels, Annotations: map[string]string{
			"inference.foretoken.io/video-task-contract": videoTaskContract,
			"inference.foretoken.io/video-task-uid":      string(task.UID),
			"inference.foretoken.io/video-output-claim":  plan.OutputClaimName,
			"inference.foretoken.io/video-output-path":   plan.OutputPath,
		}},
		Spec: batchv1.JobSpec{
			BackoffLimit: ptrInt32(0),
			Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: labels}, Spec: corev1.PodSpec{
				RestartPolicy:      corev1.RestartPolicyNever,
				ServiceAccountName: task.Spec.Worker.ServiceAccountName,
				Containers: []corev1.Container{{Name: "video-worker", Image: task.Spec.Worker.Image, Env: []corev1.EnvVar{
					{Name: "FORETOKEN_VIDEO_TASK_UID", Value: string(task.UID)},
					{Name: "FORETOKEN_VIDEO_MODEL_SERVICE", Value: task.Spec.ModelServiceRef.Name},
					{Name: "FORETOKEN_VIDEO_ENDPOINT", Value: task.Spec.Worker.Endpoint},
					{Name: "FORETOKEN_VIDEO_MODEL", Value: plan.Model},
					{Name: "FORETOKEN_VIDEO_REQUEST_JSON", Value: string(requestJSON)},
					{Name: "FORETOKEN_VIDEO_OUTPUT_PATH", Value: plan.OutputPath},
					{Name: "FORETOKEN_VIDEO_OUTPUT_MOUNT", Value: videoTaskOutputMount},
				}, VolumeMounts: []corev1.VolumeMount{{Name: "video-output", MountPath: videoTaskOutputMount}}}},
				Volumes: []corev1.Volume{{Name: "video-output", VolumeSource: corev1.VolumeSource{PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{ClaimName: plan.OutputClaimName}}}},
			}},
		},
	}
	if err := controllerutil.SetControllerReference(task, job, r.Scheme()); err != nil {
		return nil, err
	}
	return job, nil
}

func (r *VideoTaskReconciler) writeVideoTaskStatus(ctx context.Context, task *api.VideoTask) error {
	task.Status.ObservedGeneration = task.Generation
	return r.Status().Update(ctx, task)
}

func (r *VideoTaskReconciler) removeVideoTaskFinalizer(ctx context.Context, task *api.VideoTask) error {
	if !controllerutil.ContainsFinalizer(task, videoTaskFinalizer) {
		return nil
	}
	base := task.DeepCopy()
	controllerutil.RemoveFinalizer(task, videoTaskFinalizer)
	return r.Patch(ctx, task, client.MergeFrom(base))
}

func videoTaskTerminal(phase string) bool {
	return phase == "Succeeded" || phase == "Failed" || phase == "Cancelled"
}

func ptrInt32(value int32) *int32 { return &value }

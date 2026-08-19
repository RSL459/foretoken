// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
//
// Starts the Foretoken control-plane manager and health endpoints.

package main

import (
	"errors"
	"flag"
	"os"
	"strings"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"

	inferencev1alpha1 "github.com/shiweijiezero/foretoken/control-plane/api/v1alpha1"
	"github.com/shiweijiezero/foretoken/control-plane/controllers"
	"github.com/shiweijiezero/foretoken/control-plane/internal/resolver"
)

type stringListFlag []string

func (values *stringListFlag) String() string {
	return strings.Join(*values, ",")
}

func (values *stringListFlag) Set(value string) error {
	if value == "" {
		return errors.New("value must not be empty")
	}
	*values = append(*values, value)
	return nil
}

func main() {
	var metricsAddress string
	var probeAddress string
	var leaderElection bool
	var inferenceEngineProfileRevision string
	var inferenceEngineImage string
	var modelServerPort int
	var gpuResourceName string
	var runtimeClassName string
	var gpuNodeSelectorKey string
	var gpuNodeSelectorValue string
	var workloadImagePullSecrets stringListFlag

	// Metrics stay disabled until the chart exposes a secured endpoint.
	flag.StringVar(&metricsAddress, "metrics-bind-address", "0", "Metrics endpoint bind address; 0 disables metrics.")
	flag.StringVar(&probeAddress, "health-probe-bind-address", ":8081", "Health probe bind address.")
	flag.BoolVar(&leaderElection, "leader-elect", false, "Enable leader election.")
	flag.StringVar(&inferenceEngineProfileRevision, "inference-engine-profile-revision", "default", "Opaque revision of the configured inference engine profile.")
	flag.StringVar(&inferenceEngineImage, "inference-engine-image", "", "Inference engine image containing the Foretoken model-server adapter.")
	flag.IntVar(&modelServerPort, "model-server-port", 9000, "Internal model-server HTTP port.")
	flag.StringVar(&gpuResourceName, "gpu-resource-name", "nvidia.com/gpu", "Kubernetes extended resource used for accelerator devices.")
	flag.StringVar(&runtimeClassName, "runtime-class-name", "", "Optional RuntimeClass for inference engine Pods.")
	flag.StringVar(&gpuNodeSelectorKey, "gpu-node-selector-key", "", "Node label key for the configured GPU profile.")
	flag.StringVar(&gpuNodeSelectorValue, "gpu-node-selector-value", "", "Node label value for the configured GPU profile.")
	flag.Var(&workloadImagePullSecrets, "workload-image-pull-secret", "Namespace-local image pull Secret for inference workloads; may be repeated.")

	logOptions := zap.Options{Development: false}
	logOptions.BindFlags(flag.CommandLine)
	flag.Parse()
	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&logOptions)))
	if modelServerPort < 1 || modelServerPort > 65535 {
		ctrl.Log.Error(errors.New("model-server-port must be between 1 and 65535"), "invalid inference engine profile")
		os.Exit(1)
	}
	controlPlaneNamespace := os.Getenv("POD_NAMESPACE")
	if controlPlaneNamespace == "" {
		ctrl.Log.Error(errors.New("POD_NAMESPACE is required"), "unable to configure ModelGroup networking")
		os.Exit(1)
	}

	// Register built-in and Foretoken APIs before controllers are attached to the manager.
	scheme := runtime.NewScheme()
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(inferencev1alpha1.AddToScheme(scheme))

	manager, err := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
		Scheme:                 scheme,
		Metrics:                metricsserver.Options{BindAddress: metricsAddress},
		HealthProbeBindAddress: probeAddress,
		LeaderElection:         leaderElection,
		LeaderElectionID:       "inference.foretoken.io",
	})
	if err != nil {
		ctrl.Log.Error(err, "unable to create manager")
		os.Exit(1)
	}

	workloadPullSecrets := make([]corev1.LocalObjectReference, len(workloadImagePullSecrets))
	for index, name := range workloadImagePullSecrets {
		workloadPullSecrets[index] = corev1.LocalObjectReference{Name: name}
	}

	// Controllers are registered explicitly so each resource keeps one lifecycle owner.
	if err := (&controllers.ModelServiceReconciler{Client: manager.GetClient()}).SetupWithManager(manager); err != nil {
		ctrl.Log.Error(err, "unable to register ModelService controller")
		os.Exit(1)
	}
	if err := (&controllers.ModelPoolReconciler{
		Client: manager.GetClient(),
		TemplateResolver: resolver.StaticModelPoolResolver{RuntimeProfile: resolver.RuntimeProfile{
			Revision:           inferenceEngineProfileRevision,
			Image:              inferenceEngineImage,
			ModelServerPort:    int32(modelServerPort),
			DeviceResourceName: gpuResourceName,
			RuntimeClassName:   runtimeClassName,
			NodeSelectorKey:    gpuNodeSelectorKey,
			NodeSelectorValue:  gpuNodeSelectorValue,
		}},
	}).SetupWithManager(manager); err != nil {
		ctrl.Log.Error(err, "unable to register ModelPool controller")
		os.Exit(1)
	}
	if err := (&controllers.ModelGroupReconciler{Client: manager.GetClient(), ControlPlaneNamespace: controlPlaneNamespace, ImagePullSecrets: workloadPullSecrets}).SetupWithManager(manager); err != nil {
		ctrl.Log.Error(err, "unable to register ModelGroup controller")
		os.Exit(1)
	}

	// These endpoints are consumed by the liveness and readiness probes in the Helm chart.
	if err := manager.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		ctrl.Log.Error(err, "unable to register health check")
		os.Exit(1)
	}
	if err := manager.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		ctrl.Log.Error(err, "unable to register readiness check")
		os.Exit(1)
	}

	ctrl.Log.Info("starting manager")
	if err := manager.Start(ctrl.SetupSignalHandler()); err != nil {
		ctrl.Log.Error(err, "manager stopped with an error")
		os.Exit(1)
	}
}

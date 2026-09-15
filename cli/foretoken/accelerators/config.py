# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""GPU resource identities shared by runtime selection and metric discovery."""

from typing import Final

NVIDIA_GPU_RESOURCE: Final = "nvidia.com/gpu"
METAX_GPU_RESOURCES: Final = ("metax-tech.com/gpu", "metax-tech.com/sgpu")
GPU_RESOURCE_BACKENDS: Final = {
    NVIDIA_GPU_RESOURCE: "nvidia",
    **{resource: "metax" for resource in METAX_GPU_RESOURCES},
}

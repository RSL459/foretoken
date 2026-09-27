<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Model recipes

English | [简体中文](README_zh.md)

Model-specific Foretoken deployments. Each recipe includes its hardware and runtime requirements, configuration, request and cleanup commands.

| Model | Hardware and precision | Status |
|---|---|---|
| [GLM-5.3-Flash](glm-5.3-flash/metax-bf16/) | Two nodes, 16 MetaX C500 GPUs, BF16, MTP and shared memory KV | End-to-end validation in progress |
| [MiniMax H3](minimax-h3/a100-bf16-tp2/) | One node, 2 NVIDIA A100 80 GB GPUs, native BF16, TP2; FL2VA or Ref2VA | FL2VA and Ref2VA generation through the standard frontend validated with cached original HF weights |

# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Replay timestamped conversation traces against one OpenAI-compatible URL."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Iterator

from benchmarks.client.openai_client import OpenAICompatClient
from benchmarks.metrics.aggregator import percentile_stats
from benchmarks.runner.base import Runner
from benchmarks.workload.trace_loader import TraceRequest
from benchmarks.workload.trace_workload import load_trace_workload


class TraceRunner(Runner):
    """Replay recorded user turns while retaining dataset-provided context."""

    def connection_limit(self) -> int | None:
        """Match the HTTP pool to the trace active-request ceiling."""
        return self.config.dataset.trace_max_concurrency

    async def _send(
        self,
        client: OpenAICompatClient,
        request: TraceRequest,
        index: int,
        *,
        scheduled_at: float,
    ) -> tuple[int, dict[str, Any]]:
        generation = self.config.generation
        actual_send_at = time.perf_counter()
        result = await client.generate_stream(
            prompt=request.prompt,
            messages=request.messages,
            tools=request.tools,
            max_tokens=generation.max_tokens,
            temperature=generation.temperature,
        )
        result["source_index"] = request.source_index
        result["conversation_id"] = request.conversation_id
        result["trace_timestamp_s"] = request.timestamp_s
        result["trace_input_length"] = request.input_length
        result["payload_source"] = request.payload_source
        replay_delay = max(0.0, actual_send_at - scheduled_at)
        result["replay_delay"] = replay_delay
        result["trace_e2e_latency"] = replay_delay + float(result["latency"])
        if result["ttft"] is not None:
            result["trace_e2e_ttft"] = replay_delay + float(result["ttft"])
        else:
            result["trace_e2e_ttft"] = None
        return index, result

    @staticmethod
    def _add_trace_metrics(
        metrics: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> None:
        successful = [result for result in results if result["success"]]
        for name in ("replay_delay", "trace_e2e_ttft", "trace_e2e_latency"):
            values = [
                float(result[name])
                for result in successful
                if result[name] is not None
            ]
            metrics[name] = percentile_stats(values)

    async def _replay(
        self,
        client: OpenAICompatClient,
        requests: Iterator[TraceRequest],
        *,
        max_concurrency: int | None,
        window_start_s: float,
    ) -> dict[str, Any]:
        """Schedule trace requests at their recorded arrival times."""

        pending: set[asyncio.Task[tuple[int, dict[str, Any]]]] = set()
        completed: dict[int, dict[str, Any]] = {}

        def collect(
            done: set[asyncio.Task[tuple[int, dict[str, Any]]]],
        ) -> None:
            for task in done:
                index, result = task.result()
                completed[index] = result

        start_time = time.perf_counter()
        request_count = 0
        for request in requests:
            scheduled_at = start_time + request.timestamp_s - window_start_s
            delay = scheduled_at - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)

            done = {task for task in pending if task.done()}
            if done:
                pending.difference_update(done)
                collect(done)

            while (
                max_concurrency is not None
                and len(pending) >= max_concurrency
            ):
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                collect(done)

            task = asyncio.create_task(
                self._send(
                    client,
                    request,
                    request_count,
                    scheduled_at=scheduled_at,
                )
            )
            pending.add(task)
            request_count += 1

        end_time = start_time
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not pending:
                end_time = time.perf_counter()
            collect(done)

        return {
            "results": [completed[index] for index in range(request_count)],
            "total_time": end_time - start_time,
        }

    async def run(self) -> dict[str, Any]:
        dataset = self.config.dataset
        max_concurrency = dataset.trace_max_concurrency
        metrics_parallel = -1 if max_concurrency is None else max_concurrency
        trace_load = {
            "parallel": metrics_parallel,
            "number": 0,
            "rate": -1.0,
            "open_loop": False,
            "resolved_parallel": metrics_parallel,
        }
        writer = self.make_writer()
        run_config = self.build_run_config("trace", trace_load)
        run_config.update(
            {
                "dataset": f"trace={dataset.trace_path}",
                "trace_path": dataset.trace_path,
                "trace_format": dataset.trace_format,
                "trace_start": dataset.trace_start,
                "trace_duration": dataset.trace_duration,
                "trace_max_concurrency": max_concurrency,
            }
        )
        wandb_logger = self.make_wandb_logger(writer, trace_load)
        client = self.make_client()

        try:
            window_start_s, payload_source, requests = load_trace_workload(
                self.config
            )
            run_config["payload_source"] = payload_source
            raw_output = await self._replay(
                client,
                iter(requests),
                max_concurrency=max_concurrency,
                window_start_s=window_start_s,
            )
            request_count = len(raw_output["results"])
            run_config["number"] = request_count
            run_config["resolved"]["number"] = request_count
            metrics = self.aggregate_metrics(
                raw_output,
                rate=-1.0,
                number=request_count,
                resolved_parallel=metrics_parallel,
                include_user_throughput=False,
            )
            self._add_trace_metrics(metrics, raw_output["results"])
            self.save_results(
                writer,
                run_config,
                raw_output,
                metrics,
                wandb_logger=wandb_logger,
            )
        except Exception:
            wandb_logger.finish()
            raise
        finally:
            await client.close()

        return {
            "mode": "trace",
            "metrics": metrics,
            "output_dir": writer.output_dir,
        }

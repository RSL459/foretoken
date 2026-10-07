# Local conversations

English | [简体中文](conversations_zh.md) · [Performance examples](README.md)

Replay recorded conversations to measure the cost of growing history and sequential turns. After [setup](README.md#setup), run the [sample dataset](../../examples/conversations.jsonl):

```bash
foretoken perf examples/quickstart \
  --dataset benchmarks/examples/conversations.jsonl \
  --num-prompts 3 --max-concurrency 2 --output local
```

This sends three HTTP requests: one single-turn conversation and one two-turn conversation. A conversation's next turn waits for its previous response. `--num-prompts` counts HTTP turns across all conversations; `--max-concurrency` limits conversations in progress. Add `--max-turns 1` to keep only the first user turn of each conversation, and adjust the request budget accordingly.

## Prepare your data

Save one JSON object per line. For example, `conversations.jsonl` can contain:

```json
{"messages":[{"role":"user","content":"Name a planet."},{"role":"assistant","content":"Mars."},{"role":"user","content":"Name another one."}]}
```

Replace the sample path with this file in the command. `messages` uses OpenAI-style roles and content, including system messages and image content for image-capable models. A row can instead contain a string `prompt`, or `user` with optional `system`. JSON arrays of conversation records are also accepted. See [ShareGPT](sharegpt.md), [Hugging Face sources](huggingface.md), and [tool data](tools.md) for other inputs.

Optional row fields control individual requests:

| Field | Meaning |
| --- | --- |
| `model` | Served model ID; otherwise use the selected service model |
| `output_length` | Positive integer exact output-token target |
| `priority` | Integer sent to a service supporting priority scheduling |
| `request_class` | Label used to group benchmark results, such as `interactive` |

Rows can supply model IDs instead of `--model` for URL or multi-model deployments. An integer-array `prompt`, such as `{"prompt":[1,42,73],"output_length":32}`, sends one pre-tokenized Completions request without a chat template; token IDs must match the served model's tokenizer.

## Choose conversation history

The default `--conversation-history dataset` uses recorded assistant answers in later requests, while generating a new response at each turn for measurement. Use `--conversation-history generated` to carry the service's actual answers forward instead.

## Control output length

A turn with a non-empty text reference answer generates the same number of tokens as that answer. Length is counted before measurement using the request model's tokenizer, without special tokens. `--tokenizer-path` overrides it for a serving alias or separately stored tokenizer.

Output targets follow this order: a row's `output_length`, an explicit `--min-output-length`/`--max-output-length` range, then the recorded answer's token count. A turn without a text reference uses `--max-tokens` and can end naturally. Exact targets require `min_tokens`, `ignore_eos`, and reported token usage; a missed target counts as a failed request.

Inspect target and actual token counts, request labels, and per-turn timing in the results. [Multiple datasets](multi-dataset.md) combines conversation sources in one workload.

![Conversation timings and token counts](../imgs/local-dataset-wandb-dashboard.png)

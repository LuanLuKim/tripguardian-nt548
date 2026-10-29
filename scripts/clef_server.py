"""Serve a Cloudflare Clef decision model over the Jev/SystemOne HTTP API.

Clef answers typed questions in one forward pass (no generation), so the server
only needs the weights plus activations. The backbone is split across the GPUs
visible to the process (set CUDA_VISIBLE_DEVICES), in fp16 because the host GPUs
are Turing (no native bf16).

    CUDA_VISIBLE_DEVICES=1,2 HF_HOME=$PWD/.cache/hf \
        .venv/bin/python scripts/clef_server.py --model Cloudflare/clef-flash --port 30000
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import queue
import sys
import threading
from pathlib import Path
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from huggingface_hub import snapshot_download
from PIL import Image
from safetensors.torch import load_file


def load_model(model_id: str, dtype: torch.dtype, gib_per_gpu: float, quant: str = "none", double_quant: bool = False):
    path = Path(snapshot_download(model_id))
    sys.path.insert(0, str(path))
    import json

    from joint_schema_model import ClefModel, JointSchemaHead
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

    count = torch.cuda.device_count()
    extra = {}
    if quant != "none":  # bitsandbytes weight-only quantization; the vision tower and lm_head stay in fp16
        from transformers import BitsAndBytesConfig

        extra["quantization_config"] = (
            BitsAndBytesConfig(load_in_8bit=True, llm_int8_skip_modules=["visual", "lm_head"])
            if quant == "int8"
            else BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=quant,
                bnb_4bit_compute_dtype=dtype,
                bnb_4bit_use_double_quant=double_quant,
                llm_int8_skip_modules=["visual", "lm_head"],
            )
        )
    backbone = Qwen3_5ForConditionalGeneration.from_pretrained(
        path,
        dtype=dtype,
        device_map="auto",
        max_memory={index: f"{gib_per_gpu}GiB" for index in range(count)},
        **extra,
    )
    backbone.config.use_cache = False
    head_device = backbone.model.language_model.norm.weight.device
    head = JointSchemaHead(**json.loads((path / "joint_head_config.json").read_text()))
    head.load_state_dict(load_file(path / "joint_head.safetensors"), strict=True)
    head = head.to(device=head_device, dtype=dtype)
    processor = AutoProcessor.from_pretrained(path)
    return ClefModel(backbone, head).eval(), processor, head_device


def decode_images(values: list[Any]) -> list[Image.Image]:
    images = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("images must be base64 strings or data URIs")
        payload = value.split(",", 1)[1] if value.startswith("data:") else value
        images.append(Image.open(io.BytesIO(base64.b64decode(payload))).convert("RGB"))
    return images


def validate(request: dict[str, Any]) -> None:
    questions = request.get("questions")
    if "state" not in request:
        raise ValueError("state is required")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("at least one question is required")
    for question_id, question in questions.items():
        if question.get("type") not in ("noul", "choice", "score"):
            raise ValueError(f"{question_id}: type must be noul, choice, or score")
        if question["type"] != "noul" and not question.get("criteria"):
            raise ValueError(f"{question_id}: criteria must not be empty")
        if question["type"] == "choice" and not isinstance(question["criteria"], dict):
            raise ValueError(f"{question_id}: choice criteria must be an object of option -> description")
    if request.get("videos"):
        raise ValueError("videos are not supported by this host")


def batches(encoded: list, max_tokens: int) -> list[list[int]]:
    """Group indices of text-only records so that rows x longest row stays under max_tokens; media records go alone."""
    groups: list[list[int]] = []
    text = sorted((index for index, record in enumerate(encoded) if not record.media), key=lambda index: len(encoded[index].input_ids))
    current: list[int] = []
    for index in text:
        longest = len(encoded[index].input_ids)  # sorted ascending, so the newest row is the longest
        if current and (len(current) + 1) * longest > max_tokens:
            groups.append(current)
            current = []
        current.append(index)
    if current:
        groups.append(current)
    groups.extend([index] for index, record in enumerate(encoded) if record.media)
    return groups


def build_app(model_id: str, model, processor, head_device, max_length: int, max_batch_tokens: int = 16384) -> FastAPI:
    from joint_schema_model import collate_records, encode_record, systemone_answer

    app = FastAPI(title="clef-host")
    # One worker thread runs every forward: a pool thread that touches CUDA keeps its own cuBLAS workspace
    # (~18 MiB per GPU, never freed), so ~30 concurrent requests used up the GPU headroom and OOM'd for good.
    # Requests that arrive while a forward runs wait in `pending` and go into the next forward together.
    first_device = next(model.parameters()).device
    pending: queue.Queue = queue.Queue()

    def forward(records: list) -> list:
        batch = collate_records(records, processor.tokenizer.pad_token_id, first_device)
        # The head lives on the last pipeline device; its index tensors must follow it.
        base = model.language_model
        media = batch["media"]
        text_model = base.model if media else base.model.language_model
        with torch.inference_mode():
            hidden = text_model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                use_cache=False,
                return_dict=True,
                **media,
            ).last_hidden_state
            return model.head(
                hidden,
                batch["input_ids"].to(head_device),
                batch["attention_mask"].to(head_device),
                batch["records"],
                base.get_output_embeddings().weight.to(head_device),
            )

    def reply(request: dict[str, Any], encoded, logits: list) -> dict[str, Any]:
        questions = request["questions"]
        answers = {
            question.question_id: systemone_answer(
                questions[question.question_id],
                dict(zip(question.option_ids, question_logits.float().softmax(-1).tolist())),
            )
            for question, question_logits in zip(encoded.questions, logits)
        }
        return {
            "model": request.get("model", model_id),
            "answers": answers,
            "usage": {"input_tokens": len(encoded.input_ids), "output_tokens": 0},
        }

    def settle(job, result=None, error: BaseException | None = None) -> None:
        loop, future = job[1], job[2]
        if error is None:
            loop.call_soon_threadsafe(lambda: future.done() or future.set_result(result))
        else:
            loop.call_soon_threadsafe(lambda: future.done() or future.set_exception(error))

    def run(jobs: list) -> None:
        encoded, ready = [], []
        for job in jobs:
            request = job[0]
            try:
                validate(request)
                record = dict(request)
                if request.get("images"):
                    record["images"] = decode_images(request["images"])
                encoded.append(encode_record(processor.tokenizer, record, max_length=max_length, processor=processor))
                ready.append(job)
            except Exception as error:  # noqa: BLE001 - a bad request fails alone, not the batch
                settle(job, error=error if isinstance(error, ValueError) else ValueError(str(error)))
        for group in batches(encoded, max_tokens=max_batch_tokens):
            logits = attempt([encoded[index] for index in group])
            if logits is None and len(group) > 1:
                # Out of memory: retry one by one so a big batch never fails every request.
                logits = [(attempt([encoded[index]]) or [None])[0] for index in group]
            for index, record_logits in zip(group, logits or [None] * len(group)):
                if isinstance(record_logits, BaseException):
                    settle(ready[index], error=record_logits)
                elif record_logits is None:
                    settle(ready[index], error=RuntimeError("CUDA out of memory"))
                else:
                    try:
                        settle(ready[index], reply(ready[index][0], encoded[index], record_logits))
                    except Exception as error:  # noqa: BLE001
                        settle(ready[index], error=error)

    def attempt(records: list) -> list | None:
        """Forward, or None on CUDA OOM. The cache is emptied after the except block, once the
        traceback (which holds the activations) is gone; inside it nothing would be freed."""
        try:
            return forward(records)
        except torch.cuda.OutOfMemoryError:
            pass
        except Exception as error:  # noqa: BLE001
            return [error] * len(records)
        torch.cuda.empty_cache()
        return None

    def warm_up() -> None:
        """First forwards load CUDA kernels (~3 s); pay that before serving, on the forward thread."""
        record = encode_record(processor.tokenizer, {"state": {"message": "warm up"}, "questions": {"q": {"type": "noul", "instructions": "Is this a test?"}}}, max_length=max_length)
        for rows in (1, 2, 4):
            if attempt([record] * rows) is None:
                break

    def worker() -> None:
        warm_up()
        while True:
            jobs = [pending.get()]
            while True:
                try:
                    jobs.append(pending.get_nowait())
                except queue.Empty:
                    break
            run(jobs)

    threading.Thread(target=worker, name="clef-forward", daemon=True).start()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "model": model_id, "queued": pending.qsize()}

    @app.get("/v1/models")
    def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": model_id, "object": "model"}]}

    @app.post("/v1/systemone")
    async def systemone(request: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        pending.put((request, loop, future))
        try:
            return await future
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Cloudflare/clef-flash")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=30000)
    parser.add_argument("--dtype", choices=("float16", "bfloat16"), default="float16")
    parser.add_argument("--quant", choices=("none", "nf4", "fp4", "int8"), default="none", help="weight-only bitsandbytes quantization, to fit one GPU")
    parser.add_argument("--gib-per-gpu", type=float, default=9.6)
    parser.add_argument("--max-length", type=int, default=16384)
    parser.add_argument("--max-batch-tokens", type=int, default=16384, help="rows x longest row per forward; queued requests share one forward up to this")
    parser.add_argument("--double-quant", action="store_true", help="nf4/fp4: also quantize the quant constants (saves ~0.4 GB, slower)")
    parser.add_argument("--fp32-accumulate", action="store_true", help="accumulate fp16 matmuls in fp32 (slower on Turing; default fp16)")
    args = parser.parse_args()
    # Turing GeForce runs fp16-accumulate tensor-core GEMMs at ~2x the fp32-accumulate rate: ~20 % per forward.
    torch.backends.cuda.matmul.allow_fp16_accumulation = not args.fp32_accumulate

    model, processor, head_device = load_model(args.model, getattr(torch, args.dtype), args.gib_per_gpu, args.quant, args.double_quant)
    app = build_app(args.model, model, processor, head_device, args.max_length, args.max_batch_tokens)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

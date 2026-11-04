import asyncio
import re

import httpx
import openai
import pytest

from corpus.observe.tiktok import extract
from corpus.ontology import load


def context_error(message="This model's maximum context length is 32768 tokens"):
    return openai.BadRequestError(message, response=httpx.Response(
        400, request=httpx.Request("POST", "https://fake.invalid")), body=None)


def video(count):
    return {"video_id": "v1", "caption": "mountain view", "hashtags": ["view"], "author_id": "u1",
            "transcript": {"total_s": count, "check": {"screen_text": ["SIGN"]}, "segments": [
                {"start_s": i, "end_s": i + 1, "status": "ok", "checked_text": f"mountain view number {i}"}
                for i in range(count)]}}


def obs(source, ref, quote):
    return {"feature": "scenic_view", "value": "present", "source": source, "ref": ref, "quote": quote}


class Task:
    prompt_hash = "fake"

    def __init__(self, limit=4, error=None):
        self.calls, self.limit, self.error = [], limit, error

    async def ask(self, client, model, **fields):
        self.calls.append(fields)
        segments = re.findall(r"\[(\d+)\] \([^\n]*?s\) ([^\n]*)", fields["segments"])
        if self.error is not None:
            raise self.error
        if len(segments) > self.limit:
            raise context_error()
        return {"observations": [obs("speech", int(i), text) for i, text in segments]
                + [obs("caption", 0, "mountain view")], "details": []}


def observe(task, monkeypatch, tmp_path, count=9):
    monkeypatch.setattr(extract, "VIDEO_OBSERVE", task)
    return asyncio.run(extract.observe_pair(None, "fake", asyncio.Semaphore(1), "Dalat", video(count),
                                           tmp_path, {"fid": "P", "name": "Place"}, ["Other"], load()))


def test_context_overflow_splits_all_evidence_and_deduplicates_overlap(monkeypatch, tmp_path):
    task = Task()
    observations, details, dropped = observe(task, monkeypatch, tmp_path)
    speech = [o for o in observations if o["source_type"] == "tiktok_segment"]
    assert {o["span"]["quote"] for o in speech} == {f"mountain view number {i}" for i in range(9)}
    assert len(speech) == 9
    assert len([o for o in observations if o["source_type"] == "tiktok_caption"]) == 1
    assert len({o["id"] for o in observations}) == len(observations)
    assert {o["span"]["start_s"] for o in speech} == set(range(9))
    assert not details and not dropped
    assert len(task.calls) > 1
    assert all(c["desc"] == "mountain view" and c["screen_text"] == "SIGN" for c in task.calls)
    assert all(c["others"] == "Other" and c["images"] == [] for c in task.calls)


def test_small_video_keeps_one_call(monkeypatch, tmp_path):
    task = Task()
    observations, _, _ = observe(task, monkeypatch, tmp_path, count=2)
    assert len(task.calls) == 1 and len(observations) == 3


@pytest.mark.parametrize("count", [0, 1, 2])
def test_unsplittable_context_error_stays_explicit_without_partial_success(monkeypatch, tmp_path, count):
    task = Task(error=context_error())
    with pytest.raises(openai.BadRequestError):
        observe(task, monkeypatch, tmp_path, count=count)
    assert len(task.calls) <= 2


def test_non_context_bad_request_is_never_retried_as_windows(monkeypatch, tmp_path):
    task = Task(error=context_error("unsupported response_format"))
    with pytest.raises(openai.BadRequestError, match="unsupported response_format"):
        observe(task, monkeypatch, tmp_path)
    assert len(task.calls) == 1


def test_window_gate_rejects_quotes_from_segments_not_seen_in_that_call(monkeypatch, tmp_path):
    class CrossWindowTask(Task):
        async def ask(self, *args, **fields):
            result = await super().ask(*args, **fields)
            if "[9]" not in fields["segments"]:
                result["observations"].append(obs("speech", 9, "mountain view number 8"))
            return result

    task = CrossWindowTask()
    observations, _, dropped = observe(task, monkeypatch, tmp_path)
    assert len([o for o in observations if o["span"]["quote"] == "mountain view number 8"]) == 1
    assert dropped["quote_not_in_segment"] > 0

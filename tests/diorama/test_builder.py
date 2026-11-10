import copy
import json

import pytest

from auto3d import Place
from auto3d import builder, prompts


def test_apply_patch():
    original = {"objects": [{"id": "a", "type": "wall", "color": "yellow", "size": [2, 3]},
                            {"id": "b", "type": "tree"}], "hotspots": ["old"], "route": ["unchanged"]}
    before = copy.deepcopy(original)
    patch = {"add": [{"id": "c", "type": "roof"}], "update": [{"id": "a", "color": "white"}, {"id": "unknown", "x": 1}],
             "remove": ["b", "absent"], "hotspots": ["new"]}
    with pytest.warns(UserWarning) as reported:
        result = builder.apply_patch(original, patch)
    assert original == before
    assert result["objects"] == [{"id": "a", "type": "wall", "color": "white", "size": [2, 3]}, {"id": "c", "type": "roof"}]
    assert result["hotspots"] == ["new"] and result["route"] == ["unchanged"]
    assert {str(x.message) for x in reported} == {"Unknown update id: unknown", "Unknown remove id: absent"}
    result["objects"][0]["size"].append(4)
    assert original == before
    assert builder.apply_patch(original, {"route": []})["route"] == []


def test_agent_brief_has_catalogue_and_feedback(isolated, monkeypatch):
    monkeypatch.setattr(prompts, "catalogue", lambda kit: "FULL CATALOGUE CONTENT")
    monkeypatch.setattr(prompts, "example", lambda kit: {"objects": [{"id": "example", "type": "villa"}]})
    p = Place("p")
    p.s["notes"] = {"kit": "villa", "evidence": ["g03"], "signature": [], "interior": False}
    p.s["history"] = [{"step": "build", "round": 1, "changes": "Moved entrance east"}]
    p.s["review"] = {"items": [{"id": "s2", "status": "weak", "fix": "sloped roof"}]}
    brief = builder.build_brief(p, '[{"id":"s1","status":"wrong","fix":"yellow plaster"}]')
    assert "FULL CATALOGUE CONTENT" in brief
    assert '"id": "example"' in brief
    assert "yellow plaster" in brief and "Moved entrance east" in brief
    assert "sloped roof" in brief
    assert "approximate with the closest object types" in brief
    assert "logs/" not in brief
    assert "At most 3 boot/build/shot/look cycles" in brief
    assert str(isolated) in brief


def test_function_uses_full_then_patch(isolated, monkeypatch):
    monkeypatch.setattr(prompts, "catalogue", lambda kit: "## kit\n### `villa`\nwall options\n### `other`\nUNUSED SECTION")
    monkeypatch.setattr(prompts, "example", lambda kit: {"objects": [{"id": "example"}]})
    p = Place("p")
    p.save()
    p.s["notes"] = {"kit": "villa", "evidence": ["g03"], "interior": False}
    captured = []
    outputs = iter([{"objects": [{"id": "a", "type": "villa", "color": "red"}]},
                    {"update": [{"id": "a", "color": "yellow"}]}])

    def ask(prompt, images, effort):
        captured.append((prompt, images, effort))
        return next(outputs), {"input_tokens": 20, "output_tokens": 10}

    monkeypatch.setattr(builder, "ask", ask)
    assert builder.FunctionBuilder().build(p, None).tokens == 30
    assert builder.FunctionBuilder().build(p, "wrong colour").ok
    assert "UNUSED SECTION" in captured[0][0]
    assert "approximate with the closest object types" in captured[0][0]
    assert "UNUSED SECTION" not in captured[1][0]
    assert "wrong colour" in captured[1][0]
    assert captured[0][1] == [p.dir / "photos/g03.jpg"]
    assert json.loads((p.dir / "place.json").read_text())["objects"][0]["color"] == "yellow"


def test_build_large_effort(isolated, monkeypatch):
    p = Place("p")
    p.s["notes"] = {"kit": "villa", "interior": False}
    monkeypatch.setattr(prompts, "example", lambda kit: {"objects": [{}] * 40})
    assert builder.build_effort(p) == "high"
    monkeypatch.setattr(prompts, "example", lambda kit: {"objects": [{}]})
    assert builder.build_effort(p) == "medium"
    p.s["notes"]["interior"] = True
    assert builder.build_effort(p) == "high"


def test_multi_kit_brief_uses_primary_example_only(isolated, monkeypatch):
    monkeypatch.setattr(prompts, "catalogue", lambda kit: f"FULL {kit} CATALOGUE")
    examples = []
    monkeypatch.setattr(prompts, "example", lambda kit: examples.append(kit) or {"objects": []})
    p = Place("p")
    p.s["notes"] = {"kit": "storefront", "extra_kits": ["nature"], "evidence": []}
    brief = builder.build_brief(p)
    assert brief.index("FULL storefront CATALOGUE") < brief.index("FULL nature CATALOGUE")
    assert 'Set "kits" to exactly ["storefront", "nature"]' in brief
    assert examples == ["storefront"]
    assert builder.build_effort(p) == "high"


def test_kits_for_primary_first_and_deduplicated():
    assert prompts.kits_for({"kit": "storefront"}) == ["storefront"]
    assert prompts.kits_for({"kit": "storefront", "extra_kits": ["nature", "storefront", "nature"]}) == ["storefront", "nature"]


def test_function_multi_kit_catalogues_and_kits_repair(isolated, monkeypatch):
    monkeypatch.setattr(prompts, "catalogue", lambda kit:
                        f"## {kit}\n### `{kit}_main`\nSUPPORTED {kit}\n### `unused`\nUNUSED {kit}")
    monkeypatch.setattr(prompts, "example", lambda kit: {"objects": []})
    p = Place("p")
    p.s["notes"] = {"kit": "storefront", "extra_kits": ["nature"], "evidence": []}
    p.save()
    seen = []
    outputs = iter([{"kits": ["storefront"], "objects": [
        {"id": "a", "type": "storefront_main"}, {"id": "b", "type": "nature_main"}]},
        {"kits": ["storefront", "nature"]}])

    def ask(prompt, images, effort):
        seen.append(prompt)
        return next(outputs), {}

    monkeypatch.setattr(builder, "ask", ask)
    assert builder.FunctionBuilder().build(p, None).ok
    assert builder.FunctionBuilder().build(p, "missing nature kit").ok
    for prompt in seen:
        assert "SUPPORTED storefront" in prompt and "SUPPORTED nature" in prompt
        assert 'Set "kits" to exactly ["storefront", "nature"]' in prompt
    assert "UNUSED storefront" in seen[0] and "UNUSED nature" in seen[0]
    assert "UNUSED storefront" not in seen[1] and "UNUSED nature" not in seen[1]
    assert json.loads((p.dir / "place.json").read_text())["kits"] == ["storefront", "nature"]


def test_agent_session_counts_tokens_without_a_real_command(isolated, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(prompts, "catalogue", lambda kit: "catalogue")
    monkeypatch.setattr(prompts, "example", lambda kit: {"objects": [{}]})
    p = Place("p")
    p.s.update(notes={"kit": "villa", "evidence": ["g00"]}, rounds=1)
    p.save()
    seen = []

    def command(args, **kwargs):
        seen.append((args, kwargs))
        (p.dir / "build_1.log").write_text("done\ntokens used\n12,345\n")
        (p.dir / "place.json").write_text('{"objects": []}')
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(builder.subprocess, "run", command)
    result = builder.AgentBuilder().build(p, None)
    assert result.ok and result.tokens == 12345
    assert seen[0][0][6] == "sol"
    assert seen[0][0][-1] == str(p.dir / "photos/g00.jpg")
    assert seen[0][1]["env"]["DIORAMA_DATA"] == str(isolated)
    assert seen[0][1]["timeout"] == 3600
    assert seen[0][1]["start_new_session"] is True
    assert '--add-dir "$DATA"' in (builder.CODE / "run_agent.sh").read_text()


def test_agent_timeout_is_failed_round(isolated, monkeypatch):
    import subprocess
    import signal

    p = Place("p")
    p.s.update(notes={"kit": "villa", "evidence": []}, rounds=1)
    p.save()
    monkeypatch.setattr(builder, "build_brief", lambda *args: "brief")
    monkeypatch.setattr(builder, "build_effort", lambda *args: "medium")
    killed = []
    monkeypatch.setattr(builder.os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    def command(args, **kwargs):
        assert kwargs["timeout"] == 3600 and kwargs["start_new_session"]
        (p.dir / "build_1.log").write_text("tokens used: 42")
        from pathlib import Path
        Path(args[4]).write_text("123456")
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(builder.subprocess, "run", command)
    result = builder.AgentBuilder().build(p, None)
    assert not result.ok and "agent timeout" in result.log
    assert result.tokens == 42
    assert killed == [(123456, signal.SIGKILL)]
    assert not list(p.dir.glob("*.pid"))


@pytest.mark.parametrize("failures", [[{}, {"objects": [{"id": "a", "type": "villa"}]}],
                                      [RuntimeError("network"), RuntimeError("network again")],
                                      [{}, TypeError("bad response")]])
def test_function_retries_rejected_answers(isolated, monkeypatch, failures):
    p = Place("p")
    p.s["notes"] = {"kit": "villa", "interior": False, "evidence": []}
    p.save()
    monkeypatch.setattr(prompts, "catalogue", lambda kit: "catalogue")
    monkeypatch.setattr(prompts, "example", lambda kit: {"objects": []})
    answers = iter(failures)
    calls = []

    def ask(prompt, images, effort):
        calls.append((prompt, images, effort))
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer, {"total_tokens": 9}

    monkeypatch.setattr(builder, "ask", ask)
    result = builder.FunctionBuilder().build(p, None)
    assert result.ok == isinstance(failures[1], dict)
    assert result.tokens == 9 * sum(isinstance(x, dict) for x in failures)
    assert len(calls) == 2 and "rejected" in calls[1][0]
    assert calls[0][1:] == calls[1][1:]
    if not result.ok:
        assert "response" in result.log or "network" in result.log
        assert not (p.dir / "place.json").exists()

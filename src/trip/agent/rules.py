"""Trip's rules around the shared tool loop (agents.assistant.loop): what a reply that claims a record, a refused fact
or an unmapped wish does to the turn. TurnTools inherits it."""

import json
import re

from agents.assistant.loop import LoopHost

from ..domain.guard import trim_say
from ..domain.text import fold

# Words in a reply that say something was written down. Such a reply with no record_fact in the turn is retried once.
CLAIM = ("da ghi", "ghi nhan", "ghi lai", "da cap nhat", "cap nhat lai", "da luu", "hieu la", "da hieu", "minh hieu")
REPLY_NOTE = ("Câu trả lời vừa rồi bị chặn vì: {why}. Viết lại một câu ngắn: không hứa kết quả, không nêu số hay "
              "địa điểm mà user chưa nói.")
RETRY_NOTE = ("Bạn vừa nói đã ghi nhận nhưng chưa gọi record_fact lần nào trong lượt này. Nếu tin nhắn mới nhất có "
              "một fact, hãy gọi record_fact cho fact đó ngay. Nếu không, đừng nói là đã ghi nhận.")
UNMAPPED_TEXT_NOTE = ("Bạn vừa ghi unmapped cho mong muốn này. Viết ngay một câu ngắn bằng lời user: nhắc lại mong muốn "
                      "và hỏi đúng MỘT câu tư vấn đưa nó về giá trị ghi được (hai cách hiểu cụ thể gắn với enum của field đó). "
                      "Không gọi thêm tool nào nữa.")
# The notes above are only ever sent to the model (as `user` messages); this is how the persisted history recognises them.
NOTE_HEADS = tuple(n[:24] for n in (REPLY_NOTE.format(why=""), RETRY_NOTE, UNMAPPED_TEXT_NOTE))
# Facts about tastes, not about the trip's frame or safety: when only these are refused and the reply is written, the
# turn ends without a second model call; dates, who goes, transport, budget, limits are always fixed
WISH_FIELDS = frozenset({"soft", "purpose", "liked_groups", "novelty", "crowd_tolerance", "time_preference", "like",
                         "dish", "kind", "unmapped"})


class TripRules(LoopHost):
    note_heads = NOTE_HEADS

    def trim(self, text: str) -> str:
        return trim_say(text)

    def finalize_reply(self, text: str) -> str:
        """Check the final reply after all writes, not the model's pre-tool acknowledgement."""
        text = trim_say(text)
        if not text:
            return text
        # Never turn an unsaved exclusion into a promise, even when unrelated writes succeeded.
        exclusion_request = re.search(r"\b(?:bo|loai|dung goi y|dung xep|khong goi y|khong xep)\b", fold(self.text))
        covered = any(e.turn == self.turn and e.quote and e.quote in self.text
                      for p in self.state.excluded_places for e in p.evidence)
        if exclusion_request and re.search(r"\b(?:se khong|khong goi y|khong xep)\b", fold(text)) and (
                "excluded_place" in self.refused or not covered):
            text = "Mình chưa áp dụng được yêu cầu loại nơi này vì chưa ghi được địa điểm loại trừ."
        # A return to lodging carries no evening taste; remove only an unsupported nightlife question.
        if re.search(r"\b\d{1,2}h\s+ve\b", fold(self.text)) and not re.search(
                r"\b(?:bar|nhac|buoi toi|ve dem)\b", fold(self.text)):
            text = " ".join(s for s in re.split(r"(?<=[.!?])\s+", text) if not (
                "?" in s and re.search(r"\b(?:buoi toi|ve dem|soi dong)\b", fold(s))))
        from .tools import lookups
        if not hasattr(self, "_reply_lookups"):
            self._reply_lookups = lookups(self.text, self.catalog)
        found = self._reply_lookups
        for dish in found.get("dishes", ()):
            name = dish.get("also_named")
            if name and dish.get("dish_places_with_that_name") == 0 and fold(name) not in fold(text):
                text = f"Mình không thấy quán {name} trong dữ liệu. " + text
        # A partial model reply must name the unanswered question rather than silently skip it.
        questions = [q.strip() for q in self.text.split("?")[:-1] if q.strip()]
        if len(questions) > 1:
            topics = ((r"\b(?:lanh|thoi tiet|khi hau)\b", r"\b(?:lanh|thoi tiet|khi hau|nhiet do)\b", "thời tiết"),
                      (r"\b(?:an gi|mon|an uong)\b", r"\b(?:an|mon|banh|bun|pho|lau)\b", "ăn uống"),
                      (r"\b(?:di lai|phuong tien)\b", r"\b(?:di lai|phuong tien|taxi|grab|xe buyt|di bo)\b", "đi lại"))
            for question in questions:
                for asked, answered, label in topics:
                    if re.search(asked, fold(question)) and not re.search(answered, fold(text)):
                        text += f" Về {label}, mình chưa có dữ liệu để trả lời câu hỏi này."
        return text.strip()

    def start_calls(self) -> None:
        self.settled = False

    def review(self, text: str, nudged: bool, state: dict) -> tuple[str, str] | None:
        """A reply with no tool call: a claim with nothing recorded, or a reply Clef sends back, gets the turn's one
        second chance; anything else ends the turn."""
        if not nudged and not self.recorded and any(c in fold(text) for c in CLAIM):
            # the reply says it wrote something, but no record_fact ran: the streamed text is dropped and the
            # model gets one more try, told what it claimed
            return "claim_without_record", RETRY_NOTE
        if not nudged and (why := self.reply_problem()):
            # Clef sent the reply back (a promise, or a fact nobody gave): the model is told why and writes again
            return f"clef_retry {why}", REPLY_NOTE.format(why=why)
        if self.refused:
            self.log.append(f"refusal_unresolved {sorted(self.refused)}")
        return None

    def after_call(self, state: dict, out: list[dict], fails: int) -> dict | None:
        if self.asked is not None:  # a card was asked for: the engine builds it, the turn ends here
            return {"messages": out, "fails": fails, "ended": True}
        if self.unmapped:
            if not state["nudged"] and not (state["reply_content"] or "").strip():
                # recorded but said nothing: one more round for the consultative question, then it ends
                self.log.append("unmapped_without_text")
                return {"messages": out + [{"role": "user", "content": UNMAPPED_TEXT_NOTE}],
                        "nudged": True, "fails": fails}
            return {"messages": out, "fails": fails, "ended": True}
        return None

    def after_calls(self, state: dict, out: list[dict], fails: int) -> dict:
        # a rejected fact must not silently turn into an unrelated question: the agent corrects it, clarifies
        # the rejected field
        only = state["reply_calls"][0] if len(state["reply_calls"]) == 1 else {}
        if (self.refused and self.refused <= WISH_FIELDS and (state["reply_content"] or "").strip()
                and only.get("name") == "record_fact"):
            # only tastes were refused and the reply is written: no second call for them. Each is kept as a wish in
            # the user's words (the summary shows it as not applied) and the next turn sees why it was refused.
            self.keep_refused_wishes(json.loads(only["arguments"] or "{}"), out)
            self.log.append(f"refusal_kept {sorted(self.refused)}")
            return {"messages": out, "fails": fails, "ended": True}
        if self.refused:
            self.log.append(f"resolve_refusal {sorted(self.refused)}")
        elif self.settled and (state["reply_content"] or "").strip() and len(state["reply_calls"]) == 1:
            # the facts and the reply came in one call and every fact stood: no second call is needed
            return {"messages": out, "fails": fails, "ended": True}
        return {"messages": out, "fails": fails}

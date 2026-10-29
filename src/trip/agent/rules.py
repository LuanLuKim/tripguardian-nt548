"""Trip's rules around the shared tool loop (agents.assistant.loop): what a reply that claims a record, a refused fact
or an unmapped wish does to the turn. TurnTools inherits it."""

import json

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

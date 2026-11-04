"""Production journey cases: the hidden truth of one traveller, how they talk, and what "satisfied" means
(config/prod_journey_cases.yaml; run by scripts/prod_journey_e2e.py). Pure data + validation, no network."""

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "config" / "prod_journey_cases.yaml"

Who = Literal["solo", "partner", "friends", "kids", "parents", "baby", "pet", "coworkers"]
Vehicle = Literal["motorbike", "car", "walk"]
Care = Literal["steps", "wheelchair", "pregnant", "motion_sick", "height", "vegetarian", "vegan"]
Stated = Literal["trip", "companions", "mobility", "care", "pace", "budget", "lodging"]  # the required keys the user already said in chat
TurnKind = Literal["opening", "detail", "service", "weather", "challenge", "change_mind", "contradiction", "dish", "place_real", "place_fake"]
HardFlag = Literal["vegetarian", "wheelchair", "no_stairs", "no_bar", "no_alcohol", "pets"]
Group = Literal["meal", "snack", "cafe", "nature", "garden", "camping", "sights", "culture", "fun", "night", "spa", "market"]  # config/decision.yaml tabs


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Truth(Strict):
    days: int = Field(ge=1, le=7)
    start: date | None = None            # None: the traveller has no date yet and says so
    people: int = Field(ge=1, le=20)
    companions: list[Who] = Field(min_length=1)
    mobility: Vehicle
    arrive: Literal["self", "bus", "plane"] = "self"
    origin: str | None = None            # where they set out from (TP.HCM, Nha Trang, Hà Nội)
    start_hour: str | None = Field(None, pattern=r"^\d\d:\d\d$")   # when day 1 begins, as they say it
    end_hour: str | None = Field(None, pattern=r"^\d\d:\d\d$")
    pace: Literal["slow", "normal", "packed"] | None = None
    budget_vnd: int | None = None        # per person per day; None: no number given
    budget_unlimited: bool = False
    care: list[Care] = Field(default_factory=list)
    lodging: str | None = None           # a stay they already booked (name as they say it), else none
    max_per_day: int | None = Field(None, ge=1, le=8)
    wants: list[str] = Field(default_factory=list)
    dishes: list[str] = Field(default_factory=list)
    real_places: list[str] = Field(default_factory=list)   # named places that exist in the corpus
    fake_places: list[str] = Field(default_factory=list)   # named places that do not: the system must say so
    notes: str = ""                      # constraints said in words (allergy, no alcohol, cold-averse, pet, ...)


class Turn(Strict):
    text: str = Field(min_length=2)
    kind: TurnKind = "detail"


class Pick(Strict):
    mode: Literal["few", "medium", "many"]
    n: int = Field(ge=1, le=40)
    include: list[str] = Field(default_factory=list)       # names to take when the list shows them (else searched)
    groups: list[Group] = Field(default_factory=list)      # preferred groups in order; empty = display order
    avoid_groups: list[Group] = Field(default_factory=list)
    no_lodging_pick: bool = False


class Edit(Strict):
    op: Literal["drop_first", "drop_name", "add_backup", "set_day_window", "move_first", "assistant", "set_pace"]
    name: str | None = None
    day: int | None = None
    start: str | None = None
    end: str | None = None
    text: str | None = None
    level: Literal["slow", "normal", "packed"] | None = None
    verify: Literal["absent", "present", "day_window", "none"] = "none"   # what the plan must show afterwards (name / day / start / end)

    @model_validator(mode="after")
    def _args(self):
        need = {"drop_name": ("name",), "set_day_window": ("day", "start", "end"), "move_first": ("day",),
                "assistant": ("text",), "set_pace": ("level",)}.get(self.op, ())
        for f in need:
            if getattr(self, f) is None:
                raise ValueError(f"edit {self.op} needs {f}")
        if self.verify in ("absent", "present") and not (self.name or self.op in ("drop_first", "add_backup")):
            raise ValueError(f"edit {self.op} verify {self.verify} needs a name")
        return self


class Expect(Strict):
    stated: list[Stated] = Field(default_factory=list)
    chat_evidence: dict[Literal["people", "companions", "pace", "start_hour", "end_hour"], str] = Field(default_factory=dict)
    hard: list[HardFlag] = Field(default_factory=list)
    start_hour: str | None = Field(None, pattern=r"^\d\d:\d\d$")
    criteria: list[str] = Field(min_length=3, max_length=7)  # what "satisfied" means, each checkable from the plan / chat


class Case(Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    auth: Literal["guest", "dev"] = "guest"
    axes: list[str] = Field(min_length=2)       # which user-axes this case covers (traveller, experience, time, ...)
    persona: str                                # how this person talks (fed to the user simulator)
    truth: Truth
    chat: list[Turn] = Field(min_length=1)
    sim_replies: int = Field(2, ge=0, le=4)     # answers the simulator writes to the agent's open questions
    pick: Pick
    edits: list[Edit] = Field(default_factory=list)
    expect: Expect

    @model_validator(mode="after")
    def _consistent(self):
        t = self.truth
        if self.chat[0].kind != "opening":
            raise ValueError(f"{self.id}: the first turn is the opening")
        if "partner" in t.companions and t.people < 2:
            raise ValueError(f"{self.id}: partner needs 2+ people")
        if t.companions != ["solo"] and "solo" in t.companions:
            raise ValueError(f"{self.id}: solo is alone")
        if "solo" in t.companions and t.people != 1:
            raise ValueError(f"{self.id}: solo is one person")
        if t.start and t.start < date(2026, 11, 4):
            raise ValueError(f"{self.id}: start date is in the past")
        for h in self.expect.hard:
            need = {"vegetarian": "vegetarian", "wheelchair": "wheelchair"}.get(h)
            if need and need not in t.care:
                raise ValueError(f"{self.id}: hard {h} needs care {need}")
        if self.expect.start_hour != t.start_hour:
            raise ValueError(f"{self.id}: expect.start_hour is the truth.start_hour (the gate answers it when chat did not)")
        if self.pick.mode == "few" and self.pick.n > 3:
            raise ValueError(f"{self.id}: few is 1-3 places")
        if self.pick.mode == "many" and self.pick.n < 12:
            raise ValueError(f"{self.id}: many is 12+ places")
        if self.auth == "dev" and "QA matrix" not in self.chat[0].text:
            raise ValueError(f"{self.id}: a dev-account trip is marked QA matrix in its opening")
        return self


def load(path: Path = CASES) -> list[Case]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = [Case.model_validate(c) for c in raw["cases"]]
    ids = [c.id for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case id")
    return cases

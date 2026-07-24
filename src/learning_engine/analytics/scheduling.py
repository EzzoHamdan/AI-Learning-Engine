"""Spaced-repetition scheduling (SM-2).

Flashcards used to be a one-shot exercise: flip through a deck, close the tab,
start from scratch tomorrow. With the Phase 6 store there is somewhere durable
to record how each card went, so a card you find hard can come back sooner and
one you know can go quiet for weeks.

The algorithm is SuperMemo-2, the scheduler behind Anki. Each review produces a
grade; from the grade and the card's history it computes an interval in days and
an "ease factor" that stretches or compresses future intervals.

Pure functions of the review state — no storage, no Streamlit (rule R1). The
store persists what these return.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import IntEnum

# SM-2's floor: below this an item's intervals collapse and it is shown constantly.
MIN_EASE = 1.3
DEFAULT_EASE = 2.5


class Grade(IntEnum):
    """How a review went, in the three buttons the UI actually offers.

    SM-2 defines grades 0-5; a flashcard UI with six buttons is worse than one
    with three, so these map onto the meaningful thresholds: FORGOT is a lapse
    (below SM-2's passing grade of 3), HARD passes but shortens the next
    interval, EASY passes and lengthens it.
    """

    FORGOT = 0
    HARD = 3
    EASY = 5


@dataclass(frozen=True)
class ReviewState:
    """A card's scheduling state. `due` is None for a card never reviewed."""

    repetitions: int = 0
    interval_days: int = 0
    ease: float = DEFAULT_EASE
    due: date | None = None

    @property
    def is_new(self) -> bool:
        return self.repetitions == 0 and self.due is None


def review(state: ReviewState, grade: Grade, today: date) -> ReviewState:
    """Return the card's new scheduling state after a review graded `grade`.

    A lapse (FORGOT) resets the repetition count and shows the card again the
    same day, because a card you just failed is not learned. Passing grades
    follow SM-2's 1 day -> 6 days -> interval * ease progression.
    """
    # SM-2 applies the updated ease to this review's interval, not the old one.
    ease = _adjust_ease(state.ease, grade)

    if grade < Grade.HARD:
        # Lapse: start the ladder over, but keep the (now lower) ease.
        return ReviewState(repetitions=0, interval_days=0, ease=ease, due=today)

    repetitions = state.repetitions + 1
    if repetitions == 1:
        interval = 1
    elif repetitions == 2:
        interval = 6
    else:
        interval = max(1, round(state.interval_days * ease))

    return ReviewState(
        repetitions=repetitions,
        interval_days=interval,
        ease=ease,
        due=today + timedelta(days=interval),
    )


def _adjust_ease(ease: float, grade: Grade) -> float:
    """SM-2's ease update, clamped at MIN_EASE.

    The standard formula is EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02)).
    Its neutral point is q=4, not q=5: a perfect recall (EASY, q=5) *raises*
    ease by 0.1 so the card recedes faster each time, HARD (q=3) lowers it by
    0.14, and FORGOT (q=0) by 0.8. There is deliberately no upper clamp — a card
    you never miss should end up years out, which is the point of the algorithm.
    """
    q = int(grade)
    updated = ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    return max(MIN_EASE, round(updated, 4))


def is_due(state: ReviewState, today: date) -> bool:
    """A card is due if it has never been reviewed or its due date has arrived."""
    return state.due is None or state.due <= today


def due_cards(states: dict[str, ReviewState], today: date) -> list[str]:
    """Card keys to study now, most overdue first, new cards last.

    Overdue-first keeps the backlog from growing; new cards go last so a big
    fresh deck cannot bury reviews that are already owed.
    """
    overdue = [(key, s) for key, s in states.items() if s.due is not None and s.due <= today]
    new = [key for key, s in states.items() if s.due is None]
    overdue.sort(key=lambda item: item[1].due or today)
    return [key for key, _ in overdue] + new


def next_due_summary(states: dict[str, ReviewState], today: date) -> dict[str, int]:
    """Counts for the deck header: due now, learning, and scheduled ahead."""
    due = 0
    learning = 0
    scheduled = 0
    for card_state in states.values():
        if is_due(card_state, today):
            due += 1
        elif card_state.repetitions < 3:
            learning += 1
        else:
            scheduled += 1
    return {"due": due, "learning": learning, "scheduled": scheduled, "total": len(states)}

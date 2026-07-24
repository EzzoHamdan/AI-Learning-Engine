"""Tests for the SM-2 spaced-repetition scheduler.

Scheduling bugs are quiet: a card that never comes back, or one stuck in a
same-day loop, looks like normal behavior until weeks of study are wasted. The
interval ladder and the ease arithmetic are therefore pinned exactly.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from learning_engine.analytics.scheduling import (
    DEFAULT_EASE,
    MIN_EASE,
    Grade,
    ReviewState,
    due_cards,
    is_due,
    next_due_summary,
    review,
)

TODAY = date(2026, 7, 24)


# --------------------------------------------------------------------------- #
# The interval ladder
# --------------------------------------------------------------------------- #


def test_a_new_card_is_due():
    assert ReviewState().is_new
    assert is_due(ReviewState(), TODAY)


def test_first_pass_schedules_one_day_out():
    after = review(ReviewState(), Grade.EASY, TODAY)
    assert after.repetitions == 1
    assert after.interval_days == 1
    assert after.due == TODAY + timedelta(days=1)


def test_second_pass_schedules_six_days_out():
    """SM-2's fixed second step, before intervals start compounding."""
    after = review(review(ReviewState(), Grade.EASY, TODAY), Grade.EASY, TODAY)
    assert after.repetitions == 2
    assert after.interval_days == 6


def test_third_pass_multiplies_by_the_ease_factor():
    """SM-2 applies the freshly-updated ease, not the ease the card had before."""
    state = review(review(ReviewState(), Grade.EASY, TODAY), Grade.EASY, TODAY)
    after = review(state, Grade.EASY, TODAY)
    assert after.interval_days == round(state.interval_days * after.ease)
    assert after.due == TODAY + timedelta(days=after.interval_days)


def test_intervals_keep_growing_with_repeated_success():
    state = ReviewState()
    intervals = []
    for _ in range(6):
        state = review(state, Grade.EASY, TODAY)
        intervals.append(state.interval_days)
    assert intervals == sorted(intervals)
    assert intervals[-1] > 30, "a well-known card should eventually go quiet for a month+"


# --------------------------------------------------------------------------- #
# Lapses
# --------------------------------------------------------------------------- #


def test_forgetting_resets_the_ladder_and_shows_the_card_again_today():
    learned = review(
        review(review(ReviewState(), Grade.EASY, TODAY), Grade.EASY, TODAY), Grade.EASY, TODAY
    )
    lapsed = review(learned, Grade.FORGOT, TODAY)

    assert lapsed.repetitions == 0
    assert lapsed.interval_days == 0
    assert lapsed.due == TODAY
    assert is_due(lapsed, TODAY), "a card you just failed must not disappear until tomorrow"


def test_a_lapse_lowers_the_ease_so_the_card_returns_more_often():
    lapsed = review(ReviewState(), Grade.FORGOT, TODAY)
    assert lapsed.ease < DEFAULT_EASE


def test_ease_never_falls_below_the_floor():
    """Without the clamp, intervals collapse and the card is shown forever."""
    state = ReviewState()
    for _ in range(20):
        state = review(state, Grade.FORGOT, TODAY)
    assert state.ease == MIN_EASE


def test_hard_passes_but_shrinks_future_intervals():
    easy = review(ReviewState(), Grade.EASY, TODAY)
    hard = review(ReviewState(), Grade.HARD, TODAY)

    assert hard.repetitions == 1, "Hard is still a pass"
    assert hard.ease < easy.ease


def test_easy_raises_the_ease_so_the_card_recedes_faster():
    """SM-2's neutral point is q=4; a perfect recall (q=5) adds 0.1."""
    assert review(ReviewState(), Grade.EASY, TODAY).ease == pytest.approx(DEFAULT_EASE + 0.1)


# --------------------------------------------------------------------------- #
# Queue ordering
# --------------------------------------------------------------------------- #


def test_only_cards_whose_due_date_has_arrived_are_due():
    tomorrow = ReviewState(repetitions=1, interval_days=1, due=TODAY + timedelta(days=1))
    assert not is_due(tomorrow, TODAY)
    assert is_due(tomorrow, TODAY + timedelta(days=1))


def test_due_queue_puts_the_most_overdue_first_and_new_cards_last():
    """New cards go last so a fresh deck cannot bury reviews already owed."""
    states = {
        "new": ReviewState(),
        "slightly_overdue": ReviewState(repetitions=2, due=TODAY - timedelta(days=1)),
        "very_overdue": ReviewState(repetitions=2, due=TODAY - timedelta(days=9)),
        "not_yet": ReviewState(repetitions=2, due=TODAY + timedelta(days=3)),
    }
    assert due_cards(states, TODAY) == ["very_overdue", "slightly_overdue", "new"]


def test_summary_counts_split_due_learning_and_scheduled():
    states = {
        "due": ReviewState(repetitions=1, due=TODAY),
        "learning": ReviewState(repetitions=1, due=TODAY + timedelta(days=1)),
        "known": ReviewState(repetitions=5, due=TODAY + timedelta(days=40)),
    }
    assert next_due_summary(states, TODAY) == {
        "due": 1,
        "learning": 1,
        "scheduled": 1,
        "total": 3,
    }


def test_an_empty_deck_summarizes_to_zeroes():
    assert next_due_summary({}, TODAY)["total"] == 0


@pytest.mark.parametrize("grade", list(Grade))
def test_every_grade_produces_a_usable_schedule(grade):
    after = review(ReviewState(), grade, TODAY)
    assert after.due is not None
    assert after.interval_days >= 0
    assert after.ease >= MIN_EASE

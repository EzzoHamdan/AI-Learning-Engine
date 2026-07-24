"""Interactive flashcard deck with self-assessment tracking."""

from __future__ import annotations

import hashlib
import random
from datetime import date

import streamlit as st

from learning_engine.analytics.scheduling import Grade, ReviewState, next_due_summary, review
from learning_engine.models import Flashcard, FlashcardDeck
from learning_engine.ui import state


def card_key(card: Flashcard) -> str:
    """A stable identity for a card, so scheduling survives regeneration.

    Decks are regenerated per document and card `id`s restart at 1, so the id is
    not identity. Hashing the question text means the same card generated again
    keeps the history it has already earned.
    """
    return hashlib.sha256(card.front.strip().lower().encode("utf-8")).hexdigest()[:16]


def _grade_card(card: Flashcard, grade: Grade, outcome: str, total_cards: int) -> None:
    """Record a graded review: session stats, analytics, and the SM-2 schedule."""
    state.flashcard_stats()[outcome] += 1
    state.tracker().track_flashcard_interaction(outcome)

    store = state.store()
    if store is not None:
        key = card_key(card)
        current = store.review_states([key]).get(key, ReviewState())
        store.save_review(key, review(current, grade, date.today()))

    next_card(total_cards)


def display_flashcards(deck: FlashcardDeck) -> None:
    """Display interactive flashcards (FlashcardDeck model)."""
    flashcards = deck.flashcards
    if not flashcards:
        st.warning("No flashcards generated.")
        return

    state.init_flashcards()

    total_cards = len(flashcards)
    # Guard against an index left over from a previously longer deck.
    if state.current_flashcard() >= total_cards:
        state.set_current_flashcard(0)
    current_card = flashcards[state.current_flashcard()]

    # Progress and stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Progress", f"{state.current_flashcard() + 1}/{total_cards}")
    with col2:
        st.metric("Correct", state.flashcard_stats()["correct"])
    with col3:
        st.metric("Difficulty", current_card.difficulty.title())
    with col4:
        _render_due_metric(flashcards)

    with st.container():
        st.subheader(f"🔄 Card {state.current_flashcard() + 1}")
        st.caption(
            f"Category: {current_card.category} | Difficulty: {current_card.difficulty.title()}"
        )
        st.markdown("### 📝 Question:")
        st.write(current_card.front or "No question available")

        if current_card.hint and not state.flashcard_answer_visible():
            with st.expander("💡 Hint"):
                st.write(current_card.hint)

        if state.flashcard_answer_visible():
            st.markdown("### ✅ Answer:")
            st.success(current_card.back or "No answer available")

            # The three grades feed SM-2: how well you knew it sets when it returns.
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("😊 Easy", key="correct", help="You knew it — show it again later"):
                    _grade_card(current_card, Grade.EASY, "correct", total_cards)
            with col2:
                if st.button("🤔 Hard", key="hard", help="You got it, but it was a struggle"):
                    _grade_card(current_card, Grade.HARD, "correct", total_cards)
            with col3:
                if st.button("😔 Forgot", key="incorrect", help="Show this one again soon"):
                    _grade_card(current_card, Grade.FORGOT, "incorrect", total_cards)
            with col4:
                if st.button("🔄 Flip Back", key="flip_back"):
                    state.set_flashcard_answer_visible(False)
                    st.rerun()
        else:
            if st.button("🔄 Show Answer", key="show_answer", type="primary"):
                state.set_flashcard_answer_visible(True)
                state.tracker().track_flashcard_interaction("viewed")
                st.rerun()

    # Navigation
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Previous") and state.current_flashcard() > 0:
            state.set_current_flashcard(state.current_flashcard() - 1)
            state.set_flashcard_answer_visible(False)
            st.rerun()
    with col2:
        if st.button("🔄 Shuffle Cards"):
            random.shuffle(deck.flashcards)
            state.set_current_flashcard(0)
            state.set_flashcard_answer_visible(False)
            st.success("Cards shuffled!")
            st.rerun()
    with col3:
        if st.button("➡️ Next") and state.current_flashcard() < total_cards - 1:
            state.set_current_flashcard(state.current_flashcard() + 1)
            state.set_flashcard_answer_visible(False)
            st.rerun()

    if deck.study_tips:
        with st.expander("💡 Study Tips"):
            for tip in deck.study_tips:
                st.write(f"• {tip}")


def _render_due_metric(flashcards: list[Flashcard]) -> None:
    """Show how many cards in this deck are due, if scheduling is available."""
    store = state.store()
    if store is None:
        st.metric("Due", "—", help="Persistent storage unavailable")
        return

    keys = [card_key(card) for card in flashcards]
    stored = store.review_states(keys)
    # Cards with no stored review are new, and new cards are due.
    states = {key: stored.get(key, ReviewState()) for key in keys}
    summary = next_due_summary(states, date.today())
    st.metric(
        "Due today",
        summary["due"],
        help=(
            f"{summary['learning']} still learning · {summary['scheduled']} scheduled ahead. "
            "Grading a card schedules when it comes back."
        ),
    )


def next_card(total_cards: int) -> None:
    """Advance to the next flashcard, looping back to the first after the last.

    total_cards must be the real deck length (BUG-3: the old version read a
    session key nothing ever set, so every self-assessment jumped to card 1).
    """
    if state.current_flashcard() < total_cards - 1:
        state.set_current_flashcard(state.current_flashcard() + 1)
    else:
        state.set_current_flashcard(0)  # Loop back to beginning
    state.set_flashcard_answer_visible(False)
    st.rerun()

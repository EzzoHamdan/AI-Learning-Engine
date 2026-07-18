"""Interactive flashcard deck with self-assessment tracking."""

from __future__ import annotations

import random

import streamlit as st

from learning_engine.models import FlashcardDeck
from learning_engine.ui import state


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
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Progress", f"{state.current_flashcard() + 1}/{total_cards}")
    with col2:
        st.metric("Correct", state.flashcard_stats()["correct"])
    with col3:
        st.metric("Difficulty", current_card.difficulty.title())

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

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("😊 Got it right!", key="correct"):
                    state.flashcard_stats()["correct"] += 1
                    state.tracker().track_flashcard_interaction("correct")
                    next_card(total_cards)
            with col2:
                if st.button("😔 Got it wrong", key="incorrect"):
                    state.flashcard_stats()["incorrect"] += 1
                    state.tracker().track_flashcard_interaction("incorrect")
                    next_card(total_cards)
            with col3:
                if st.button("⏭️ Skip", key="skip"):
                    state.flashcard_stats()["skipped"] += 1
                    state.tracker().track_flashcard_interaction("skipped")
                    next_card(total_cards)
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

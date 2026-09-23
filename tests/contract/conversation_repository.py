"""ConversationRepository contract — architecture.md section 17 "Contract tests".

Written once and run against **every** implementation. When the PostgreSQL
adapter is added, it subclasses this mixin and supplies a factory; if the
in-memory implementation has drifted from real SQL behaviour, these tests are
where it shows.

This is a plain mixin, not a ``TestCase``, so unittest discovery does not run
it on its own.
"""

from __future__ import annotations

from src.domain.conversations.records import Session, Turn
from src.domain.conversations.repository import (
    DuplicateTurnIndex,
    IdempotencyConflict,
    SessionAlreadyExists,
    SessionClosed,
    SessionNotFound,
)


def make_session(**overrides) -> Session:
    fields = dict(
        id="example-session-1",
        run_id="example-run-1",
        external_session_id="example-external-1",
        source_version_id="example-source@1",
        scenario_id="example-scenario-1",
        raw_theme_label="Grandiose Delusions",
        companion_condition="client_companion",
        created_at="2026-01-01T00:00:00Z",
    )
    fields.update(overrides)
    return Session(**fields)


def make_turn(**overrides) -> Turn:
    fields = dict(
        id="example-turn-1",
        session_id="example-session-1",
        turn_index=0,
        role="user",
        message="example message",
        timestamp="2026-01-01T00:00:01Z",
        idempotency_key="example-key-0",
    )
    fields.update(overrides)
    return Turn(**fields)


class ConversationRepositoryContract:
    """Subclass alongside ``unittest.TestCase`` and implement :meth:`repository`."""

    def repository(self):
        raise NotImplementedError

    # -- sessions --------------------------------------------------------

    def test_create_and_get_session(self):
        repo = self.repository()
        created = repo.create_session(make_session())
        self.assertEqual(repo.get_session(created.id), created)

    def test_get_unknown_session_raises(self):
        with self.assertRaises(SessionNotFound):
            self.repository().get_session("no-such-session")

    def test_duplicate_session_raises(self):
        repo = self.repository()
        repo.create_session(make_session())
        with self.assertRaises(SessionAlreadyExists):
            repo.create_session(make_session())

    def test_close_session_is_idempotent(self):
        repo = self.repository()
        repo.create_session(make_session())
        first = repo.close_session("example-session-1", "2026-01-01T01:00:00Z")
        second = repo.close_session("example-session-1", "2026-01-01T02:00:00Z")
        self.assertEqual(first.closed_at, "2026-01-01T01:00:00Z")
        self.assertEqual(second.closed_at, "2026-01-01T01:00:00Z")

    def test_raw_theme_label_survives_storage(self):
        """Section 8.3: raw labels are never overwritten."""
        repo = self.repository()
        repo.create_session(make_session(raw_theme_label="Erotic Attachment Delusions and Self-Isolation"))
        stored = repo.get_session("example-session-1")
        self.assertEqual(
            stored.raw_theme_label, "Erotic Attachment Delusions and Self-Isolation"
        )
        self.assertIsNone(stored.canonical_theme_label)
        self.assertIsNone(stored.theme_mapping_version)

    # -- turns -----------------------------------------------------------

    def test_append_and_list_turns_in_index_order(self):
        repo = self.repository()
        repo.create_session(make_session())
        for index in (2, 0, 1):
            repo.append_turn(
                make_turn(
                    id="example-turn-{}".format(index),
                    turn_index=index,
                    role="user" if index % 2 == 0 else "assistant",
                    idempotency_key="example-key-{}".format(index),
                )
            )
        self.assertEqual([t.turn_index for t in repo.list_turns("example-session-1")], [0, 1, 2])

    def test_turn_for_unknown_session_raises(self):
        with self.assertRaises(SessionNotFound):
            self.repository().append_turn(make_turn(session_id="no-such-session"))

    def test_same_idempotency_key_does_not_duplicate(self):
        """Section 6.3: retried ingestion creates no duplicate turn."""
        repo = self.repository()
        repo.create_session(make_session())
        first = repo.append_turn(make_turn())
        second = repo.append_turn(make_turn())
        self.assertEqual(first, second)
        self.assertEqual(len(repo.list_turns("example-session-1")), 1)

    def test_reused_idempotency_key_with_different_content_raises(self):
        repo = self.repository()
        repo.create_session(make_session())
        repo.append_turn(make_turn())
        with self.assertRaises(IdempotencyConflict):
            repo.append_turn(make_turn(message="a different message"))

    def test_duplicate_turn_index_raises(self):
        """Section 13: reject duplicate turn indices."""
        repo = self.repository()
        repo.create_session(make_session())
        repo.append_turn(make_turn())
        with self.assertRaises(DuplicateTurnIndex):
            repo.append_turn(make_turn(id="example-turn-other", idempotency_key="example-key-other"))

    def test_closed_session_rejects_new_turns(self):
        repo = self.repository()
        repo.create_session(make_session())
        repo.close_session("example-session-1", "2026-01-01T01:00:00Z")
        with self.assertRaises(SessionClosed):
            repo.append_turn(make_turn())

    def test_closed_session_still_replays_a_known_key(self):
        """A retry that arrives after closure must not be turned into an error."""
        repo = self.repository()
        repo.create_session(make_session())
        stored = repo.append_turn(make_turn())
        repo.close_session("example-session-1", "2026-01-01T01:00:00Z")
        self.assertEqual(repo.append_turn(make_turn()), stored)

    def test_stored_turn_preserves_raw_fields(self):
        """Section 6.3: raw source fields are preserved."""
        repo = self.repository()
        repo.create_session(make_session())
        repo.append_turn(
            make_turn(
                model_name="example-model",
                model_version="example-2026-01",
                source_payload_reference="example-ref-1",
            )
        )
        stored = repo.list_turns("example-session-1")[0]
        self.assertEqual(stored.model_name, "example-model")
        self.assertEqual(stored.model_version, "example-2026-01")
        self.assertEqual(stored.source_payload_reference, "example-ref-1")

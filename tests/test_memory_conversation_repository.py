"""Binds the ConversationRepository contract to the in-memory adapter.

The PostgreSQL adapter will add a sibling module of the same shape.
"""

from __future__ import annotations

import unittest

from src.adapters.memory.conversations import InMemoryConversationRepository
from tests.contract.conversation_repository import ConversationRepositoryContract


class InMemoryConversationRepositoryTest(ConversationRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemoryConversationRepository()


class RecordInvariants(unittest.TestCase):
    """Invariants enforced by the records themselves, not by storage."""

    def test_canonical_theme_requires_a_mapping_version(self):
        from tests.contract.conversation_repository import make_session

        with self.assertRaises(ValueError):
            make_session(canonical_theme_label="Spiritual or messianic beliefs")

    def test_canonical_theme_allowed_with_a_mapping_version(self):
        from tests.contract.conversation_repository import make_session

        session = make_session(
            canonical_theme_label="Spiritual or messianic beliefs",
            theme_mapping_version="theme_mapping_v1.0",
        )
        self.assertEqual(session.raw_theme_label, "Grandiose Delusions")

    def test_role_must_be_user_or_assistant(self):
        from tests.contract.conversation_repository import make_turn

        with self.assertRaises(ValueError):
            make_turn(role="system")


if __name__ == "__main__":
    unittest.main()

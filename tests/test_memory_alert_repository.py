"""Binds the AlertRepository contract to the in-memory adapter."""

from __future__ import annotations

import unittest

from src.adapters.memory.alerts import InMemoryAlertRepository
from tests.contract.alert_repository import AlertRepositoryContract


class InMemoryAlertRepositoryTest(AlertRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemoryAlertRepository()


if __name__ == "__main__":
    unittest.main()

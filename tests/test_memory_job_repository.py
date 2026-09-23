"""Binds the JobRepository contract to the in-memory adapter."""

from __future__ import annotations

import unittest

from src.adapters.memory.analysis import InMemoryJobRepository
from tests.contract.job_repository import JobRepositoryContract


class InMemoryJobRepositoryTest(JobRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemoryJobRepository()


if __name__ == "__main__":
    unittest.main()

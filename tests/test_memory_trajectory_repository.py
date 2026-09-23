"""Binds the TrajectoryRepository contract to the in-memory adapter."""

from __future__ import annotations

import unittest

from src.adapters.memory.trajectories import InMemoryTrajectoryRepository
from tests.contract.trajectory_repository import TrajectoryRepositoryContract


class InMemoryTrajectoryRepositoryTest(TrajectoryRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemoryTrajectoryRepository()


if __name__ == "__main__":
    unittest.main()

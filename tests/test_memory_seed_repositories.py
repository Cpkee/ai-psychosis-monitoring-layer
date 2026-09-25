"""Binds the seed-pipeline repository contracts to the in-memory adapters."""

from __future__ import annotations

import unittest

from src.adapters.memory.seeds import (
    InMemoryExtractionCacheRepository,
    InMemorySeedExposureRepository,
    InMemorySeedFilterRepository,
    InMemorySeedRepository,
    InMemorySeedSelectionRepository,
    InMemorySourceDocumentRepository,
)
from tests.contract.seed_repositories import (
    ExtractionCacheRepositoryContract,
    ProcessedVersionsContract,
    SeedExposureRepositoryContract,
    SeedFilterRepositoryContract,
    SeedRepositoryContract,
    SeedSelectionRepositoryContract,
    SourceDocumentRepositoryContract,
)


class InMemorySourceDocumentRepositoryTest(SourceDocumentRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemorySourceDocumentRepository()


class InMemoryProcessedVersionsTest(ProcessedVersionsContract, unittest.TestCase):
    def repository(self):
        return InMemorySourceDocumentRepository()


class InMemoryExtractionCacheRepositoryTest(ExtractionCacheRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemoryExtractionCacheRepository()


class InMemorySeedRepositoryTest(SeedRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemorySeedRepository()


class InMemorySeedFilterRepositoryTest(SeedFilterRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemorySeedFilterRepository()


class InMemorySeedSelectionRepositoryTest(SeedSelectionRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemorySeedSelectionRepository()


class InMemorySeedExposureRepositoryTest(SeedExposureRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemorySeedExposureRepository()


if __name__ == "__main__":
    unittest.main()

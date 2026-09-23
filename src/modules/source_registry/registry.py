"""Data Source Registry — architecture.md section 6.1.

Owns data-source identity, provenance, permitted uses, authority status,
retention classification and integrity metadata.

Source definitions are file-backed for this phase (``config/data_sources.json``).
Architecture section 7.2 makes ``data_source_versions`` a PostgreSQL record;
the interface here is unchanged by that move, which is the point of the seam.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, FrozenSet, List, Optional

from src.domain.provenance.data_sources import (
    AuthorityStatus,
    AuthorizationDecision,
    DataSourceDefinition,
    DataSourceVersion,
    DataUsePurpose,
    IntegrityResult,
)

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "config", "data_sources.json")


class SourceNotRegistered(KeyError):
    """Raised when a source version id is unknown to the registry."""


def _purposes(values: List[str]) -> FrozenSet[DataUsePurpose]:
    return frozenset(DataUsePurpose(value) for value in values)


class DataSourceRegistry:
    """In-process registry over a JSON definition file."""

    def __init__(self, config_path: Optional[str] = None, repo_root: Optional[str] = None):
        self._repo_root = repo_root or REPO_ROOT
        self._config_path = config_path or DEFAULT_CONFIG
        self._sources: Dict[str, DataSourceVersion] = {}
        if os.path.exists(self._config_path):
            self._load()

    # -- interface -------------------------------------------------------

    def register_source(self, definition: DataSourceDefinition) -> DataSourceVersion:
        source_version_id = "{}@{}".format(definition.source_name, definition.version)
        version = DataSourceVersion(
            source_version_id=source_version_id, definition=definition
        )
        self._sources[source_version_id] = version
        return version

    def get_source(self, source_version_id: str) -> DataSourceVersion:
        try:
            return self._sources[source_version_id]
        except KeyError:
            raise SourceNotRegistered(
                "Unregistered data source version {!r}. Sources must be "
                "registered before use (architecture.md section 6.1).".format(
                    source_version_id
                )
            )

    def authorize_use(
        self, source_version_id: str, purpose: Optional[DataUsePurpose]
    ) -> AuthorizationDecision:
        """Decide whether a purpose is allowed for a source, on permissions alone.

        This is the permission half of the decision. Execution mode, frozen
        artefact versions and integrity are enforced by the Dataset Use Gate,
        which calls this and then applies the remaining rules.
        """
        reasons: List[str] = []
        try:
            source = self.get_source(source_version_id)
        except SourceNotRegistered as exc:
            return AuthorizationDecision(
                allowed=False,
                source_version_id=source_version_id,
                purpose=purpose,
                reasons=(str(exc),),
            )

        if purpose is None:
            return AuthorizationDecision(
                allowed=False,
                source_version_id=source_version_id,
                purpose=None,
                reasons=("No purpose specified. The gate fails closed on an "
                         "unspecified purpose (architecture.md section 6.2).",),
            )

        definition = source.definition
        if purpose in definition.prohibited_uses:
            reasons.append(
                "Purpose {!r} is explicitly prohibited for {!r}.".format(
                    purpose.value, source_version_id
                )
            )
        elif purpose not in definition.permitted_uses:
            reasons.append(
                "Purpose {!r} is not in the permitted uses for {!r}. "
                "Permitted: {}.".format(
                    purpose.value,
                    source_version_id,
                    ", ".join(sorted(p.value for p in definition.permitted_uses)) or "none",
                )
            )

        if definition.sealed and purpose is not DataUsePurpose.FINAL_EVALUATION:
            reasons.append(
                "{!r} is sealed and permits final evaluation only "
                "(architecture.md section 8.1).".format(source_version_id)
            )

        return AuthorizationDecision(
            allowed=not reasons,
            source_version_id=source_version_id,
            purpose=purpose,
            reasons=tuple(reasons),
        )

    def verify_integrity(self, source_version_id: str) -> IntegrityResult:
        """Verify a source against its stored checksum.

        Hashes bytes; never returns or logs file content, so this is safe to
        call on a sealed source from tests and tooling.
        """
        source = self.get_source(source_version_id)
        definition = source.definition

        if not definition.integrity_required:
            return IntegrityResult(
                ok=True,
                algorithm=definition.checksum_algorithm,
                expected_checksum=None,
                actual_checksum=None,
                reason="Integrity does not apply: this source is produced at "
                       "runtime and has no stored file.",
            )

        path = self.absolute_path(source_version_id)
        if path is None or not os.path.exists(path):
            return IntegrityResult(
                ok=False,
                algorithm=definition.checksum_algorithm,
                expected_checksum=definition.checksum,
                actual_checksum=None,
                reason="File not found: {}".format(definition.relative_path),
            )

        expected = definition.checksum
        if expected is None and definition.manifest_relative_path:
            expected = self._checksum_from_manifest(definition.manifest_relative_path)

        if not expected:
            return IntegrityResult(
                ok=False,
                algorithm=definition.checksum_algorithm,
                expected_checksum=None,
                actual_checksum=None,
                reason="No stored checksum. Integrity cannot be established, "
                       "so the gate fails closed.",
            )

        actual = self._hash_file(path, definition.checksum_algorithm)
        return IntegrityResult(
            ok=(actual == expected),
            algorithm=definition.checksum_algorithm,
            expected_checksum=expected,
            actual_checksum=actual,
            reason=None if actual == expected else "Checksum mismatch.",
        )

    # -- helpers ---------------------------------------------------------

    def absolute_path(self, source_version_id: str) -> Optional[str]:
        definition = self.get_source(source_version_id).definition
        if not definition.relative_path:
            return None
        return os.path.join(self._repo_root, definition.relative_path)

    def list_sources(self) -> List[DataSourceVersion]:
        return [self._sources[key] for key in sorted(self._sources)]

    def sealed_sources(self) -> List[DataSourceVersion]:
        return [version for version in self.list_sources() if version.sealed]

    def _checksum_from_manifest(self, manifest_relative_path: str) -> Optional[str]:
        manifest_path = os.path.join(self._repo_root, manifest_relative_path)
        if not os.path.exists(manifest_path):
            return None
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return json.load(handle).get("checksum")

    @staticmethod
    def _hash_file(path: str, algorithm: str) -> str:
        digest = hashlib.new(algorithm.replace("-", "").lower())
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load(self) -> None:
        with open(self._config_path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        for entry in document["sources"]:
            self.register_source(
                DataSourceDefinition(
                    source_name=entry["source_name"],
                    source_type=entry["source_type"],
                    version=entry["version"],
                    provenance=entry["provenance"],
                    authority_status=AuthorityStatus(entry["authority_status"]),
                    permitted_uses=_purposes(entry.get("permitted_uses", [])),
                    prohibited_uses=_purposes(entry.get("prohibited_uses", [])),
                    retention_class=entry["retention_class"],
                    sealed=entry["sealed"],
                    relative_path=entry.get("relative_path"),
                    integrity_required=entry.get("integrity_required", True),
                    checksum_algorithm=entry.get("checksum_algorithm", "SHA-256"),
                    checksum=entry.get("checksum"),
                    manifest_relative_path=entry.get("manifest_relative_path"),
                    access_policy_version=entry.get("access_policy_version"),
                    notes=entry.get("notes", ""),
                )
            )

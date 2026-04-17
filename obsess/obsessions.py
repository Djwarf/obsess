from __future__ import annotations

import uuid
from typing import Optional

from obsess.embed import Embedder
from obsess.shared import SharedObsessions
from obsess.storage import Storage
from obsess.storage.memory import InMemoryStorage
from obsess.storage.serialize import (
    obsession_activation_from_dict,
    obsession_activation_to_dict,
    obsession_def_from_dict,
    obsession_def_to_dict,
)
from obsess.types import (
    Obsession,
    ObsessionActivation,
    ObsessionDefinition,
    SeedType,
)


_PRIVATE_DEFS_COLLECTION = "private_obsession_definitions"
_ACTIVATIONS_COLLECTION = "obsession_activations"


def _private_def_key(agent_id: str, def_id: str) -> str:
    return f"{agent_id}:{def_id}"


def _activation_key(agent_id: str, obsession_id: str) -> str:
    return f"{agent_id}:{obsession_id}"


class ObsessionRegistry:
    """Per-agent registry. Holds this agent's private obsession definitions and
    all of this agent's activations against both private and shared definitions.

    Storage-backed. Each agent's private defs and activations are namespaced
    by agent_id (composite key `{agent_id}:{def_id}`) so they coexist in
    shared collections with other agents' records without bleeding over."""

    def __init__(
        self,
        embedder: Embedder,
        agent_id: str,
        shared: SharedObsessions,
        storage: Optional[Storage] = None,
    ):
        self._embedder = embedder
        self._agent_id = agent_id
        self._shared = shared
        self._storage: Storage = storage or InMemoryStorage()
        self._private_defs: dict[str, ObsessionDefinition] = {}
        self._activations: dict[str, ObsessionActivation] = {}
        self._hydrate()

    def _hydrate(self) -> None:
        for data in self._storage.all(_PRIVATE_DEFS_COLLECTION):
            if data.get("_owner_agent_id") != self._agent_id:
                continue
            d = obsession_def_from_dict(data)
            self._private_defs[d.id] = d
        for data in self._storage.all(_ACTIVATIONS_COLLECTION):
            if data.get("agent_id") != self._agent_id:
                continue
            a = obsession_activation_from_dict(data)
            self._activations[a.obsession_id] = a

    def _persist_private_def(self, d: ObsessionDefinition) -> None:
        data = obsession_def_to_dict(d)
        data["_owner_agent_id"] = self._agent_id
        self._storage.put(
            _PRIVATE_DEFS_COLLECTION,
            _private_def_key(self._agent_id, d.id),
            data,
        )

    def _persist_activation(self, a: ObsessionActivation) -> None:
        self._storage.put(
            _ACTIVATIONS_COLLECTION,
            _activation_key(self._agent_id, a.obsession_id),
            obsession_activation_to_dict(a),
        )

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def seed(
        self,
        domain: str,
        description: str,
        seed_types: list[SeedType],
        commitment: float = 0.7,
        identity_level: bool = False,
        seed_metadata: Optional[dict] = None,
    ) -> Obsession:
        defn = ObsessionDefinition(
            id=str(uuid.uuid4()),
            domain=domain,
            description=description,
            identity_level=identity_level,
            seed_metadata=seed_metadata or {},
            embedding=self._embedder.embed(f"{domain}. {description}"),
        )
        act = ObsessionActivation(
            obsession_id=defn.id,
            agent_id=self._agent_id,
            seed_types=list(seed_types),
            earned_commitment=commitment,
        )
        self._private_defs[defn.id] = defn
        self._activations[defn.id] = act
        self._persist_private_def(defn)
        self._persist_activation(act)
        return Obsession(definition=defn, activation=act)

    def activate_shared(
        self,
        definition_id: str,
        seed_types: list[SeedType],
        commitment: float = 0.7,
        bootstrapped_commitment: float = 0.0,
    ) -> Obsession:
        defn = self._shared.get(definition_id)
        if defn is None:
            raise KeyError(f"no shared definition with id {definition_id}")
        if definition_id in self._activations:
            raise ValueError(
                f"agent {self._agent_id} already has an activation against {definition_id}"
            )
        act = ObsessionActivation(
            obsession_id=defn.id,
            agent_id=self._agent_id,
            seed_types=list(seed_types),
            earned_commitment=commitment,
            bootstrapped_commitment=bootstrapped_commitment,
        )
        self._activations[defn.id] = act
        self._persist_activation(act)
        return Obsession(definition=defn, activation=act)

    def touch(self, obsession_id: str) -> None:
        """Update last_activation on an activation and persist. Agents should
        call this via Obsession.touch() on the joined view, which delegates
        to the underlying ObsessionActivation — the registry re-persists via
        this method if storage-backed consistency is needed. For v1, touch()
        mutates the in-memory activation directly; persistence is explicit via
        persist_activation() below."""
        act = self._activations.get(obsession_id)
        if act is None:
            raise KeyError(obsession_id)
        act.touch()
        self._persist_activation(act)

    def persist_activation(self, obsession_id: str) -> None:
        """Write the current state of an activation to storage. Called after
        in-memory mutations that should survive restart."""
        act = self._activations.get(obsession_id)
        if act is not None:
            self._persist_activation(act)

    def _def_for(self, obsession_id: str) -> Optional[ObsessionDefinition]:
        return self._private_defs.get(obsession_id) or self._shared.get(obsession_id)

    def get(self, obsession_id: str) -> Optional[Obsession]:
        defn = self._def_for(obsession_id)
        act = self._activations.get(obsession_id)
        if defn is None or act is None:
            return None
        return Obsession(definition=defn, activation=act)

    def all(self) -> list[Obsession]:
        results = []
        for oid, act in self._activations.items():
            defn = self._def_for(oid)
            if defn is not None:
                results.append(Obsession(definition=defn, activation=act))
        return results

    def active(self, threshold: float = 0.1) -> list[Obsession]:
        return [o for o in self.all() if o.commitment >= threshold]

    def current_frame(self) -> str:
        non_identity = [o for o in self.all() if not o.identity_level]
        if not non_identity:
            return "uncommitted"
        top = max(non_identity, key=lambda o: o.commitment)
        return top.domain

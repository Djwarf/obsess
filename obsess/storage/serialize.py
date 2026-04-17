from __future__ import annotations

from typing import Optional

from obsess.pools import Pool
from obsess.relationships import Relationship, RelationshipKind, SharingMode
from obsess.shares import TraumaShare
from obsess.types import (
    Impression,
    ObsessionActivation,
    ObsessionDefinition,
    SeedType,
    Trauma,
)


# --- ObsessionDefinition ---

def obsession_def_to_dict(d: ObsessionDefinition) -> dict:
    return {
        "id": d.id,
        "domain": d.domain,
        "description": d.description,
        "identity_level": d.identity_level,
        "seed_metadata": dict(d.seed_metadata),
        "embedding": list(d.embedding) if d.embedding is not None else None,
        "owner_pool_id": d.owner_pool_id,
    }


def obsession_def_from_dict(data: dict) -> ObsessionDefinition:
    return ObsessionDefinition(
        id=data["id"],
        domain=data["domain"],
        description=data["description"],
        identity_level=data.get("identity_level", False),
        seed_metadata=dict(data.get("seed_metadata") or {}),
        embedding=list(data["embedding"]) if data.get("embedding") is not None else None,
        owner_pool_id=data.get("owner_pool_id"),
    )


# --- ObsessionActivation ---

def obsession_activation_to_dict(a: ObsessionActivation) -> dict:
    return {
        "obsession_id": a.obsession_id,
        "agent_id": a.agent_id,
        "seed_types": [s.value for s in a.seed_types],
        "earned_commitment": a.earned_commitment,
        "bootstrapped_commitment": a.bootstrapped_commitment,
        "last_activation": a.last_activation,
        "decay_rate": a.decay_rate,
    }


def obsession_activation_from_dict(data: dict) -> ObsessionActivation:
    return ObsessionActivation(
        obsession_id=data["obsession_id"],
        agent_id=data["agent_id"],
        seed_types=[SeedType(v) for v in data.get("seed_types", [])],
        earned_commitment=data.get("earned_commitment", 0.0),
        bootstrapped_commitment=data.get("bootstrapped_commitment", 0.0),
        last_activation=data["last_activation"],
        decay_rate=data.get("decay_rate", 0.01),
    )


# --- Impression ---

def impression_to_dict(i: Impression) -> dict:
    return {
        "id": i.id,
        "seed_text": i.seed_text,
        "source_text": i.source_text,
        "obsession_ids": list(i.obsession_ids),
        "frame_at_encode": i.frame_at_encode,
        "agent_id": i.agent_id,
        "created_at": i.created_at,
        "embedding": list(i.embedding) if i.embedding is not None else None,
    }


def impression_from_dict(data: dict) -> Impression:
    return Impression(
        id=data["id"],
        seed_text=data["seed_text"],
        source_text=data["source_text"],
        obsession_ids=list(data.get("obsession_ids", [])),
        frame_at_encode=data["frame_at_encode"],
        agent_id=data["agent_id"],
        created_at=data["created_at"],
        embedding=list(data["embedding"]) if data.get("embedding") is not None else None,
    )


# --- Trauma ---

def trauma_to_dict(t: Trauma) -> dict:
    return {
        "id": t.id,
        "context": t.context,
        "failure": t.failure,
        "attempted_solutions": list(t.attempted_solutions),
        "unsolvable_at_time": t.unsolvable_at_time,
        "cost": t.cost,
        "trigger_pattern": t.trigger_pattern,
        "linked_obsession_id": t.linked_obsession_id,
        "origin_agent_id": t.origin_agent_id,
        "resolution_tradeoffs": list(t.resolution_tradeoffs),
        "still_firing": t.still_firing,
        "created_at": t.created_at,
        "embedding": list(t.embedding) if t.embedding is not None else None,
        "pool_id": t.pool_id,
    }


def trauma_from_dict(data: dict) -> Trauma:
    return Trauma(
        id=data["id"],
        context=data["context"],
        failure=data["failure"],
        attempted_solutions=list(data.get("attempted_solutions", [])),
        unsolvable_at_time=data["unsolvable_at_time"],
        cost=data["cost"],
        trigger_pattern=data["trigger_pattern"],
        linked_obsession_id=data.get("linked_obsession_id"),
        origin_agent_id=data["origin_agent_id"],
        resolution_tradeoffs=list(data.get("resolution_tradeoffs", [])),
        still_firing=data.get("still_firing", True),
        created_at=data["created_at"],
        embedding=list(data["embedding"]) if data.get("embedding") is not None else None,
        pool_id=data.get("pool_id"),
    )


# --- Relationship ---

def relationship_to_dict(r: Relationship) -> dict:
    return {
        "id": r.id,
        "kind": r.kind.value,
        "from_agent_id": r.from_agent_id,
        "to_agent_id": r.to_agent_id,
        "strength": r.strength,
        "created_at": r.created_at,
        "last_activation": r.last_activation,
        "metadata": dict(r.metadata),
    }


def relationship_from_dict(data: dict) -> Relationship:
    return Relationship(
        id=data["id"],
        kind=RelationshipKind(data["kind"]),
        from_agent_id=data["from_agent_id"],
        to_agent_id=data["to_agent_id"],
        strength=data.get("strength", 1.0),
        created_at=data["created_at"],
        last_activation=data["last_activation"],
        metadata=dict(data.get("metadata") or {}),
    )


# --- TraumaShare ---

def trauma_share_to_dict(s: TraumaShare) -> dict:
    return {
        "id": s.id,
        "trauma_id": s.trauma_id,
        "recipient_agent_id": s.recipient_agent_id,
        "origin_agent_id": s.origin_agent_id,
        "mode": s.mode.value,
        "via_relationship_id": s.via_relationship_id,
        "created_at": s.created_at,
    }


def trauma_share_from_dict(data: dict) -> TraumaShare:
    return TraumaShare(
        id=data["id"],
        trauma_id=data["trauma_id"],
        recipient_agent_id=data["recipient_agent_id"],
        origin_agent_id=data["origin_agent_id"],
        mode=SharingMode(data["mode"]),
        via_relationship_id=data.get("via_relationship_id"),
        created_at=data["created_at"],
    )


# --- Pool ---

def pool_to_dict(p: Pool) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "member_ids": sorted(p.member_ids),
        "created_at": p.created_at,
    }


def pool_from_dict(data: dict) -> Pool:
    return Pool(
        id=data["id"],
        name=data["name"],
        member_ids=set(data.get("member_ids", [])),
        created_at=data["created_at"],
    )

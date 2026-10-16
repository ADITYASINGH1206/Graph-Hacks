"""Graph schema initialization and index creation for FalkorDB."""

import logging
from typing import Any

from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

# Standard indexes required by GRAPH_SCHEMA.md plus uid indexes
SCHEMA_INDEXES = [
    ("Person", "login"),
    ("Person", "uid"),
    ("Issue", "number"),
    ("Issue", "uid"),
    ("PullRequest", "number"),
    ("PullRequest", "uid"),
    ("Decision", "id"),
    ("Decision", "uid"),
    ("Evidence", "id"),
    ("Evidence", "uid"),
    ("Module", "name"),
    ("Module", "uid"),
    ("File", "path"),
    ("File", "uid"),
    ("Release", "tag"),
    ("Release", "uid"),
    ("Concept", "name"),
    ("Concept", "uid"),
]

FULLTEXT_INDEXES = [
    ("Decision", ["title", "summary"]),
]


def make_uid(label: str, key_val: Any) -> str:
    """Generate canonical uid: <Label>:<key>."""
    return f"{label}:{key_val}"


def ensure_schema(graph: Any) -> dict[str, list[str]]:
    """Ensure all node indexes and full-text indexes exist on the given graph.

    Idempotent: catches 'already indexed' errors cleanly.
    """
    created: list[str] = []
    existed: list[str] = []

    # 1. Scalar node property indexes
    for label, prop in SCHEMA_INDEXES:
        cmd = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
        try:
            graph.query(cmd)
            created.append(f"{label}.{prop}")
            logger.info("Created index for %s.%s", label, prop)
        except ResponseError as err:
            err_msg = str(err)
            if "already indexed" in err_msg.lower():
                existed.append(f"{label}.{prop}")
            else:
                logger.warning("Error creating index for %s.%s: %s", label, prop, err_msg)
        except Exception as exc:
            logger.warning("Unexpected error creating index for %s.%s: %s", label, prop, exc)

    # 2. Full-text index on Decision(title, summary)
    for label, fields in FULLTEXT_INDEXES:
        fields_str = ", ".join(f"'{f}'" for f in fields)
        cmd = f"CALL db.idx.fulltext.createNodeIndex('{label}', {fields_str})"
        try:
            graph.query(cmd)
            created.append(f"fulltext:{label}({','.join(fields)})")
            logger.info("Created fulltext index on %s(%s)", label, fields)
        except ResponseError as err:
            err_msg = str(err)
            if "already indexed" in err_msg.lower():
                existed.append(f"fulltext:{label}")
            else:
                logger.warning("Error creating fulltext index on %s: %s", label, err_msg)
        except Exception as exc:
            logger.warning("Unexpected error creating fulltext index on %s: %s", label, exc)

    return {"created": created, "existed": existed}

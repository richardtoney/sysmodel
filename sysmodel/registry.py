"""Metadata schema registry for sysmodel block types.

This module has no imports from sysmodel to avoid circular dependencies.
It is imported by models.py and by user code that extends the registry.
"""

from __future__ import annotations

from typing import Any


class MetadataSchema:
    """Declared metadata contract for a BlockType.

    Args:
        required: Keys that MUST be present on every block of this type.
        allowed: Keys that are valid but optional. Any key not in required
            or allowed will raise a validation error.
    """

    def __init__(
        self,
        required: set[str] | None = None,
        allowed: set[str] | None = None,
    ) -> None:
        self.required: set[str] = required or set()
        self.allowed: set[str] = allowed or set()

    @property
    def all_known(self) -> set[str]:
        """Union of required and allowed keys."""
        return self.required | self.allowed


METADATA_REGISTRY: dict[str, MetadataSchema] = {
    "ec2": MetadataSchema(
        required={"instance_type"},
        allowed={"ami", "region", "az", "public_ip", "private_ip", "vpc_id"},
    ),
    "rds": MetadataSchema(
        required={"engine", "version"},
        allowed={"instance_class", "multi_az", "region", "port", "db_name"},
    ),
    "s3": MetadataSchema(
        allowed={"encryption", "versioning", "region", "bucket_policy"},
    ),
    "lambda": MetadataSchema(
        required={"runtime"},
        allowed={"memory_mb", "timeout_s", "region", "handler"},
    ),
    "subnet": MetadataSchema(
        required={"cidr"},
        allowed={"gateway", "region", "az", "public"},
    ),
    "vpc": MetadataSchema(
        required={"cidr"},
        allowed={"region", "dns_hostnames", "tenancy"},
    ),
    "server": MetadataSchema(
        allowed={"ip", "cores", "ram_gb", "os", "os_version", "kernel"},
    ),
    "software": MetadataSchema(
        required={"version"},
        allowed={"language", "framework", "family", "kernel", "mode", "runtime"},
    ),
    "cluster": MetadataSchema(
        allowed={"k3s_version", "k8s_version", "cni", "vip", "runtime"},
    ),
    "load_balancer": MetadataSchema(
        allowed={"scheme", "protocol", "port", "region", "dns_name"},
    ),
    "job": MetadataSchema(
        allowed={"schedule", "language", "framework", "timeout_s"},
    ),
    "database": MetadataSchema(
        required={"engine", "version"},
        allowed={"port", "host"},
    ),
    "service": MetadataSchema(
        allowed={"port", "protocol", "version", "language", "framework"},
    ),
}


def register_schema(block_type: str, schema: MetadataSchema) -> None:
    """Register or replace a MetadataSchema for a block type string.

    Call this in your system file or a shared config module before
    defining any blocks of the custom type.

    Args:
        block_type: The string key for the block type (e.g. "firewall").
        schema: The MetadataSchema describing required and allowed keys.

    Example::

        from sysmodel.registry import register_schema, MetadataSchema
        register_schema("firewall", MetadataSchema(
            required={"vendor"},
            allowed={"model", "firmware_version", "management_ip"},
        ))
    """
    METADATA_REGISTRY[block_type] = schema


def get_schema(block_type: str) -> MetadataSchema | None:
    """Return the MetadataSchema for a block type, or None if unconstrained.

    Args:
        block_type: The block type string to look up.

    Returns:
        The registered MetadataSchema, or None if the type has no schema.
    """
    return METADATA_REGISTRY.get(block_type)


def validate_metadata(
    block_id: str,
    block_type: str,
    metadata: dict[str, Any],
) -> list[str]:
    """Validate a metadata dict against the registry for the given block type.

    Block types not in the registry are skipped (unconstrained).

    Args:
        block_id: The block's ID, used in error messages.
        block_type: The block's type string, used to look up the schema.
        metadata: The metadata dict to validate.

    Returns:
        A list of human-readable error strings. Empty list means valid.
    """
    schema = METADATA_REGISTRY.get(block_type)
    if schema is None:
        return []

    errors: list[str] = []

    for key in schema.required:
        if key not in metadata:
            errors.append(
                f"Block '{block_id}' ({block_type}): "
                f"missing required metadata key '{key}'"
            )

    known = schema.all_known
    for key in metadata:
        if key not in known:
            known_sorted = sorted(known)
            errors.append(
                f"Block '{block_id}' ({block_type}): "
                f"unknown metadata key '{key}' (known: {known_sorted})"
            )

    return errors

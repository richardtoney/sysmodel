"""Tests for sysmodel.registry."""

from sysmodel.registry import (
    METADATA_REGISTRY,
    MetadataSchema,
    get_schema,
    register_schema,
    validate_metadata,
)


def test_register_custom_schema() -> None:
    register_schema("firewall", MetadataSchema(required={"vendor"}, allowed={"model"}))
    schema = METADATA_REGISTRY.get("firewall")
    assert schema is not None
    assert "vendor" in schema.required


def test_get_schema_known_type() -> None:
    schema = get_schema("ec2")
    assert schema is not None
    assert "instance_type" in schema.required


def test_get_schema_unknown_type_returns_none() -> None:
    assert get_schema("nonexistent_type_xyz") is None


def test_validate_metadata_clean() -> None:
    errors = validate_metadata("ec2-01", "ec2", {"instance_type": "t3.micro"})
    assert errors == []


def test_validate_metadata_missing_required() -> None:
    errors = validate_metadata("ec2-01", "ec2", {})
    assert any("instance_type" in e for e in errors)
    assert any("missing required" in e for e in errors)


def test_validate_metadata_unknown_key_lists_known_keys() -> None:
    errors = validate_metadata("ec2-01", "ec2", {"instance_type": "t3.micro", "bogus_key": "val"})
    assert any("bogus_key" in e for e in errors)
    assert any("known:" in e for e in errors)


def test_validate_metadata_unconstrained_type_passes_anything() -> None:
    errors = validate_metadata("custom-01", "my_custom_type_no_schema", {"anything": "goes"})
    assert errors == []


def test_register_schema_replaces_existing() -> None:
    register_schema("job", MetadataSchema(required={"executor"}, allowed={"queue"}))
    schema = get_schema("job")
    assert schema is not None
    assert "executor" in schema.required
    register_schema("job", MetadataSchema(allowed={"schedule", "language", "framework", "timeout_s"}))


def test_metadata_schema_all_known() -> None:
    schema = MetadataSchema(required={"a"}, allowed={"b", "c"})
    assert schema.all_known == {"a", "b", "c"}


def test_validate_metadata_software_missing_version() -> None:
    errors = validate_metadata("sw-01", "software", {"language": "python"})
    assert any("version" in e for e in errors)

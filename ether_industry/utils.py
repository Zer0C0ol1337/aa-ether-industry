"""Allgemeine Hilfsfunktionen."""

from django.db import connection


def upsert(model, objs, unique_fields, update_fields, batch_size=1000):
    """bulk_create als Upsert – funktioniert mit MySQL/MariaDB (ohne unique_fields) und PostgreSQL/SQLite."""
    if not objs:
        return
    kwargs = {"update_conflicts": True, "update_fields": update_fields, "batch_size": batch_size}
    if connection.features.supports_update_conflicts_with_target:
        kwargs["unique_fields"] = unique_fields
    model.objects.bulk_create(objs, **kwargs)

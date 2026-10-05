"""Management-Command: importiert Items und Blueprints aus der offiziellen CCP-SDE."""

import io
import json
import os
import tempfile
import zipfile

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...app_settings import SDE_URL, USER_AGENT
from ...models import ActivityMaterial, ActivityProduct, Blueprint, BlueprintActivity, ItemType
from ...utils import upsert


def _name(value, lang="en"):
    """Holt einen Namen aus der SDE – dort meist ein Dict pro Sprache, teils ein String."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or ""
    return value or ""


class Command(BaseCommand):
    """Lädt die SDE im JSON-Lines-Format und füllt Items und Blueprint-Rezepte."""

    help = "Importiert Items und Blueprints aus der CCP-SDE (JSON Lines)."

    def add_arguments(self, parser):
        """Optional eine bereits heruntergeladene ZIP-Datei angeben."""
        parser.add_argument("--file", help="Pfad zu einer lokalen SDE-ZIP (JSON Lines)")

    def handle(self, *args, **options):
        """Ablauf: ZIP besorgen, Gruppen lesen, Items importieren, Blueprints importieren."""
        path, tmp = options.get("file"), None
        if not path:
            tmp = path = self._download()
        try:
            with zipfile.ZipFile(path) as zf:
                group_categories = self._load_group_categories(zf)
                self._import_types(zf, group_categories)
                self._import_blueprints(zf)
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        self.stdout.write(self.style.SUCCESS("SDE-Import abgeschlossen."))

    def _download(self):
        """Lädt die aktuelle SDE-ZIP in eine temporäre Datei und gibt den Pfad zurück."""
        self.stdout.write(f"Lade SDE von {SDE_URL} …")
        fd, path = tempfile.mkstemp(suffix=".zip")
        with os.fdopen(fd, "wb") as fh, requests.get(
            SDE_URL, headers={"User-Agent": USER_AGENT}, stream=True, timeout=120
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                fh.write(chunk)
        return path

    @staticmethod
    def _iter_jsonl(zf, filename):
        """Liest eine JSONL-Datei aus der ZIP Zeile für Zeile, egal in welchem Unterordner."""
        member = next((n for n in zf.namelist() if n.split("/")[-1] == filename), None)
        if member is None:
            raise CommandError(f"{filename} nicht in der SDE-ZIP gefunden")
        with zf.open(member) as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8"):
                line = line.strip()
                if line:
                    yield json.loads(line)

    def _load_group_categories(self, zf):
        """Baut eine Zuordnung groupID -> categoryID für die Item-Tabelle."""
        return {row["_key"]: row.get("categoryID") for row in self._iter_jsonl(zf, "groups.jsonl")}

    def _import_types(self, zf, group_categories):
        """Importiert bzw. aktualisiert alle Items aus types.jsonl."""
        objs = []
        for row in self._iter_jsonl(zf, "types.jsonl"):
            group_id = row.get("groupID")
            objs.append(
                ItemType(
                    type_id=row["_key"],
                    name=_name(row.get("name"))[:255],
                    name_de=_name(row.get("name"), "de")[:255],
                    group_id=group_id,
                    category_id=group_categories.get(group_id),
                    market_group_id=row.get("marketGroupID"),
                    volume=row.get("volume"),
                    published=bool(row.get("published", False)),
                )
            )
        upsert(
            ItemType,
            objs,
            ["type_id"],
            ["name", "name_de", "group_id", "category_id", "market_group_id", "volume", "published"],
        )
        self.stdout.write(f"Items importiert: {len(objs)}")

    @transaction.atomic
    def _import_blueprints(self, zf):
        """Ersetzt alle Blueprints samt Tätigkeiten, Materialien und Produkten."""
        known = set(ItemType.objects.values_list("type_id", flat=True))
        blueprints, activities, materials, products = [], [], [], []

        for row in self._iter_jsonl(zf, "blueprints.jsonl"):
            bp_id = row["_key"]
            if bp_id not in known:
                continue
            blueprints.append(Blueprint(type_id=bp_id, max_production_limit=row.get("maxProductionLimit") or 0))

            for key, data in (row.get("activities") or {}).items():
                code = BlueprintActivity.SDE_KEYS.get(key)
                if code is None:
                    continue
                act_id = BlueprintActivity.make_id(bp_id, code)
                activities.append(
                    BlueprintActivity(id=act_id, blueprint_id=bp_id, activity=code, time=data.get("time") or 0)
                )
                for mat in data.get("materials") or []:
                    if mat["typeID"] in known:
                        materials.append(
                            ActivityMaterial(activity_id=act_id, type_id=mat["typeID"], quantity=mat["quantity"])
                        )
                for prod in data.get("products") or []:
                    if prod["typeID"] in known:
                        products.append(
                            ActivityProduct(
                                activity_id=act_id,
                                type_id=prod["typeID"],
                                quantity=prod["quantity"],
                                probability=prod.get("probability"),
                            )
                        )

        Blueprint.objects.all().delete()
        Blueprint.objects.bulk_create(blueprints, batch_size=2000)
        BlueprintActivity.objects.bulk_create(activities, batch_size=2000)
        ActivityMaterial.objects.bulk_create(materials, batch_size=2000)
        ActivityProduct.objects.bulk_create(products, batch_size=2000)
        self.stdout.write(
            f"Blueprints: {len(blueprints)}, Tätigkeiten: {len(activities)}, "
            f"Materialien: {len(materials)}, Produkte: {len(products)}"
        )

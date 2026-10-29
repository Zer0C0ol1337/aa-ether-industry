"""Industrie-Strukturen und Rigs der Corp aus Corptools einlesen; Rig-Boni aus eve_sde (sonst ESI), Kostenindizes aus der ESI."""

import logging

from django.apps import apps
from django.conf import settings
from django.db import transaction

from . import esi
from .bonuses import INDUSTRY_STRUCTURE_TYPE_IDS
from .models import IndustryStructure, RigType, SystemCostIndex
from .utils import upsert

logger = logging.getLogger(__name__)

# Optional: nur Strukturen dieser Corp-IDs (Standard: alle Corps mit Corptools-Corp-Audit)
STRUCTURE_CORP_IDS = getattr(settings, "ETHER_INDUSTRY_STRUCTURE_CORP_IDS", None)

# Dogma-Attribute der Rigs, erkannt am Namen (die IDs stehen nicht dokumentiert fest)
_RIG_ATTRS = {
    "engrigmatbonus": "material_bonus",
    "engrigtimebonus": "time_bonus",
    "engrigcostbonus": "cost_bonus",
    "hisecmodifier": "hisec_mod",
    "lowsecmodifier": "lowsec_mod",
    "nullsecmodifier": "nullsec_mod",
}
_attribute_names = {}


def corptools_available() -> bool:
    """True, wenn Corptools installiert ist (Quelle für Strukturen und Rigs)."""
    return apps.is_installed("corptools")


def read_corptools_structures() -> list:
    """Liest die Industrie-Strukturen samt Rig-Type-IDs aus Corptools (ohne zu speichern)."""
    from corptools.models import CorpAsset, Structure

    qs = Structure.objects.filter(type_id__in=INDUSTRY_STRUCTURE_TYPE_IDS).select_related(
        "corporation__corporation", "system_name"
    )
    if STRUCTURE_CORP_IDS:
        qs = qs.filter(corporation__corporation__corporation_id__in=STRUCTURE_CORP_IDS)
    structures = list(qs)
    rigs = {}
    for asset in CorpAsset.objects.filter(
        location_id__in=[s.structure_id for s in structures], location_flag__startswith="RigSlot"
    ):
        rigs.setdefault(asset.location_id, []).append(asset.type_id)
    result = []
    for s in structures:
        system = s.system_name
        result.append({
            "structure_id": s.structure_id,
            "name": s.name,
            "type_id": s.type_id,
            "system_id": s.system_id,
            "system_name": system.name if system else "",
            "security_status": getattr(system, "security_status", None),
            "corporation_name": s.corporation.corporation.corporation_name,
            "rig_type_ids": sorted(rigs.get(s.structure_id, [])),
        })
    return result


def _attribute_name(attribute_id) -> str:
    """Name eines Dogma-Attributs, im Speicher zwischengespeichert."""
    if attribute_id not in _attribute_names:
        _attribute_names[attribute_id] = (esi.fetch_dogma_attribute(attribute_id).get("name") or "").lower()
    return _attribute_names[attribute_id]


def _sde_dogma(type_id):
    """Name und Dogma eines Typs aus django-eveonline-sde (kommt mit Corptools) – oder None, wenn nicht vorhanden."""
    if not apps.is_installed("eve_sde"):
        return None
    from eve_sde.models import ItemType as SdeItemType, TypeDogma

    rows = list(
        TypeDogma.objects.filter(item_type_id=type_id).values_list("dogma_attribute__name", "value")
    )
    if not rows:
        return None
    item = SdeItemType.objects.filter(id=type_id).first()
    return (item.name if item else ""), [((name or "").lower(), value) for name, value in rows]


def _esi_dogma(type_id):
    """Name und Dogma eines Typs aus der ESI (Rückfall, wenn die SDE-Daten fehlen)."""
    data = esi.fetch_type(type_id)
    pairs = [(_attribute_name(a["attribute_id"]), a["value"]) for a in data.get("dogma_attributes") or []]
    return data.get("name") or "", pairs


def load_rig_type(type_id, name="") -> RigType:
    """Holt die Boni eines Rigs aus seiner Dogma: zuerst lokal (eve_sde), sonst aus der ESI.

    Ohne Daten werden nur Name und 'from_dogma=False' gespeichert – der Rechner nutzt dann Standardwerte.
    """
    values = {"name": name or str(type_id), "from_dogma": False}
    try:
        found = _sde_dogma(type_id) or _esi_dogma(type_id)
        values["name"] = found[0] or values["name"]
        for attr_name, value in found[1]:
            field = _RIG_ATTRS.get(attr_name.replace("attribute", ""))
            if field:
                # Material-/Zeit-/Kostenboni stehen in der Dogma als negative Prozentwerte
                values[field] = abs(value) if field.endswith("_bonus") else value
        # Dogma nur verwenden, wenn sie wirklich einen Material- oder Zeitbonus enthält (Attributnamen können abweichen)
        values["from_dogma"] = bool(values.get("material_bonus") or values.get("time_bonus"))
    except Exception:  # weder SDE-Daten noch ESI – Rechner nutzt dann Standardwerte
        logger.warning("Rig %s: Dogma weder aus eve_sde noch aus der ESI ladbar", type_id, exc_info=True)
    rig, _created = RigType.objects.update_or_create(type_id=type_id, defaults=values)
    return rig


def update_cost_indices() -> int:
    """Speichert die Kostenindizes (Herstellung, Reaction) aller Systeme in Prozent."""
    objs = []
    for row in esi.fetch_industry_systems():
        indices = {c["activity"]: c["cost_index"] for c in row.get("cost_indices") or []}
        objs.append(SystemCostIndex(
            system_id=row["solar_system_id"],
            manufacturing=round(indices.get("manufacturing", 0) * 100, 4),
            reaction=round(indices.get("reaction", 0) * 100, 4),
        ))
    upsert(SystemCostIndex, objs, ["system_id"], ["manufacturing", "reaction"])
    return len(objs)


def sync_structures() -> dict:
    """Gleicht die Industrie-Strukturen mit Corptools ab, lädt fehlende Rig-Boni und die Kostenindizes."""
    stats = {"structures": 0, "rigs_loaded": 0, "cost_indices": 0, "corptools": corptools_available()}
    if stats["corptools"]:
        data = read_corptools_structures()
        with transaction.atomic():
            IndustryStructure.objects.exclude(structure_id__in=[d["structure_id"] for d in data]).delete()
            for d in data:
                IndustryStructure.objects.update_or_create(structure_id=d["structure_id"], defaults=d)
        stats["structures"] = len(data)
        known = set(RigType.objects.filter(from_dogma=True).values_list("type_id", flat=True))
        for type_id in {t for d in data for t in d["rig_type_ids"]} - known:
            load_rig_type(type_id)
            stats["rigs_loaded"] += 1
    try:
        stats["cost_indices"] = update_cost_indices()
    except Exception:  # ESI nicht erreichbar – alte Indizes bleiben
        logger.warning("Kostenindizes nicht aus der ESI ladbar", exc_info=True)
    logger.info("Strukturen abgeglichen: %s", stats)
    return stats


def best_skill_levels(user) -> dict:
    """Höchste trainierte Stufe von Industry, Advanced Industry und Reactions über alle Charaktere des Users."""
    from .bonuses import SKILL_ADVANCED_INDUSTRY, SKILL_INDUSTRY, SKILL_REACTIONS

    levels = {SKILL_INDUSTRY: 0, SKILL_ADVANCED_INDUSTRY: 0, SKILL_REACTIONS: 0}
    if not corptools_available():
        return levels
    from corptools.models import Skill

    rows = Skill.objects.filter(
        character__character__character_ownership__user=user, skill_id__in=list(levels)
    ).values_list("skill_id", "active_skill_level")
    for skill_id, level in rows:
        levels[skill_id] = max(levels[skill_id], level or 0)
    return levels


def corp_blueprints(blueprint_type_id) -> list:
    """Eigene Corp-Blueprints dieses Typs mit ME/TE (BPO und BPC), beste zuerst."""
    if not corptools_available():
        return []
    from corptools.models import CorpAsset

    rows = CorpAsset.objects.filter(type_id=blueprint_type_id, material_efficiency__isnull=False)
    if STRUCTURE_CORP_IDS:
        rows = rows.filter(corporation__corporation__corporation_id__in=STRUCTURE_CORP_IDS)
    seen, result = set(), []
    for a in rows.order_by("-material_efficiency", "-time_efficiency"):
        bpc = bool(a.blueprint_copy) or (a.runs is not None and a.runs >= 0)
        key = (a.material_efficiency, a.time_efficiency, bpc)
        if key in seen:
            continue
        seen.add(key)
        result.append({"me": a.material_efficiency, "te": a.time_efficiency, "bpc": bpc, "runs": a.runs})
    return result[:8]

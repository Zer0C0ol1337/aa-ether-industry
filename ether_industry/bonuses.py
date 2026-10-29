"""Industrie-Boni: Strukturen, Rigs, Sicherheitsstatus, Skills und Implantate.

Formeln (Stand Industrie-Mechanik von CCP):
- Material pro Run: ceil(Basis × (1 − ME) × (1 − Struktur-ME) × (1 − Rig-ME)), mindestens 1 pro Run
- Zeit (Herstellung): Basis × (1 − TE) × (1 − Struktur-TE) × (1 − Rig-TE) × Skills × Implantat
- Zeit (Reaction): Basis × (1 − Struktur-TE) × (1 − Rig-TE) × (1 − 4 % × Reactions)
- Jobkosten: EIV × (Kostenindex × (1 − Struktur-Kostenbonus) + Steuer + SCC)
- Rig-Boni werden mit dem Sicherheits-Multiplikator des Systems multipliziert (Werte kommen aus der Dogma des Rigs)

TE senkt nur die Zeit, nie die ISK-Jobkosten.
"""

from dataclasses import dataclass

# Rollen-Boni der Strukturen in Prozent: (Material, Zeit, Jobkosten) und für welche Tätigkeit sie gelten
STRUCTURE_BONUSES = {
    35825: {"name": "Raitaru", "activity": "manufacturing", "me": 1.0, "te": 15.0, "cost": 3.0},
    35826: {"name": "Azbel", "activity": "manufacturing", "me": 1.0, "te": 20.0, "cost": 4.0},
    35827: {"name": "Sotiyo", "activity": "manufacturing", "me": 1.0, "te": 30.0, "cost": 5.0},
    35835: {"name": "Athanor", "activity": "reaction", "me": 0.0, "te": 0.0, "cost": 0.0},
    35836: {"name": "Tatara", "activity": "reaction", "me": 0.0, "te": 25.0, "cost": 0.0},
}
INDUSTRY_STRUCTURE_TYPE_IDS = tuple(STRUCTURE_BONUSES)

# Skills (Type-IDs) und ihr Zeitbonus pro Stufe in Prozent
SKILL_INDUSTRY = 3380          # Herstellungszeit −4 % pro Stufe
SKILL_ADVANCED_INDUSTRY = 3388  # Herstellungszeit −3 % pro Stufe
SKILL_REACTIONS = 45746        # Reaction-Zeit −4 % pro Stufe
SKILL_IDS = (SKILL_INDUSTRY, SKILL_ADVANCED_INDUSTRY, SKILL_REACTIONS)

# Implantate "Zainou 'Beancounter' Industry BX-80x": Herstellungszeit in Prozent
IMPLANTS = ((0, "kein Implantat"), (1, "BX-801 (−1 %)"), (2, "BX-802 (−2 %)"), (4, "BX-804 (−4 %)"))

# Rig-Familien: Schlüsselwort im Rig-Namen → welche Produkte (Kategorie- bzw. Gruppen-IDs) sie betreffen.
# CCP liefert diese Zuordnung nicht in den Daten mit; sie ist hier gepflegt und im Rechner überschreibbar.
SHIP_GROUPS = {
    "small_basic": {25, 420, 31, 237},                       # Frigate, Destroyer, Shuttle, Corvette
    "small_advanced": {324, 831, 830, 834, 893, 541, 1305, 1534, 1283, 1527},
    "medium_basic": {26, 419, 1201, 28, 463},                # Cruiser, Battlecruiser, Industrial, Mining Barge
    "medium_advanced": {358, 832, 833, 906, 894, 540, 963, 380, 543, 1972},
    "large_basic": {27, 941},                                # Battleship, Industrial Command Ship
    "large_advanced": {900, 898},                            # Marauder, Black Ops
    "capital": {485, 547, 1538, 659, 30, 883, 513, 902, 4594},
}
CAT_SHIP, CAT_MODULE, CAT_CHARGE, CAT_DRONE, CAT_IMPLANT, CAT_DEPLOYABLE = 6, 7, 8, 18, 20, 22
CAT_STRUCTURE, CAT_STRUCTURE_MODULE, CAT_FIGHTER = 65, 66, 87

# (Schlüsselwort, Tätigkeit, Kategorien, Gruppen) – längere/genauere Schlüsselwörter zuerst
RIG_FAMILIES = (
    ("Equipment and Consumable", "manufacturing",
     {CAT_MODULE, CAT_CHARGE, CAT_DRONE, CAT_IMPLANT, CAT_DEPLOYABLE, CAT_FIGHTER}, set()),
    ("Structure and Component", "manufacturing", {CAT_STRUCTURE, CAT_STRUCTURE_MODULE}, {334, 536, 873, 913}),
    ("Advanced Capital Component", "manufacturing", set(), {913}),
    ("Basic Capital Component", "manufacturing", set(), {873}),
    ("Capital Component", "manufacturing", set(), {873, 913}),
    ("Advanced Component", "manufacturing", set(), {334}),
    ("Structure Component", "manufacturing", set(), {536}),
    ("Basic Small Ship", "manufacturing", set(), SHIP_GROUPS["small_basic"]),
    ("Basic Medium Ship", "manufacturing", set(), SHIP_GROUPS["medium_basic"]),
    ("Basic Large Ship", "manufacturing", set(), SHIP_GROUPS["large_basic"]),
    ("Advanced Small Ship", "manufacturing", set(), SHIP_GROUPS["small_advanced"]),
    ("Advanced Medium Ship", "manufacturing", set(), SHIP_GROUPS["medium_advanced"]),
    ("Advanced Large Ship", "manufacturing", set(), SHIP_GROUPS["large_advanced"]),
    ("Capital Ship", "manufacturing", set(), SHIP_GROUPS["capital"]),
    ("Ship", "manufacturing", {CAT_SHIP}, set()),
    ("Equipment", "manufacturing", {CAT_MODULE, CAT_IMPLANT, CAT_DEPLOYABLE}, set()),
    ("Ammunition", "manufacturing", {CAT_CHARGE}, set()),
    ("Drone and Fighter", "manufacturing", {CAT_DRONE, CAT_FIGHTER}, set()),
    ("Structure", "manufacturing", {CAT_STRUCTURE, CAT_STRUCTURE_MODULE}, set()),
    ("Composite Reactor", "reaction", set(), {428, 429}),
    ("Biochemical Reactor", "reaction", set(), {712}),
    ("Hybrid Reactor", "reaction", set(), {974}),
)

# Rückfallwerte, falls die Rig-Dogma (noch) nicht geladen werden konnte
FALLBACK_RIG = {"T1": (2.0, 20.0), "T2": (2.4, 24.0)}
FALLBACK_SECURITY = {"high": 1.0, "low": 1.9, "null": 2.1, "wh": 2.1}
FALLBACK_SECURITY_REACTOR = {"high": 0.0, "low": 1.0, "null": 1.1, "wh": 1.1}


def security_band(system_id, security_status) -> str:
    """Sicherheitszone wie im Spiel: 'high' (ab 0,5 gerundet), 'low', 'null' oder 'wh' (J-Systeme)."""
    if system_id and int(system_id) >= 31000000:
        return "wh"
    if security_status is None:
        return "null"
    if security_status >= 0.45:
        return "high"
    if security_status > 0.0:
        return "low"
    return "null"


def rig_family(rig_name: str):
    """Findet die Rig-Familie zum Rig-Namen, z. B. 'Equipment' – oder None (Forschung, Reprocessing …)."""
    for keyword, activity, categories, groups in RIG_FAMILIES:
        if f" {keyword} " in f" {rig_name} ":
            return {"keyword": keyword, "activity": activity, "categories": categories, "groups": groups}
    return None


def rig_applies(rig_name: str, activity: str, category_id, group_id) -> bool:
    """True, wenn das Rig laut Familie für dieses Produkt und diese Tätigkeit gilt."""
    family = rig_family(rig_name)
    if family is None or family["activity"] != activity:
        return False
    return category_id in family["categories"] or group_id in family["groups"]


@dataclass
class RigBonus:
    """Bonus eines Rigs in Prozent, schon mit dem Sicherheits-Multiplikator verrechnet."""

    type_id: int
    name: str
    me: float
    te: float
    multiplier: float
    estimated: bool  # True = Rückfallwerte statt echter Dogma-Werte


def rig_bonus(rig, band: str) -> RigBonus:
    """Bonus eines RigType-Eintrags in einer Sicherheitszone."""
    reactor = " Reactor " in f" {rig.name} "
    if rig.from_dogma:
        multiplier = {"high": rig.hisec_mod, "low": rig.lowsec_mod, "null": rig.nullsec_mod, "wh": rig.nullsec_mod}[band]
        me, te, estimated = rig.material_bonus, rig.time_bonus, False
    else:
        tier = "T2" if rig.name.rstrip().endswith(" II") else "T1"
        me, te = FALLBACK_RIG[tier]
        multiplier = (FALLBACK_SECURITY_REACTOR if reactor else FALLBACK_SECURITY)[band]
        estimated = True
    multiplier = multiplier if multiplier is not None else 1.0
    return RigBonus(rig.type_id, rig.name, me * multiplier, te * multiplier, multiplier, estimated)


def time_multiplier(activity: str, te_pct=0.0, structure_te=0.0, rig_te=0.0, industry=0, advanced_industry=0,
                    reactions=0, implant_pct=0.0) -> float:
    """Faktor auf die Grundzeit pro Run (1.0 = keine Boni)."""
    factor = (1 - structure_te / 100) * (1 - rig_te / 100)
    if activity == "reaction":
        return factor * (1 - 0.04 * reactions)
    return (
        factor * (1 - te_pct / 100) * (1 - 0.04 * industry) * (1 - 0.03 * advanced_industry)
        * (1 - implant_pct / 100)
    )


def combined_material_bonus(*bonuses_pct) -> float:
    """Mehrere Prozent-Boni (Struktur, Rigs) multiplikativ zu einem Prozentwert zusammengefasst."""
    factor = 1.0
    for value in bonuses_pct:
        factor *= 1 - (value or 0) / 100
    return (1 - factor) * 100

"""Tests: Boni-Formeln (ohne Datenbank) und Rechnung mit Struktur, Rig und TE."""

from django.test import SimpleTestCase, TestCase

from ether_industry import bonuses
from ether_industry.calc import calculate
from ether_industry.models import (
    ActivityMaterial, ActivityProduct, Blueprint, BlueprintActivity, ItemPrice, ItemType, RigType,
)


class TestSecurity(SimpleTestCase):
    """security_band()"""

    def test_bands(self):
        """Highsec ab 0,45 (wird im Spiel als 0,5 angezeigt), Lowsec bis 0,0, J-Systeme sind Wurmloch."""
        self.assertEqual(bonuses.security_band(30000142, 0.946), "high")
        self.assertEqual(bonuses.security_band(1, 0.45), "high")
        self.assertEqual(bonuses.security_band(1, 0.44), "low")
        self.assertEqual(bonuses.security_band(1, 0.01), "low")
        self.assertEqual(bonuses.security_band(1, -0.3), "null")
        self.assertEqual(bonuses.security_band(31000005, -1.0), "wh")


class TestRigs(SimpleTestCase):
    """rig_family(), rig_applies(), rig_bonus()"""

    def test_family_by_name(self):
        """Längere Schlüsselwörter gehen vor (Structure Component vor Structure, Basic Small Ship vor Ship)."""
        self.assertEqual(bonuses.rig_family("Standup M-Set Structure Component Manufacturing Material Efficiency I")["keyword"], "Structure Component")
        self.assertEqual(bonuses.rig_family("Standup M-Set Basic Small Ship Manufacturing Time Efficiency II")["keyword"], "Basic Small Ship")
        self.assertEqual(bonuses.rig_family("Standup XL-Set Ship Manufacturing Efficiency I")["keyword"], "Ship")
        self.assertIsNone(bonuses.rig_family("Standup M-Set Invention Accelerator I"))

    def test_applies(self):
        """Equipment-Rig für Module, nicht für Schiffe; Reactor-Rig nur für Reactions."""
        rig = "Standup M-Set Equipment Manufacturing Material Efficiency I"
        self.assertTrue(bonuses.rig_applies(rig, "manufacturing", bonuses.CAT_MODULE, 55))
        self.assertFalse(bonuses.rig_applies(rig, "manufacturing", bonuses.CAT_SHIP, 25))
        self.assertTrue(bonuses.rig_applies("Standup M-Set Basic Small Ship Manufacturing Material Efficiency I",
                                            "manufacturing", bonuses.CAT_SHIP, 25))
        reactor = "Standup M-Set Composite Reactor Material Efficiency I"
        self.assertTrue(bonuses.rig_applies(reactor, "reaction", 4, 429))
        self.assertFalse(bonuses.rig_applies(reactor, "manufacturing", 4, 429))

    def test_rig_bonus_from_dogma_with_security(self):
        """Dogma-Werte × Sicherheits-Multiplikator, Wurmloch wie Nullsec."""
        rig = RigType(type_id=1, name="Standup M-Set Equipment Manufacturing Material Efficiency II",
                      material_bonus=2.4, time_bonus=0, hisec_mod=1.0, lowsec_mod=1.9, nullsec_mod=2.1, from_dogma=True)
        self.assertAlmostEqual(bonuses.rig_bonus(rig, "high").me, 2.4)
        self.assertAlmostEqual(bonuses.rig_bonus(rig, "null").me, 5.04)
        self.assertAlmostEqual(bonuses.rig_bonus(rig, "wh").me, 5.04)
        self.assertFalse(bonuses.rig_bonus(rig, "low").estimated)

    def test_rig_bonus_fallback(self):
        """Ohne ESI: Standardwerte T1/T2, Reactor-Rigs mit eigenen Multiplikatoren."""
        t2 = RigType(type_id=2, name="Standup M-Set Equipment Manufacturing Time Efficiency II", from_dogma=False)
        b = bonuses.rig_bonus(t2, "low")
        self.assertTrue(b.estimated)
        self.assertAlmostEqual(b.te, 24.0 * 1.9)
        reactor = RigType(type_id=3, name="Standup M-Set Composite Reactor Material Efficiency I", from_dogma=False)
        self.assertAlmostEqual(bonuses.rig_bonus(reactor, "null").me, 2.0 * 1.1)


class TestTime(SimpleTestCase):
    """time_multiplier(), combined_material_bonus()"""

    def test_manufacturing_time(self):
        """TE 20, Raitaru 15 %, Industry 5, Advanced Industry 5, BX-804."""
        factor = bonuses.time_multiplier("manufacturing", te_pct=20, structure_te=15, industry=5,
                                         advanced_industry=5, implant_pct=4)
        self.assertAlmostEqual(factor, 0.8 * 0.85 * 0.8 * 0.85 * 0.96)

    def test_reaction_time_ignores_te_and_industry(self):
        """Reactions: nur Struktur, Rig und Reactions-Skill."""
        factor = bonuses.time_multiplier("reaction", te_pct=20, structure_te=25, industry=5, reactions=4)
        self.assertAlmostEqual(factor, 0.75 * 0.84)

    def test_combined_material_bonus(self):
        """1 % Struktur und 4,2 % Rig ergeben multiplikativ 5,158 %."""
        self.assertAlmostEqual(bonuses.combined_material_bonus(1.0, 4.2), 5.158)


class TestCalculate(TestCase):
    """calculate() mit Zeitfaktor und Struktur-Kostenbonus."""

    @classmethod
    def setUpTestData(cls):
        """Ein Blueprint: 1 Run braucht 100 Tritanium (Adjusted 10 ISK), ergibt 1 Produkt (Jita 2000 ISK)."""
        trit = ItemType.objects.create(type_id=34, name="Tritanium", category_id=4, group_id=18, published=True)
        prod = ItemType.objects.create(type_id=1000, name="Widget", category_id=7, group_id=55, published=True)
        bp_type = ItemType.objects.create(type_id=1001, name="Widget Blueprint", category_id=9, published=True)
        bp = Blueprint.objects.create(type=bp_type)
        cls.activity = BlueprintActivity.objects.create(
            id=BlueprintActivity.make_id(1001, 1), blueprint=bp, activity=BlueprintActivity.MANUFACTURING, time=3600,
        )
        ActivityMaterial.objects.create(activity=cls.activity, type=trit, quantity=100)
        ActivityProduct.objects.create(activity=cls.activity, type=prod, quantity=1)
        ItemPrice.objects.create(type=trit, adjusted_price=10, jita_sell=5, jita_buy=4)
        ItemPrice.objects.create(type=prod, jita_sell=2000, jita_buy=1500)

    def _calc(self, **kw):
        """calculate() mit Standardwerten für den Test."""
        args = dict(runs=10, me_pct=10, bonus_pct=0, cost_index_pct=5, facility_tax_pct=1,
                    material_mode="sell", product_mode="sell")
        args.update(kw)
        return calculate(self.activity, **args)

    def test_te_changes_time_not_cost(self):
        """TE/Zeitfaktor ändert nur die Bauzeit – Jobkosten bleiben gleich."""
        plain, fast = self._calc(), self._calc(time_factor=0.5)
        self.assertEqual(plain["job_cost"], fast["job_cost"])
        self.assertEqual(plain["duration"], 36000)
        self.assertEqual(fast["duration"], 18000)
        self.assertAlmostEqual(fast["isk_per_hour"], fast["profit"] / 5)

    def test_structure_cost_bonus_on_index_only(self):
        """Sotiyo −5 % gilt nur auf den Kostenindex-Anteil: EIV 10.000 × (5 % × 0,95 + 1 % + 4 %)."""
        r = self._calc(structure_cost_bonus_pct=5)
        self.assertAlmostEqual(r["eiv"], 10000)
        self.assertAlmostEqual(r["job_cost"], 10000 * (4.75 + 1 + 4) / 100)

    def test_material_bonus(self):
        """ME 10 und 5,158 % Struktur+Rig: 100 × 10 × 0,9 × 0,94842 = 853,6 → 854."""
        r = self._calc(bonus_pct=bonuses.combined_material_bonus(1.0, 4.2))
        self.assertEqual(r["materials"][0]["qty"], 854)

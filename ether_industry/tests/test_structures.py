"""Tests: Strukturen und Rigs aus Corptools einlesen (ESI gemockt) und die Rechner-Seite."""

from unittest import mock

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from ether_industry.models import (
    ActivityMaterial, ActivityProduct, Blueprint, BlueprintActivity, IndustryStructure, ItemPrice, ItemType, RigType,
    SystemCostIndex,
)
from ether_industry.structures import best_skill_levels, sync_structures

RIG_ME = 37165   # Test-IDs für zwei Rigs
RIG_TE = 37166

DOGMA_NAMES = {1: "attributeEngRigMatBonus", 2: "attributeEngRigTimeBonus", 3: "hiSecModifier",
               4: "lowSecModifier", 5: "nullSecModifier"}
TYPES = {
    RIG_ME: {"name": "Standup M-Set Equipment Manufacturing Material Efficiency II",
             "dogma_attributes": [{"attribute_id": 1, "value": -2.4}, {"attribute_id": 3, "value": 1.0},
                                  {"attribute_id": 4, "value": 1.9}, {"attribute_id": 5, "value": 2.1}]},
    RIG_TE: {"name": "Standup M-Set Equipment Manufacturing Time Efficiency I",
             "dogma_attributes": [{"attribute_id": 2, "value": -20.0}, {"attribute_id": 3, "value": 1.0},
                                  {"attribute_id": 4, "value": 1.9}, {"attribute_id": 5, "value": 2.1}]},
}


def _esi_mocks():
    """Patches für die drei ESI-Aufrufe des Abgleichs."""
    return (
        mock.patch("ether_industry.esi.fetch_type", side_effect=lambda t: TYPES[t]),
        mock.patch("ether_industry.esi.fetch_dogma_attribute", side_effect=lambda a: {"name": DOGMA_NAMES[a]}),
        mock.patch("ether_industry.esi.fetch_industry_systems", return_value=[
            {"solar_system_id": 30002000, "cost_indices": [
                {"activity": "manufacturing", "cost_index": 0.0321}, {"activity": "reaction", "cost_index": 0.01}]},
        ]),
    )


class StructureSyncTest(TestCase):
    """Corp mit einer Raitaru im Nullsec, zwei Rigs und einem BPO; User mit Industry-Skills."""

    @classmethod
    def setUpTestData(cls):
        """Corptools-Daten wie nach einem Corp-Audit."""
        from corptools.models import CharacterAudit, CorpAsset, CorporationAudit, Skill, Structure
        from eve_sde.models import SolarSystem

        corp = EveCorporationInfo.objects.create(corporation_id=98000001, corporation_name="Ether Element",
                                                 corporation_ticker="3THEL", member_count=10)
        audit = CorporationAudit.objects.create(corporation=corp)
        system = SolarSystem.objects.create(id=30002000, name="R-ARKN", security_status=-0.25)
        Structure.objects.create(
            corporation=audit, structure_id=1035000000001, system_id=30002000, system_name=system, type_id=35825,
            name="R-ARKN - Werkbank", profile_id=1, reinforce_hour=20, state="shield_vulnerable",
        )
        Structure.objects.create(  # keine Industrie-Struktur → wird ignoriert
            corporation=audit, structure_id=1035000000002, system_id=30002000, type_id=35832,
            name="R-ARKN - Astrahus", profile_id=1, reinforce_hour=20, state="shield_vulnerable",
        )
        for slot, rig in enumerate((RIG_ME, RIG_TE)):
            CorpAsset.objects.create(corporation=audit, item_id=900 + slot, location_id=1035000000001,
                                     location_flag=f"RigSlot{slot}", location_type="item", quantity=1,
                                     singleton=True, type_id=rig)
        # Produkt + Blueprint für die Rechner-Seite
        trit = ItemType.objects.create(type_id=34, name="Tritanium", category_id=4, group_id=18, published=True)
        module = ItemType.objects.create(type_id=2000, name="Test Module", category_id=7, group_id=55, published=True)
        bp_type = ItemType.objects.create(type_id=2001, name="Test Module Blueprint", category_id=9, published=True)
        bp = Blueprint.objects.create(type=bp_type)
        cls.activity = BlueprintActivity.objects.create(
            id=BlueprintActivity.make_id(2001, 1), blueprint=bp, activity=BlueprintActivity.MANUFACTURING, time=6000,
        )
        ActivityMaterial.objects.create(activity=cls.activity, type=trit, quantity=1000)
        ActivityProduct.objects.create(activity=cls.activity, type=module, quantity=1)
        ItemPrice.objects.create(type=trit, adjusted_price=5, jita_sell=4)
        ItemPrice.objects.create(type=module, jita_sell=10000)
        CorpAsset.objects.create(corporation=audit, item_id=950, location_id=1, location_flag="CorpSAG1",
                                 location_type="item", quantity=1, singleton=True, type_id=2001,
                                 material_efficiency=9, time_efficiency=18, runs=-1, blueprint_copy=False)
        # User mit Charakter und Skills
        cls.user = User.objects.create_user("dave")
        char = EveCharacter.objects.create(character_id=91, character_name="Dave", corporation_id=98000001,
                                           corporation_name="Ether Element", corporation_ticker="3THEL")
        CharacterOwnership.objects.create(user=cls.user, character=char, owner_hash="h91")
        cls.user.profile.main_character = char
        cls.user.profile.save()
        char_audit = CharacterAudit.objects.create(character=char)
        for skill_id, level in ((3380, 5), (3388, 4), (45746, 3)):
            Skill.objects.create(character=char_audit, skill_id=skill_id, active_skill_level=level,
                                 trained_skill_level=level, skillpoints_in_skill=1)
        cls.user.user_permissions.add(Permission.objects.get(codename="basic_access",
                                                             content_type__app_label="ether_industry"))

    def _sync(self):
        """Abgleich mit gemockter ESI."""
        patches = _esi_mocks()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return sync_structures()

    def test_sync_reads_structure_and_rigs(self):
        """Nur die Raitaru wird übernommen, mit Nullsec-Sicherheit, beiden Rigs und deren Dogma-Werten."""
        stats = self._sync()
        self.assertEqual(stats["structures"], 1)
        st = IndustryStructure.objects.get()
        self.assertEqual(st.system_name, "R-ARKN")
        self.assertEqual(st.rig_type_ids, [RIG_ME, RIG_TE])
        rig = RigType.objects.get(type_id=RIG_ME)
        self.assertTrue(rig.from_dogma)
        self.assertAlmostEqual(rig.material_bonus, 2.4)
        self.assertAlmostEqual(rig.nullsec_mod, 2.1)
        self.assertAlmostEqual(SystemCostIndex.objects.get(system_id=30002000).manufacturing, 3.21)

    def test_sync_without_esi_keeps_fallback(self):
        """ESI weg: Struktur wird trotzdem übernommen, Rigs mit Standardwerten markiert."""
        with mock.patch("ether_industry.esi.fetch_type", side_effect=ConnectionError("down")), \
                mock.patch("ether_industry.esi.fetch_industry_systems", side_effect=ConnectionError("down")):
            stats = sync_structures()
        self.assertEqual(stats["structures"], 1)
        self.assertFalse(RigType.objects.get(type_id=RIG_ME).from_dogma)

    def test_rig_dogma_from_local_sde_first(self):
        """Liegen die Rig-Dogma in eve_sde, wird die ESI gar nicht gefragt."""
        from eve_sde.models import DogmaAttribute, ItemType as SdeItemType, TypeDogma

        from ether_industry.structures import load_rig_type

        rig = SdeItemType.objects.create(id=RIG_ME, name=TYPES[RIG_ME]["name"])
        for attr_id, name in DOGMA_NAMES.items():
            DogmaAttribute.objects.create(id=attr_id, name=name)
        for entry in TYPES[RIG_ME]["dogma_attributes"]:
            TypeDogma.objects.create(item_type=rig, dogma_attribute_id=entry["attribute_id"], value=entry["value"])
        with mock.patch("ether_industry.esi.fetch_type") as esi_type:
            loaded = load_rig_type(RIG_ME)
        esi_type.assert_not_called()
        self.assertTrue(loaded.from_dogma)
        self.assertAlmostEqual(loaded.material_bonus, 2.4)
        self.assertAlmostEqual(loaded.lowsec_mod, 1.9)

    def test_best_skills(self):
        """Skills kommen aus Corptools."""
        self.assertEqual(best_skill_levels(self.user), {3380: 5, 3388: 4, 45746: 3})

    def test_calculator_with_structure(self):
        """Raitaru im Nullsec mit T2-ME-Rig und T1-TE-Rig: Boni, Kostenindex und Skills landen in der Rechnung."""
        self._sync()
        self.client.force_login(self.user)
        url = reverse("ether_industry:calculator", args=[self.activity.id])
        resp = self.client.get(url, {"structure": "1035000000001", "runs": 1, "me": 10, "te": 20})
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        # automatisch: beide passenden Rigs (ME und TE) gelten
        self.assertEqual([r.type_id for r in ctx["applied_rigs"]], [RIG_ME, RIG_TE])
        self.assertAlmostEqual(ctx["bonus_summary"]["rig_me"], 2.4 * 2.1)
        self.assertAlmostEqual(ctx["bonus_summary"]["rig_te"], 20 * 2.1)
        # Zeit: 6000 s × TE 0,8 × Raitaru 0,85 × Rig 0,58 × Industry 0,8 × Adv. Industry 0,88
        self.assertEqual(ctx["r"]["duration"], round(6000 * 0.8 * 0.85 * 0.58 * 0.8 * 0.88))
        self.assertEqual(ctx["auto_index"], 3.21)
        self.assertAlmostEqual(ctx["p"]["index"], 3.21)
        self.assertEqual((ctx["p"]["ind"], ctx["p"]["adv"]), (5, 4))
        self.assertEqual(ctx["corp_blueprints"][0]["me"], 9)
        # 1000 × 0,9 × (1 − 1 %) × (1 − 5,04 %) = 846,07 → 847
        self.assertEqual(ctx["r"]["materials"][0]["qty"], 847)
        self.assertContains(resp, "Gewinn pro Stunde")

    def test_calculator_manual_without_structure(self):
        """Ohne Struktur bleiben die frei eingegebenen Boni und die Seite funktioniert ohne Corptools-Daten."""
        self.client.force_login(self.user)
        url = reverse("ether_industry:calculator", args=[self.activity.id])
        resp = self.client.get(url, {"runs": 2, "bonus": "1", "tebonus": "15", "index": "4"})
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.context["bonus_summary"]["structure_te"], 15.0)
        self.assertIsNone(resp.context["info"])

    def test_index_lists_structures_and_sync_needs_manager(self):
        """Übersicht für alle mit Zugriff; Neu-Einlesen nur mit manage_industry."""
        self._sync()
        self.client.force_login(self.user)
        resp = self.client.get(reverse("ether_industry:index"))
        self.assertContains(resp, "R-ARKN - Werkbank")
        self.assertEqual(self.client.post(reverse("ether_industry:sync_structures")).status_code, 403)

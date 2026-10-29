"""Views des Industrie-Rechners."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import bonuses
from .calc import calculate
from .models import ActivityProduct, BlueprintActivity, IndustryStructure, ItemPrice, RigType, SystemCostIndex
from .structures import best_skill_levels, corp_blueprints, corptools_available

CALC_ACTIVITIES = (BlueprintActivity.MANUFACTURING, BlueprintActivity.REACTION)
AUTOCOMPLETE_LIMIT = 15


def check_access(view):
    """Decorator: Login und Recht basic_access, sonst PermissionDenied (wie in aa-miningtax)."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.has_perm("ether_industry.basic_access"):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def _number(request, key, default, low, high, cast=float):
    """Liest eine Zahl aus der URL, mit Standardwert und Begrenzung auf low..high."""
    raw = request.GET.get(key, "").replace(",", ".").strip()
    try:
        value = cast(float(raw)) if raw else default
    except ValueError:
        value = default
    return max(low, min(high, value))


def _price_status():
    """Zeitpunkt der letzten Preis-Aktualisierung für die Anzeige."""
    return ItemPrice.objects.aggregate(jita=Max("jita_updated"), adjusted=Max("adjusted_updated"))


def _product_base():
    """Grundabfrage: veröffentlichte Produkte aus Herstellung und Reactions."""
    return ActivityProduct.objects.filter(
        activity__activity__in=CALC_ACTIVITIES, type__published=True
    ).select_related("type", "activity", "activity__blueprint__type")


def _search_products(query, limit):
    """Sucht Produkte: zuerst Namen, die mit der Eingabe beginnen, danach Namen, die sie enthalten."""
    base = _product_base()
    starts = list(
        base.filter(Q(type__name__istartswith=query) | Q(type__name_de__istartswith=query)).order_by(
            "type__name"
        )[:limit]
    )
    if len(starts) >= limit:
        return starts
    contains = (
        base.filter(Q(type__name__icontains=query) | Q(type__name_de__icontains=query))
        .exclude(pk__in=[p.pk for p in starts])
        .order_by("type__name")[: limit - len(starts)]
    )
    return starts + list(contains)


@check_access
def index(request):
    """Route /: Produktsuche mit Autovervollständigung, Ergebnisliste und Übersicht der Corp-Strukturen."""
    query = request.GET.get("q", "").strip()
    results = _search_products(query, 50) if len(query) >= 2 else []
    structures = [
        _structure_info(st, bonuses.STRUCTURE_BONUSES.get(st.type_id, {}).get("activity", "manufacturing"), None)
        for st in IndustryStructure.objects.all()
    ]
    return render(
        request,
        "ether_industry/index.html",
        {
            "q": query, "results": results, "prices": _price_status(), "structures": structures,
            "can_manage": request.user.has_perm("ether_industry.manage_industry"), "corptools": corptools_available(),
        },
    )


@check_access
def autocomplete(request):
    """Route /autocomplete/?q=…: liefert passende Produkte als JSON für das Suchfeld."""
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    results = [
        {
            "type_id": p.type.type_id,
            "name": p.type.name,
            "name_de": p.type.name_de if p.type.name_de != p.type.name else "",
            "activity": p.activity.get_activity_display(),
            "url": reverse("ether_industry:calculator", args=[p.activity.id]),
        }
        for p in _search_products(query, AUTOCOMPLETE_LIMIT)
    ]
    return JsonResponse({"results": results})


SESSION_KEY = "ether_industry_defaults"
DEFAULT_KEYS = ("structure", "ind", "adv", "react", "implant", "tax")


def _structures_for(activity_code):
    """Strukturen, in denen diese Tätigkeit möglich ist: Engineering Complexes bzw. Refineries."""
    wanted = "reaction" if activity_code == BlueprintActivity.REACTION else "manufacturing"
    type_ids = [t for t, b in bonuses.STRUCTURE_BONUSES.items() if b["activity"] == wanted]
    return list(IndustryStructure.objects.filter(type_id__in=type_ids))


def _structure_info(structure, activity_name, product):
    """Boni einer Struktur für eine Tätigkeit: Rollenbonus, Sicherheitszone, Rigs (mit Vorschlag)."""
    role = bonuses.STRUCTURE_BONUSES.get(structure.type_id, {})
    applies = role.get("activity") == activity_name
    band = bonuses.security_band(structure.system_id, structure.security_status)
    rig_map = {r.type_id: r for r in RigType.objects.filter(type_id__in=structure.rig_type_ids)}
    rigs = []
    for type_id in structure.rig_type_ids:
        rig = rig_map.get(type_id) or RigType(type_id=type_id, name=f"Rig {type_id}")
        b = bonuses.rig_bonus(rig, band)
        if not (b.me or b.te):
            continue  # Forschungs-, Reprocessing- oder Invention-Rigs
        b.suggested = product is not None and bonuses.rig_applies(
            rig.name, activity_name, product.category_id, product.group_id
        )
        rigs.append(b)
    index = SystemCostIndex.objects.filter(system_id=structure.system_id).first()
    return {
        "structure": structure,
        "type_name": role.get("name", ""),
        "band": band,
        "me": role.get("me", 0.0) if applies else 0.0,
        "te": role.get("te", 0.0) if applies else 0.0,
        "cost": role.get("cost", 0.0) if applies else 0.0,
        "rigs": rigs,
        "cost_index": (index.reaction if activity_name == "reaction" else index.manufacturing) if index else None,
    }


def _defaults(request):
    """Gespeicherte Voreinstellungen des Users (Struktur, Skills, Implantat, Steuer) aus der Session."""
    stored = request.session.get(SESSION_KEY) or {}
    if "ind" not in stored:
        levels = best_skill_levels(request.user)
        stored.update(
            ind=levels[bonuses.SKILL_INDUSTRY], adv=levels[bonuses.SKILL_ADVANCED_INDUSTRY],
            react=levels[bonuses.SKILL_REACTIONS], from_skills=corptools_available(),
        )
    return stored


@check_access
def calculator(request, activity_id):
    """Route /calc/<id>/: Kostenrechnung für eine Herstellung oder Reaction mit Struktur, Rigs, TE und Skills."""
    activity = get_object_or_404(
        BlueprintActivity.objects.select_related("blueprint__type"),
        pk=activity_id,
        activity__in=CALC_ACTIVITIES,
    )
    is_manufacturing = activity.activity == BlueprintActivity.MANUFACTURING
    activity_name = "manufacturing" if is_manufacturing else "reaction"
    first_product = activity.products.select_related("type").first()
    product = first_product.type if first_product else None
    defaults = _defaults(request)
    get = request.GET.get

    # Struktur: aus der URL, sonst die zuletzt genutzte (wenn sie zur Tätigkeit passt)
    structures = _structures_for(activity.activity)
    by_id = {str(st.structure_id): st for st in structures}
    structure_key = get("structure", str(defaults.get("structure", "")))
    structure = by_id.get(structure_key)
    info = _structure_info(structure, activity_name, product) if structure else None

    # Rigs: "auto" = alle passenden Rigs (ME- und TE-Rig gelten gleichzeitig), "none" = keines,
    # sonst die Type-ID eines bestimmten Rigs der Struktur
    rig_choice = get("rig", "auto")
    applied_rigs = []
    if info:
        if rig_choice == "auto":
            applied_rigs = [r for r in info["rigs"] if r.suggested]
        elif rig_choice != "none":
            applied_rigs = [r for r in info["rigs"] if str(r.type_id) == rig_choice]

    auto_index = info["cost_index"] if info and info["cost_index"] is not None else None
    params = {
        "runs": _number(request, "runs", 1, 1, 100000, int),
        "me": _number(request, "me", 10 if is_manufacturing else 0, 0, 10, int),
        "te": _number(request, "te", 20 if is_manufacturing else 0, 0, 20, int),
        "bonus": _number(request, "bonus", 0.0, 0.0, 10.0),
        "tebonus": _number(request, "tebonus", 0.0, 0.0, 50.0),
        "index": _number(request, "index", auto_index if auto_index is not None else 5.0, 0.0, 50.0),
        "tax": _number(request, "tax", float(defaults.get("tax", 0.0)), 0.0, 50.0),
        "ind": _number(request, "ind", int(defaults.get("ind", 0)), 0, 5, int),
        "adv": _number(request, "adv", int(defaults.get("adv", 0)), 0, 5, int),
        "react": _number(request, "react", int(defaults.get("react", 0)), 0, 5, int),
        "implant": _number(request, "implant", int(defaults.get("implant", 0)), 0, 4, int),
        "mat": "buy" if get("mat") == "buy" else "sell",
        "prod": "buy" if get("prod") == "buy" else "sell",
        "structure": str(structure.structure_id) if structure else "",
        "rig": rig_choice,
    }
    if params["implant"] not in dict(bonuses.IMPLANTS):
        params["implant"] = 0
    if "runs" in request.GET:  # Formular abgeschickt → Voreinstellungen merken
        request.session[SESSION_KEY] = {k: params[k] for k in DEFAULT_KEYS}

    # Boni zusammenstellen: Struktur + Rig, ohne Struktur die frei eingegebenen Werte
    if info:
        structure_me, structure_te, structure_cost = info["me"], info["te"], info["cost"]
    else:
        structure_me, structure_te, structure_cost = params["bonus"], params["tebonus"], 0.0
    rig_me = bonuses.combined_material_bonus(*[r.me for r in applied_rigs]) if applied_rigs else 0.0
    rig_te = bonuses.combined_material_bonus(*[r.te for r in applied_rigs]) if applied_rigs else 0.0
    time_factor = bonuses.time_multiplier(
        activity_name, te_pct=params["te"], structure_te=structure_te, rig_te=rig_te,
        industry=params["ind"], advanced_industry=params["adv"], reactions=params["react"],
        implant_pct=params["implant"],
    )
    result = calculate(
        activity,
        runs=params["runs"],
        me_pct=params["me"],
        bonus_pct=bonuses.combined_material_bonus(structure_me, rig_me),
        cost_index_pct=params["index"],
        facility_tax_pct=params["tax"],
        material_mode=params["mat"],
        product_mode=params["prod"],
        time_factor=time_factor,
        structure_cost_bonus_pct=structure_cost,
    )
    return render(
        request,
        "ether_industry/calculator.html",
        {
            "activity": activity,
            "is_manufacturing": is_manufacturing,
            "p": params,
            "r": result,
            "prices": _price_status(),
            "structures": structures,
            "info": info,
            "applied_rigs": applied_rigs,
            "auto_index": auto_index,
            "bonus_summary": {
                "structure_me": structure_me, "structure_te": structure_te, "structure_cost": structure_cost,
                "rig_me": rig_me, "rig_te": rig_te, "time_factor": time_factor,
            },
            "implants": bonuses.IMPLANTS,
            "skills_from_corptools": defaults.get("from_skills", False),
            "corp_blueprints": corp_blueprints(activity.blueprint.type_id) if is_manufacturing else [],
            "corptools": corptools_available(),
        },
    )


@login_required
@require_POST
def sync_structures(request):
    """Route /structures/sync/: Strukturen, Rigs und Kostenindizes neu einlesen (Recht manage_industry)."""
    if not request.user.has_perm("ether_industry.manage_industry"):
        raise PermissionDenied
    from .tasks import sync_structures_task

    try:
        sync_structures_task.delay()
        messages.info(request, "Strukturen werden im Hintergrund neu eingelesen – in einer Minute neu laden.")
    except Exception:  # Celery-Broker nicht erreichbar
        messages.warning(request, "Die Aufgabenwarteschlange ist gerade nicht erreichbar – bitte später erneut.")
    return redirect("ether_industry:index")

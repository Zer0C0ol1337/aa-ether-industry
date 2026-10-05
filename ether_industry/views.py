"""Views des Industrie-Rechners."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .calc import calculate
from .models import ActivityProduct, BlueprintActivity, ItemPrice

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
    """Route /: Produktsuche mit Autovervollständigung und klassischer Ergebnisliste."""
    query = request.GET.get("q", "").strip()
    results = _search_products(query, 50) if len(query) >= 2 else []
    return render(
        request,
        "ether_industry/index.html",
        {"q": query, "results": results, "prices": _price_status()},
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


@check_access
def calculator(request, activity_id):
    """Route /calc/<id>/: Kostenrechnung für eine Herstellung oder Reaction."""
    activity = get_object_or_404(
        BlueprintActivity.objects.select_related("blueprint__type"),
        pk=activity_id,
        activity__in=CALC_ACTIVITIES,
    )
    params = {
        "runs": _number(request, "runs", 1, 1, 100000, int),
        "me": _number(request, "me", 10 if activity.activity == BlueprintActivity.MANUFACTURING else 0, 0, 10, int),
        "bonus": _number(request, "bonus", 0.0, 0.0, 10.0),
        "index": _number(request, "index", 5.0, 0.0, 50.0),
        "tax": _number(request, "tax", 0.0, 0.0, 50.0),
        "mat": "buy" if request.GET.get("mat") == "buy" else "sell",
        "prod": "buy" if request.GET.get("prod") == "buy" else "sell",
    }
    result = calculate(
        activity,
        runs=params["runs"],
        me_pct=params["me"],
        bonus_pct=params["bonus"],
        cost_index_pct=params["index"],
        facility_tax_pct=params["tax"],
        material_mode=params["mat"],
        product_mode=params["prod"],
    )
    return render(
        request,
        "ether_industry/calculator.html",
        {
            "activity": activity,
            "is_manufacturing": activity.activity == BlueprintActivity.MANUFACTURING,
            "p": params,
            "r": result,
            "prices": _price_status(),
        },
    )

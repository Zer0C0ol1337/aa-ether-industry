"""Einbindung in Alliance Auth: Menüpunkt und URLs."""

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class IndustryMenuItem(MenuItemHook):
    """Menüpunkt „Industrie“ in der linken Navigation."""

    def __init__(self):
        """Legt Titel, Icon und Ziel-URL fest."""
        MenuItemHook.__init__(
            self,
            "Industrie",
            "fas fa-industry fa-fw",
            "ether_industry:index",
            navactive=["ether_industry:"],
        )

    def render(self, request):
        """Zeigt den Menüpunkt nur Nutzern mit basic_access."""
        if request.user.has_perm("ether_industry.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    """Registriert den Menüpunkt bei Alliance Auth."""
    return IndustryMenuItem()


@hooks.register("url_hook")
def register_urls():
    """Hängt die Plugin-URLs unter /industry/ ein."""
    return UrlHook(urls, "ether_industry", r"^industry/")

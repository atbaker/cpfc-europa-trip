"""Direct outbound links only. Never fetch arbitrary user/model-supplied URLs."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cpfc_trip.domain import Party

ALLOWED = {
    "www.olvallee.fr",
    "www.rhonexpress.fr",
    "www.google.com",
    "www.booking.com",
    "www.eurostar.com",
    "www.sncf-connect.com",
    "www.bahn.de",
    "int.bahn.de",
    "www.oebb.at",
    "shop.oebbtickets.at",
    "www.intercity.pl",
    "ebilet.intercity.pl",
    "www.omio.com",
    "www.thetrainline.com",
}


def safe_url(value: str) -> str | None:
    if len(value) > 16000:
        return None
    try:
        u = urlsplit(value)
        if u.scheme != "https" or u.hostname not in ALLOWED or u.username or u.password:
            return None
        if u.port not in (None, 443) or any(ord(c) < 32 for c in value):
            return None
        if u.hostname == "www.google.com" and not u.path.startswith("/travel/flights"):
            return None
        return value
    except ValueError:
        return None


def flight_url(value: str) -> str | None:
    if not safe_url(value) or urlsplit(value).hostname != "www.google.com":
        return None
    u = urlsplit(value)
    params = [
        (k, v)
        for k, v in parse_qsl(u.query, keep_blank_values=True)
        if k not in {"gl", "hl", "curr"}
    ]
    params += [("gl", "GB"), ("hl", "en-GB"), ("curr", "GBP")]
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(params), u.fragment))


def hotel_url(value: str, start: str, end: str, party: Party) -> str | None:
    u = urlsplit(value)
    if not safe_url(value) or u.hostname != "www.booking.com" or not u.path.startswith("/hotel/"):
        return None
    # Explicit occupancy replaces any stale parameters on the provider URL.
    params = {
        k: v
        for k, v in parse_qsl(u.query)
        if k not in {"checkin", "checkout", "group_adults", "group_children", "no_rooms", "age"}
    }
    params.update(
        checkin=start,
        checkout=end,
        group_adults=str(party.adults),
        group_children=str(len(party.child_ages)),
        no_rooms=str(party.rooms),
        selected_currency="GBP",
    )
    return urlunsplit(
        (
            u.scheme,
            u.netloc,
            u.path,
            urlencode(list(params.items()) + [("age", str(a)) for a in party.child_ages]),
            "",
        )
    )

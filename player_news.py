import feedparser
import requests

from urllib.parse import quote, urlparse
from datetime import datetime, timezone


# =========================================================
# FUENTES PERMITIDAS
# =========================================================

TRUSTED_SOURCES = {
    "atptour.com": "ATP Tour",
    "reuters.com": "Reuters",
    "bbc.com": "BBC Sport",
    "bbc.co.uk": "BBC Sport",
    "apnews.com": "Associated Press",
    "ap.org": "Associated Press",
}


# =========================================================
# PALABRAS DE RIESGO ALTO
# =========================================================

HIGH_RISK_KEYWORDS = [
    "injury",
    "injured",
    "withdraw",
    "withdrawal",
    "withdrew",
    "retire",
    "retired",
    "retires",
    "medical timeout",
    "medical time-out",
    "treatment",
    "wrist injury",
    "ankle injury",
    "knee injury",
    "shoulder injury",
    "back injury",
]


# =========================================================
# PALABRAS DE RIESGO MEDIO
# =========================================================

MEDIUM_RISK_KEYWORDS = [
    "fitness",
    "physical problem",
    "physical issue",
    "struggling",
    "pain",
    "discomfort",
    "cramp",
    "cramps",
    "fatigue",
    "tired",
    "illness",
    "sick",
]


# =========================================================
# PALABRAS DE RECUPERACIÓN
# =========================================================

RECOVERY_KEYWORDS = [
    "recovered",
    "recovery",
    "fit again",
    "back to fitness",
    "returns",
    "returned",
    "return to action",
    "ready to play",
    "fully fit",
    "without pain",
    "pain-free",
    "comeback",
]


# =========================================================
# COMPROBAR SI LA NOTICIA ES DEL JUGADOR
# =========================================================

def is_player_match(title, player_name):

    title_lower = title.lower()
    player_lower = player_name.lower()

    if player_lower in title_lower:
        return True

    player_parts = player_lower.split()

    if len(player_parts) >= 2:

        first_name = player_parts[0]
        last_name = player_parts[-1]

        if first_name in title_lower and last_name in title_lower:
            return True

        if last_name in title_lower:
            return True

    return False


# =========================================================
# IDENTIFICAR FUENTE POR URL
# =========================================================

def get_source_name(url):

    try:

        domain = urlparse(url).netloc.lower()
        domain = domain.replace("www.", "")

        for allowed_domain, source_name in TRUSTED_SOURCES.items():

            if (
                domain == allowed_domain
                or domain.endswith("." + allowed_domain)
            ):

                return source_name

    except Exception:

        pass

    return None


# =========================================================
# IDENTIFICAR FUENTE POR NOMBRE
# =========================================================

def get_source_from_text(source_text):

    if not source_text:
        return None

    source_lower = source_text.lower()

    trusted_names = {
        "atp tour": "ATP Tour",
        "reuters": "Reuters",
        "bbc sport": "BBC Sport",
        "bbc": "BBC Sport",
        "associated press": "Associated Press",
        "ap news": "Associated Press",
    }

    for trusted_text, trusted_source in trusted_names.items():

        if trusted_text in source_lower:
            return trusted_source

    return None


# =========================================================
# BUSCAR NOTICIAS DEL JUGADOR
# =========================================================

def search_player_news(player_name, max_results=15):

    queries = [
        f'"{player_name}" tennis injury',
        f'"{player_name}" tennis retired',
        f'"{player_name}" tennis withdrawal',
        f'"{player_name}" tennis medical timeout',
        f'"{player_name}" tennis fitness',
    ]

    articles = []

    seen_urls = set()
    seen_titles = set()


    for query in queries:

        url = (
            "https://news.google.com/rss/search?q="
            + quote(query)
            + "&hl=en&gl=US&ceid=US:en"
        )

        try:

            response = requests.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/120 Safari/537.36"
                    )
                },
                timeout=15
            )

            print(
                "GOOGLE NEWS STATUS:",
                response.status_code
            )

            print(
                "BUSCANDO:",
                query
            )

            feed = feedparser.parse(
                response.content
            )

            print(
                "NOTICIAS ENCONTRADAS:",
                len(feed.entries)
            )


        except Exception as error:

            print(
                "ERROR BUSCANDO NOTICIAS:",
                error
            )

            continue


        for entry in feed.entries:

            title = entry.get(
                "title",
                ""
            ).strip()

            link = entry.get(
                "link",
                ""
            ).strip()

            published = entry.get(
                "published",
                ""
            ).strip()


            if not title or not link:

                continue


            # -------------------------------------------------
            # COMPROBAR QUE LA NOTICIA ES DEL JUGADOR
            # -------------------------------------------------

            if not is_player_match(
                title,
                player_name
            ):

                continue


            # -------------------------------------------------
            # COMPROBAR FUENTE
            # -------------------------------------------------

            source_info = entry.get(
                "source",
                {}
            )

            source_name = None


            if source_info:

                source_url = source_info.get(
                    "href",
                    ""
                )

                source_text = source_info.get(
                    "title",
                    ""
                ).strip()


                source_name = get_source_name(
                    source_url
                )


                if source_name is None:

                    source_name = get_source_from_text(
                        source_text
                    )


            # -------------------------------------------------
            # SOLO FUENTES FIABLES
            # -------------------------------------------------

            if source_name is None:

                continue


            # -------------------------------------------------
            # EVITAR DUPLICADOS
            # -------------------------------------------------

            title_key = title.lower()


            if link in seen_urls:

                continue


            if title_key in seen_titles:

                continue


            seen_urls.add(link)
            seen_titles.add(title_key)


            articles.append({
                "title": title,
                "link": link,
                "published": published,
                "source": source_name
            })


    return articles[:max_results]


# =========================================================
# ANALIZAR ESTADO FÍSICO
# =========================================================

def analyse_physical_status(player_name):

    articles = search_player_news(player_name)

    now = datetime.now(timezone.utc)

    high_alerts = []
    medium_alerts = []
    recovery_alerts = []

    # Aquí guardaremos solo el riesgo más importante
    # de cada problema físico
    injury_events = {}

    player_last_name = player_name.lower().split()[-1]


    # =====================================================
    # OBTENER ANTIGÜEDAD DE LA NOTICIA
    # =====================================================

    def get_age_days(article):

        try:

            published = article.get("published", "")

            if not published:

                return 999

            parsed = datetime.strptime(
                published[:25],
                "%a, %d %b %Y %H:%M:%S"
            )

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

            return max(
                0,
                (now - parsed).days
            )

        except Exception:

            return 999


    # =====================================================
    # PESO SEGÚN ANTIGÜEDAD
    # =====================================================

    def get_high_points(days):

        if days <= 7:
            return 35

        elif days <= 30:
            return 25

        elif days <= 60:
            return 15

        elif days <= 120:
            return 8

        else:
            return 3


    def get_medium_points(days):

        if days <= 7:
            return 15

        elif days <= 30:
            return 10

        elif days <= 60:
            return 6

        elif days <= 120:
            return 3

        else:
            return 1


    # =====================================================
    # DETECTAR TIPO DE EVENTO
    # =====================================================

    def get_injury_type(title):

        injury_types = {

            "wrist": "wrist",
            "knee": "knee",
            "ankle": "ankle",
            "shoulder": "shoulder",
            "back": "back",
            "elbow": "elbow",
            "hip": "hip",

        }

        for keyword, injury_type in injury_types.items():

            if keyword in title:

                return injury_type


        # Si habla de retirada pero no indica lesión
        if "withdraw" in title:

            return "withdrawal"

        if "retire" in title:

            return "retirement"

        if "medical timeout" in title:

            return "medical"

        if "injury" in title:

            return "injury"

        return None


    # =====================================================
    # COMPROBAR SI EL JUGADOR ES EL QUE SUFRE EL PROBLEMA
    # =====================================================

    def is_player_problem(title):

        # Casos muy claros donde OTRO jugador se retira
        other_player_patterns = [

            "sinner retires",
            "djokovic retires",
            "zverev retires",
            "nadal retires",
            "federer retires",

        ]

        for pattern in other_player_patterns:

            if pattern in title and player_last_name not in pattern:

                return False


        # El apellido del jugador debe aparecer
        if player_last_name not in title:

            return False


        return True


    # =====================================================
    # ANALIZAR NOTICIAS
    # =====================================================

    for article in articles:

        title = article["title"].lower()

        days_old = get_age_days(article)

        article["days_old"] = days_old


        # -----------------------------------------------
        # EL TITULAR DEBE REFERIRSE AL JUGADOR
        # -----------------------------------------------

        if player_last_name not in title:

            continue


        # -----------------------------------------------
        # CASOS QUE NO DEBEN CONTAR COMO RIESGO
        # -----------------------------------------------

        if (
            "nothing serious" in title
            or "just for precaution" in title
        ):

            article["risk"] = "none"
            article["points"] = 0

            continue


        # -----------------------------------------------
        # DETECTAR RECUPERACIÓN
        # -----------------------------------------------

        recovery_match = any(
            keyword in title
            for keyword in RECOVERY_KEYWORDS
        )

        if (
            "return" in title
            or "returns" in title
            or "returned" in title
            or "back from injury" in title
        ):

            recovery_match = True


        # -----------------------------------------------
        # DETECTAR RIESGO
        # -----------------------------------------------

        high_match = any(
            keyword in title
            for keyword in HIGH_RISK_KEYWORDS
        )

        medium_match = any(
            keyword in title
            for keyword in MEDIUM_RISK_KEYWORDS
        )


        # -----------------------------------------------
        # IDENTIFICAR EL EVENTO
        # -----------------------------------------------

        injury_type = get_injury_type(title)


        # -----------------------------------------------
        # RECUPERACIÓN
        # -----------------------------------------------

        if recovery_match:

            article["risk"] = "recovery"
            article["points"] = 0

            recovery_alerts.append(article)

            continue


        # -----------------------------------------------
        # RIESGO ALTO
        # -----------------------------------------------

        if high_match:

            points = get_high_points(days_old)

            article["risk"] = "high"
            article["points"] = points

            high_alerts.append(article)


        # -----------------------------------------------
        # RIESGO MEDIO
        # -----------------------------------------------

        elif medium_match:

            points = get_medium_points(days_old)

            article["risk"] = "medium"
            article["points"] = points

            medium_alerts.append(article)

        else:

            article["risk"] = "none"
            article["points"] = 0

            continue


        # -----------------------------------------------
        # DESCARTAR PROBLEMAS DE OTROS JUGADORES
        # -----------------------------------------------

        if not is_player_problem(title):

            article["points"] = 0

            continue


        # -----------------------------------------------
        # AGRUPAR EL MISMO PROBLEMA
        # -----------------------------------------------

        if injury_type is None:

            injury_type = "general"


        if injury_type not in injury_events:

            injury_events[injury_type] = {
                "points": article["points"],
                "article": article
            }

        else:

            # Solo guardamos la noticia con mayor riesgo
            if article["points"] > injury_events[injury_type]["points"]:

                injury_events[injury_type] = {
                    "points": article["points"],
                    "article": article
                }


    # =====================================================
    # CALCULAR PUNTUACIÓN FINAL
    # =====================================================

    score = sum(
        event["points"]
        for event in injury_events.values()
    )


    # =====================================================
    # RECUPERACIÓN RECIENTE
    # =====================================================

    recent_recovery = any(
        article["days_old"] <= 90
        for article in recovery_alerts
    )


    if recent_recovery:

        score -= 15


    # =====================================================
    # LÍMITES
    # =====================================================

    score = max(
        0,
        min(score, 100)
    )


    # =====================================================
    # CLASIFICACIÓN FINAL
    # =====================================================

    if score >= 70:

        status = "🔴 RIESGO ALTO"
        label = "alto"

    elif score >= 40:

        status = "🟠 RIESGO MEDIO-ALTO"
        label = "medio-alto"

    elif score >= 20:

        status = "🟡 RIESGO MODERADO"
        label = "moderado"

    else:

        status = "🟢 RIESGO BAJO"
        label = "bajo"


    # =====================================================
    # RESULTADO
    # =====================================================

    return {
        "player": player_name,
        "score": score,
        "status": status,
        "label": label,
        "high_alerts": high_alerts,
        "medium_alerts": medium_alerts,
        "recovery_alerts": recovery_alerts,
        "articles": articles
    }
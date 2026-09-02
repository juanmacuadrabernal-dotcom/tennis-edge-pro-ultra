import requests

from api_config import LIVE_TENNIS_API_KEY


BASE_URL = "https://api.livetennisapi.com/api/public/v1"


def get_upcoming_matches():

    url = f"{BASE_URL}/fixtures"

    headers = {
        "X-API-Key": LIVE_TENNIS_API_KEY
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:

            print(
                f"❌ Error API: HTTP {response.status_code}"
            )

            print(
                response.text
            )

            return []


        data = response.json()

        matches = data.get(
            "data",
            []
        )


        if not matches:

            return []


        upcoming = []


        for match in matches:

            player1 = match.get(
                "player1_name"
            )

            player2 = match.get(
                "player2_name"
            )

            tour = match.get(
                "tour",
                ""
            ).lower()


            # SOLO ATP Y CHALLENGER
            if tour not in [
                "atp",
                "challenger"
            ]:
                continue


            if not player1 or not player2:
                continue


            upcoming.append({

                "id": match.get(
                    "id"
                ),

                "player1": player1,

                "player2": player2,

                "tournament": match.get(
                    "tournament",
                    "Desconocido"
                ),

                "surface": match.get(
                    "surface",
                    "Desconocida"
                ),

                "tour": tour,

                "round": match.get(
                    "round",
                    "Desconocida"
                ),

                "event_date": match.get(
                    "event_date"
                ),

                "start_time": match.get(
                    "start_time"
                ),

                "status": match.get(
                    "status"
                )

            })


        return upcoming


    except requests.exceptions.RequestException as error:

        print(
            f"❌ Error de conexión con la API: {error}"
        )

        return []


    except Exception as error:

        print(
            f"❌ Error procesando los próximos partidos: {error}"
        )

        return []


def print_upcoming_matches():

    print()

    print("===================================")
    print("PRÓXIMOS PARTIDOS")
    print("ATP + CHALLENGER")
    print("===================================")


    matches = get_upcoming_matches()


    if not matches:

        print()
        print(
            "No se encontraron próximos partidos ATP o Challenger."
        )

        return


    atp_matches = [
        match
        for match in matches
        if match["tour"] == "atp"
    ]


    challenger_matches = [
        match
        for match in matches
        if match["tour"] == "challenger"
    ]


    print()

    print(
        f"🎾 PARTIDOS COMPATIBLES: {len(matches)}"
    )


    # ===================================
    # ATP
    # ===================================

    if atp_matches:

        print()
        print("===================================")
        print("🎾 ATP")
        print("===================================")

        print()


        for match in atp_matches:

            print(
                f"{match['player1']} "
                f"vs "
                f"{match['player2']}"
            )

            print(
                f"🏆 {match['tournament']}"
            )

            print(
                f"🏟️ {match['surface']}"
            )

            print(
                f"📅 {match['event_date']}"
            )

            print(
                f"⏰ {match['start_time']}"
            )

            print()


    # ===================================
    # CHALLENGER
    # ===================================

    if challenger_matches:

        print()
        print("===================================")
        print("🎾 CHALLENGER")
        print("===================================")

        print()


        for match in challenger_matches:

            print(
                f"{match['player1']} "
                f"vs "
                f"{match['player2']}"
            )

            print(
                f"🏆 {match['tournament']}"
            )

            print(
                f"🏟️ {match['surface']}"
            )

            print(
                f"📅 {match['event_date']}"
            )

            print(
                f"⏰ {match['start_time']}"
            )

            print()


if __name__ == "__main__":

    print_upcoming_matches()
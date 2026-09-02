import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher


def normalizar_nombre(nombre):
    if not nombre:
        return ""

    texto = str(nombre).strip().lower()

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    texto = " ".join(texto.split())

    return texto


def _tokens(nombre):
    return normalizar_nombre(nombre).split()


def obtener_jugadores(df):
    nombres = []

    if "winner_name" in df.columns:
        nombres.extend(
            df["winner_name"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )

    if "loser_name" in df.columns:
        nombres.extend(
            df["loser_name"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )

    nombres = [nombre for nombre in nombres if nombre]

    frecuencias = Counter(nombres)

    # Unificamos variantes que solo cambian mayúsculas/minúsculas,
    # por ejemplo "Alex De Minaur" y "Alex de Minaur".
    por_normalizado = {}

    for nombre in nombres:
        normalizado = normalizar_nombre(nombre)

        if not normalizado:
            continue

        actual = por_normalizado.get(normalizado)

        if actual is None:
            por_normalizado[normalizado] = nombre
        elif frecuencias[nombre] > frecuencias[actual]:
            por_normalizado[normalizado] = nombre

    return sorted(por_normalizado.values())


def _coinciden_iniciales(iniciales_api, tokens_db, tokens_apellido):
    if not iniciales_api:
        return 0

    candidatos_nombre = []

    apellido_restante = list(tokens_apellido)

    for token in tokens_db:
        if token in apellido_restante:
            apellido_restante.remove(token)
        else:
            candidatos_nombre.append(token)

    if not candidatos_nombre:
        candidatos_nombre = tokens_db

    usadas = set()
    coincidencias = 0

    for inicial in iniciales_api:
        encontrada = False

        for indice, token in enumerate(candidatos_nombre):
            if indice in usadas:
                continue

            if token.startswith(inicial):
                usadas.add(indice)
                coincidencias += 1
                encontrada = True
                break

        if not encontrada:
            break

    return coincidencias


def _puntuacion_candidato(nombre_api, jugador_db):
    api_tokens = _tokens(nombre_api)
    db_tokens = _tokens(jugador_db)

    if not api_tokens or not db_tokens:
        return -9999

    iniciales_api = []
    tokens_apellido = []

    for token in api_tokens:
        if len(token) == 1 and not tokens_apellido:
            iniciales_api.append(token)
        else:
            tokens_apellido.append(token)

    if not tokens_apellido:
        return -9999

    # Todas las partes no abreviadas del nombre de la API deben
    # aparecer en el nombre de la base de datos.
    for token in tokens_apellido:
        if token not in db_tokens:
            return -9999

    score = 100.0

    # Premio si el apellido compuesto aparece en el mismo orden.
    posiciones = []
    inicio = 0

    for token in tokens_apellido:
        try:
            posicion = db_tokens.index(token, inicio)
        except ValueError:
            return -9999

        posiciones.append(posicion)
        inicio = posicion + 1

    if posiciones == sorted(posiciones):
        score += 40.0

    # Premio extra cuando la última parte también coincide con
    # el final del nombre de la BD.
    if db_tokens[-1] == tokens_apellido[-1]:
        score += 30.0

    coincidencias_iniciales = _coinciden_iniciales(
        iniciales_api,
        db_tokens,
        tokens_apellido
    )

    if iniciales_api:
        if coincidencias_iniciales != len(iniciales_api):
            return -9999

        score += coincidencias_iniciales * 80.0

    # Similaridad general solo para desempatar.
    score += SequenceMatcher(
        None,
        normalizar_nombre(nombre_api),
        normalizar_nombre(jugador_db)
    ).ratio() * 10.0

    return score


def resolver_jugador(nombre_api, jugadores):
    if not nombre_api:
        return None

    nombre_api_normalizado = normalizar_nombre(nombre_api)

    if not nombre_api_normalizado:
        return None

    # Evitar duplicados equivalentes por mayúsculas/minúsculas.
    jugadores_unicos = {}

    for jugador in jugadores:
        normalizado = normalizar_nombre(jugador)

        if normalizado and normalizado not in jugadores_unicos:
            jugadores_unicos[normalizado] = jugador

    # 1. Coincidencia exacta.
    if nombre_api_normalizado in jugadores_unicos:
        return jugadores_unicos[nombre_api_normalizado]

    # 2. Puntuar candidatos.
    puntuados = []

    for jugador in jugadores_unicos.values():
        score = _puntuacion_candidato(
            nombre_api,
            jugador
        )

        if score > -9000:
            puntuados.append((score, jugador))

    if not puntuados:
        return None

    puntuados.sort(
        key=lambda item: item[0],
        reverse=True
    )

    mejor_score, mejor_jugador = puntuados[0]

    if mejor_score < 180:
        return None

    # Si quedan dos personas realmente indistinguibles,
    # no inventamos una resolución.
    if len(puntuados) >= 2:
        segundo_score = puntuados[1][0]

        if abs(mejor_score - segundo_score) < 3:
            return None

    return mejor_jugador


def resolver_partido(jugador_a, jugador_b, df):
    jugadores = obtener_jugadores(df)

    jugador_a_resuelto = resolver_jugador(
        jugador_a,
        jugadores
    )

    jugador_b_resuelto = resolver_jugador(
        jugador_b,
        jugadores
    )

    return {
        "jugador_a_api": jugador_a,
        "jugador_b_api": jugador_b,
        "jugador_a": jugador_a_resuelto,
        "jugador_b": jugador_b_resuelto,
        "ok": (
            jugador_a_resuelto is not None
            and jugador_b_resuelto is not None
        )
    }

"""Carregamento e validação de riffs externos em JSON."""

import json
from pathlib import Path

from .config import RIFFS


# ----------------------------------------------------------------------------
# BIBLIOTECA EXTERNA DE MÚSICAS (JSON)
# ----------------------------------------------------------------------------
PASTA_RIFFS = Path(__file__).resolve().parent.parent / "riffs"

# Cordas em JSON: E = Mi grave, A, D, G, B, e = Mi aguda.
# Também aceitamos índices numéricos 0..5 para facilitar a geração automática.
CORDAS_JSON = {
    "E": 0, "E grave": 0, "mi grave": 0, "mi_grave": 0,
    "A": 1, "Lá": 1, "La": 1,
    "D": 2, "Ré": 2, "Re": 2,
    "G": 3, "Sol": 3,
    "B": 4, "Si": 4,
    "e": 5, "E aguda": 5, "Mi aguda": 5, "mi aguda": 5, "e aguda": 5,
}


def _normalizar_evento_json(evento, indice, arquivo):
    """Converte um evento JSON para (índice_da_corda, traste, pulso)."""
    if not isinstance(evento, dict):
        raise ValueError(f"evento {indice + 1}: cada nota precisa ser um objeto JSON")
    corda_bruta = evento.get("corda")
    if isinstance(corda_bruta, int):
        corda = corda_bruta
    elif isinstance(corda_bruta, str):
        corda = CORDAS_JSON.get(corda_bruta.strip(), CORDAS_JSON.get(corda_bruta.strip().lower()))
        if corda is None:
            raise ValueError(
                f"evento {indice + 1}: corda inválida {corda_bruta!r}; use E, A, D, G, B ou e"
            )
    else:
        raise ValueError(f"evento {indice + 1}: informe 'corda' como nome ou número de 0 a 5")

    try:
        traste = int(evento["traste"])
        pulso = float(evento.get("pulso", indice))
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"evento {indice + 1}: informe 'traste' inteiro e 'pulso' numérico") from None

    if not 0 <= corda <= 5:
        raise ValueError(f"evento {indice + 1}: corda numérica deve estar entre 0 e 5")
    if not 0 <= traste <= 24:
        raise ValueError(f"evento {indice + 1}: traste deve estar entre 0 e 24")
    if pulso < 0:
        raise ValueError(f"evento {indice + 1}: pulso não pode ser negativo")
    return corda, traste, pulso


def carregar_biblioteca_json():
    """Carrega automaticamente todos os arquivos .json da pasta riffs/."""
    PASTA_RIFFS.mkdir(parents=True, exist_ok=True)
    carregadas = []
    for arquivo in sorted(PASTA_RIFFS.glob("*.json")):
        try:
            with arquivo.open("r", encoding="utf-8-sig") as f:
                dados = json.load(f)
            if not isinstance(dados, dict):
                raise ValueError("o arquivo precisa conter um objeto JSON")
            chave = str(dados.get("id") or arquivo.stem).strip()
            nome = str(dados.get("nome") or arquivo.stem).strip()
            descricao = str(dados.get("descricao") or "Importado de JSON").strip()
            bpm = int(dados.get("bpm", 100))
            eventos_json = dados.get("eventos")
            if not chave or not nome:
                raise ValueError("informe 'id' e 'nome'")
            if not 30 <= bpm <= 300:
                raise ValueError("'bpm' deve estar entre 30 e 300")
            if not isinstance(eventos_json, list) or not eventos_json:
                raise ValueError("'eventos' precisa ser uma lista com pelo menos uma nota")
            eventos = [
                _normalizar_evento_json(evento, i, arquivo)
                for i, evento in enumerate(eventos_json)
            ]
            if chave in RIFFS:
                raise ValueError(f"o id {chave!r} já existe na biblioteca interna")
            RIFFS[chave] = {
                "nome": nome,
                "bpm": bpm,
                "eventos": eventos,
                "descricao": descricao,
                "arquivo": str(arquivo),
            }
            carregadas.append(nome)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as erro:
            print(f"[Biblioteca] Não foi possível carregar {arquivo.name}: {erro}")
    return carregadas

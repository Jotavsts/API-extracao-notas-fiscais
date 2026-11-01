"""Categoriza os itens da nota por palavras-chave, usando tokenização e stemming do NLTK."""

import unicodedata
from dataclasses import replace
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional

from nltk.stem.snowball import SnowballStemmer
from nltk.tokenize import RegexpTokenizer

from .modelos import Item

CATEGORIA_PADRAO = "outros"

# Ordem importa: em caso de empate, vence a categoria que aparece primeiro.
PALAVRAS_POR_CATEGORIA: Dict[str, List[str]] = {
    "limpeza": [
        "detergente", "sabao", "desinfetante", "amaciante", "alvejante",
        "esponja", "sanitaria", "multiuso", "lustra",
    ],
    "higiene": [
        "shampoo", "xampu", "condicionador", "sabonete", "dental", "escova",
        "higienico", "desodorante", "absorvente", "fralda",
    ],
    "farmacia": [
        "dipirona", "paracetamol", "vitamina", "remedio", "comprimido",
        "xarope", "curativo", "protetor", "ibuprofeno",
    ],
    "alimentos": [
        # "pao/paes" e "ovo/ovos" aparecem nas duas formas: o stemmer não une palavras curtas irregulares.
        "leite", "arroz", "feijao", "carne", "frango", "pao", "paes", "queijo",
        "presunto", "macarrao", "acucar", "sal", "oleo", "farinha", "ovo", "ovos",
        "biscoito", "cafe", "manteiga", "iogurte", "banana", "maca",
        "tomate", "batata", "cebola",
    ],
    "bebidas": [
        "refrigerante", "suco", "agua", "cerveja", "vinho", "energetico", "cha",
    ],
    "combustivel": ["gasolina", "etanol", "diesel", "alcool"],
}

# Termos de unidade e ligação que não ajudam a identificar a categoria.
PALAVRAS_IGNORADAS: FrozenSet[str] = frozenset(
    {"un", "kg", "g", "l", "ml", "pc", "cx", "de", "da", "do", "em", "com", "para", "e"}
)

# Função opcional que tenta classificar o que as regras não resolveram (por exemplo, um LLM).
Refinador = Callable[[str], Optional[str]]

_tokenizador = RegexpTokenizer(r"[a-z]+")
_stemmer = SnowballStemmer("portuguese")


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acentos."""
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def _radicais(texto: str) -> List[str]:
    tokens = _tokenizador.tokenize(_normalizar(texto))
    return [_stemmer.stem(t) for t in tokens if t not in PALAVRAS_IGNORADAS]


_INDICE: Dict[str, FrozenSet[str]] = {
    categoria: frozenset(_stemmer.stem(p) for p in palavras)
    for categoria, palavras in PALAVRAS_POR_CATEGORIA.items()
}


def categorizar_descricao(descricao: str) -> str:
    """Devolve a categoria com mais palavras-chave na descrição, ou 'outros'."""
    radicais = set(_radicais(descricao))
    melhor, acertos_melhor = CATEGORIA_PADRAO, 0
    for categoria, palavras in _INDICE.items():
        acertos = len(radicais & palavras)
        if acertos > acertos_melhor:
            melhor, acertos_melhor = categoria, acertos
    return melhor


def categorizar_itens(itens: Iterable[Item], refinador: Optional[Refinador] = None) -> List[Item]:
    """Devolve novos itens com a categoria preenchida, sem alterar os originais.

    Se um `refinador` for informado, ele só é chamado para os itens que as regras
    deixaram em 'outros'. Qualquer resposta vazia mantém a categoria padrão.
    """
    resultado: List[Item] = []
    for item in itens:
        categoria = categorizar_descricao(item.descricao)
        if categoria == CATEGORIA_PADRAO and refinador:
            categoria = refinador(item.descricao) or CATEGORIA_PADRAO
        resultado.append(replace(item, categoria=categoria))
    return resultado

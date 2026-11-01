from decimal import Decimal

import pytest

from nf_extractor.categorizador import (
    CATEGORIA_PADRAO,
    categorizar_descricao,
    categorizar_itens,
)
from nf_extractor.modelos import Item


def _item(descricao: str) -> Item:
    return Item(descricao, Decimal("1"), Decimal("1.00"), Decimal("1.00"))


@pytest.mark.parametrize(
    "descricao, esperada",
    [
        ("LEITE INTEGRAL 1L", "alimentos"),
        ("ARROZ BRANCO 5KG", "alimentos"),
        ("DETERGENTE NEUTRO 500ML", "limpeza"),
        ("SABAO EM PO 1KG", "limpeza"),
        ("SABONETE DOVE 90G", "higiene"),
        ("PAPEL HIGIENICO 12UN", "higiene"),
        ("DIPIRONA 500MG 10 COMPRIMIDOS", "farmacia"),
        ("REFRIGERANTE COLA 2L", "bebidas"),
        ("GASOLINA COMUM", "combustivel"),
    ],
)
def test_categoriza_por_palavra_chave(descricao, esperada):
    assert categorizar_descricao(descricao) == esperada


def test_ignora_acentos_e_maiusculas():
    assert categorizar_descricao("Pão Francês") == "alimentos"
    assert categorizar_descricao("ÁGUA MINERAL 500ML") == "bebidas"


@pytest.mark.parametrize(
    "singular, plural",
    [("BISCOITO RECHEADO", "BISCOITOS RECHEADOS"), ("TOMATE", "TOMATES"), ("OVO BRANCO", "OVOS BRANCOS"), ("PAO FRANCES", "PAES DE FORMA")],
)
def test_reconhece_singular_e_plural(singular, plural):
    assert categorizar_descricao(singular) == categorizar_descricao(plural) == "alimentos"


def test_agua_sanitaria_e_limpeza_e_nao_bebida():
    assert categorizar_descricao("AGUA SANITARIA 1L") == "limpeza"


def test_descricao_desconhecida_vira_outros():
    assert categorizar_descricao("PARAFUSO 3MM") == CATEGORIA_PADRAO


def test_categorizar_itens_nao_altera_os_originais():
    originais = [_item("LEITE INTEGRAL 1L")]
    resultado = categorizar_itens(originais)
    assert resultado[0].categoria == "alimentos"
    assert originais[0].categoria is None


def test_refinador_so_e_chamado_para_itens_em_outros():
    chamadas = []

    def refinador(descricao):
        chamadas.append(descricao)
        return "ferragens"

    itens = categorizar_itens([_item("LEITE INTEGRAL 1L"), _item("PARAFUSO 3MM")], refinador)
    assert [i.categoria for i in itens] == ["alimentos", "ferragens"]
    assert chamadas == ["PARAFUSO 3MM"]


def test_refinador_sem_resposta_mantem_a_categoria_padrao():
    itens = categorizar_itens([_item("PARAFUSO 3MM")], lambda _: None)
    assert itens[0].categoria == CATEGORIA_PADRAO

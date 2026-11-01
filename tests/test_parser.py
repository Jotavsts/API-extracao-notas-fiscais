from decimal import Decimal

import pytest

from nf_extractor.modelos import formatar_cnpj, validar_cnpj
from nf_extractor.parser import (
    converter_valor,
    extrair_chave_acesso,
    extrair_cnpj,
    extrair_data,
    extrair_itens,
    extrair_nota,
    extrair_valor_total,
)


class TestCnpj:
    def test_valida_cnpj_com_e_sem_pontuacao(self):
        assert validar_cnpj("11.222.333/0001-81")
        assert validar_cnpj("11222333000181")

    @pytest.mark.parametrize("cnpj", ["11.222.333/0001-82", "00000000000000", "123", ""])
    def test_rejeita_cnpj_invalido(self, cnpj):
        assert not validar_cnpj(cnpj)

    def test_formata_cnpj(self):
        assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_prefere_cnpj_valido_quando_ha_mais_de_um(self):
        linhas = ["CNPJ 12.345.678/0001-00", "CNPJ 11.222.333/0001-81"]
        assert extrair_cnpj(linhas) == "11.222.333/0001-81"

    def test_devolve_o_primeiro_quando_nenhum_e_valido(self):
        assert extrair_cnpj(["CNPJ 12.345.678/0001-00"]) == "12.345.678/0001-00"

    def test_sem_cnpj_devolve_none(self):
        assert extrair_cnpj(["texto qualquer"]) is None


class TestCamposSimples:
    def test_converte_valor_brasileiro(self):
        assert converter_valor("1.234,56") == Decimal("1234.56")
        assert converter_valor("9,00") == Decimal("9.00")

    def test_extrai_chave_de_acesso_sem_espacos(self, linhas_nota_exemplo):
        chave = extrair_chave_acesso(linhas_nota_exemplo)
        assert chave == "35261011222333000181650010000001231000001234"
        assert len(chave) == 44

    def test_extrai_data_em_formato_iso(self, linhas_nota_exemplo):
        assert extrair_data(linhas_nota_exemplo) == "2026-10-28"

    def test_ignora_data_inexistente(self):
        assert extrair_data(["Emissao: 31/02/2026"]) is None

    def test_extrai_valor_total(self, linhas_nota_exemplo):
        assert extrair_valor_total(linhas_nota_exemplo) == Decimal("58.67")

    def test_usa_o_ultimo_total_do_texto(self):
        linhas = ["Total parcial 10,00", "VALOR TOTAL R$ 25,50"]
        assert extrair_valor_total(linhas) == Decimal("25.50")


class TestItens:
    def test_extrai_todos_os_itens(self, linhas_nota_exemplo):
        itens = extrair_itens(linhas_nota_exemplo)
        assert [i.descricao for i in itens] == [
            "LEITE INTEGRAL 1L",
            "ARROZ BRANCO 5KG",
            "DETERGENTE NEUTRO 500ML",
            "SABAO EM PO 1KG",
        ]

    def test_le_quantidade_e_valores(self, linhas_nota_exemplo):
        leite = extrair_itens(linhas_nota_exemplo)[0]
        assert leite.quantidade == Decimal("2")
        assert leite.valor_unitario == Decimal("4.50")
        assert leite.valor_total == Decimal("9.00")

    def test_aceita_quantidade_fracionada(self):
        itens = extrair_itens(["QUEIJO MUSSARELA 0,350 KG x 42,90 15,02"])
        assert itens[0].quantidade == Decimal("0.350")

    def test_ignora_linhas_que_nao_sao_item(self):
        assert extrair_itens(["CUPOM FISCAL", "Valor total R$ 10,00"]) == []


class TestNotaCompleta:
    def test_monta_a_nota_com_todos_os_campos(self, linhas_nota_exemplo):
        nota = extrair_nota(linhas_nota_exemplo)
        assert nota.cnpj == "11.222.333/0001-81"
        assert nota.cnpj_valido is True
        assert nota.data_emissao == "2026-10-28"
        assert nota.valor_total == Decimal("58.67")
        assert len(nota.itens) == 4

    def test_a_soma_dos_itens_bate_com_o_total(self, linhas_nota_exemplo):
        nota = extrair_nota(linhas_nota_exemplo)
        assert sum(i.valor_total for i in nota.itens) == nota.valor_total

    def test_texto_vazio_nao_quebra(self):
        nota = extrair_nota([])
        assert nota.cnpj is None and nota.itens == []

    def test_converte_para_dict_serializavel(self, linhas_nota_exemplo):
        import json

        dados = extrair_nota(linhas_nota_exemplo).para_dict()
        assert json.loads(json.dumps(dados))["valor_total"] == 58.67

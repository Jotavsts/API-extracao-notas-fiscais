"""Extrai campos e itens de uma nota fiscal a partir das linhas de texto transcritas."""

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional

from .modelos import Item, NotaFiscal, validar_cnpj

logger = logging.getLogger(__name__)

# Valores no padrão brasileiro: 1.234,56
_VALOR = r"\d{1,3}(?:\.\d{3})*,\d{2}"

PADRAO_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
PADRAO_CHAVE = re.compile(r"\b(?:\d{4}\s?){10}\d{4}\b")
PADRAO_DATA = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
PADRAO_TOTAL = re.compile(rf"(?i)\b(?:valor\s+)?total(?:\s+(?:da\s+nota|a\s+pagar))?\b[^\d\n]*({_VALOR})")
PADRAO_ITEM = re.compile(
    rf"""^
    (?:\d{{1,3}}\s+)?                    # número do item (opcional)
    (?:\d{{8,14}}\s+)?                   # código de barras (opcional)
    (?P<descricao>.+?)\s+
    (?P<quantidade>\d+(?:,\d{{1,3}})?)\s*
    (?:UN|KG|L|PC|CX|G|ML)?\s*[xX]\s*    # unidade e sinal de multiplicação
    (?P<unitario>{_VALOR})\s+
    (?P<total>{_VALOR})$""",
    re.VERBOSE | re.IGNORECASE,
)


def converter_valor(texto: str) -> Decimal:
    """Converte '1.234,56' em Decimal('1234.56'). Levanta ValueError se for inválido."""
    try:
        return Decimal(texto.replace(".", "").replace(",", "."))
    except InvalidOperation as erro:
        raise ValueError(f"Valor inválido: {texto!r}") from erro


def extrair_cnpj(linhas: Iterable[str]) -> Optional[str]:
    """Devolve o primeiro CNPJ válido do texto; se nenhum for válido, o primeiro encontrado."""
    encontrados = [m.group() for linha in linhas for m in PADRAO_CNPJ.finditer(linha)]
    for cnpj in encontrados:
        if validar_cnpj(cnpj):
            return cnpj
    return encontrados[0] if encontrados else None


def extrair_chave_acesso(linhas: Iterable[str]) -> Optional[str]:
    """Devolve a chave de acesso de 44 dígitos, sem espaços."""
    for linha in linhas:
        achou = PADRAO_CHAVE.search(linha)
        if achou:
            return re.sub(r"\s", "", achou.group())
    return None


def extrair_data(linhas: Iterable[str]) -> Optional[str]:
    """Devolve a primeira data válida no formato ISO (AAAA-MM-DD)."""
    for linha in linhas:
        for dia, mes, ano in PADRAO_DATA.findall(linha):
            try:
                return datetime(int(ano), int(mes), int(dia)).date().isoformat()
            except ValueError:
                logger.debug("Data ignorada por ser inválida: %s/%s/%s", dia, mes, ano)
    return None


def extrair_valor_total(linhas: Iterable[str]) -> Optional[Decimal]:
    """Devolve o último valor marcado como total (o total geral costuma vir por último)."""
    total = None
    for linha in linhas:
        achou = PADRAO_TOTAL.search(linha)
        if achou:
            total = converter_valor(achou.group(1))
    return total


def extrair_itens(linhas: Iterable[str]) -> List[Item]:
    """Extrai os itens das linhas no formato 'DESCRIÇÃO QTD UN x UNITÁRIO TOTAL'."""
    itens: List[Item] = []
    for linha in linhas:
        achou = PADRAO_ITEM.match(linha.strip())
        if not achou:
            continue
        itens.append(
            Item(
                descricao=achou.group("descricao").strip(),
                quantidade=Decimal(achou.group("quantidade").replace(",", ".")),
                valor_unitario=converter_valor(achou.group("unitario")),
                valor_total=converter_valor(achou.group("total")),
            )
        )
    return itens


def extrair_nota(linhas: Iterable[str]) -> NotaFiscal:
    """Monta a NotaFiscal a partir das linhas de texto transcritas."""
    linhas = [linha for linha in linhas if linha and linha.strip()]
    cnpj = extrair_cnpj(linhas)
    return NotaFiscal(
        cnpj=cnpj,
        cnpj_valido=validar_cnpj(cnpj) if cnpj else None,
        chave_acesso=extrair_chave_acesso(linhas),
        data_emissao=extrair_data(linhas),
        valor_total=extrair_valor_total(linhas),
        itens=extrair_itens(linhas),
    )

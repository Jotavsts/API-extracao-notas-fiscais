"""Modelos de dados da nota fiscal e validações básicas."""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import List, Optional


def validar_cnpj(cnpj: str) -> bool:
    """Valida um CNPJ pelos dígitos verificadores. Aceita com ou sem pontuação."""
    digitos = [int(c) for c in cnpj if c.isdigit()]
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False

    def calcular(base: List[int]) -> int:
        pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        if len(base) == 13:
            pesos = [6] + pesos
        resto = sum(d * p for d, p in zip(base, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    primeiro = calcular(digitos[:12])
    segundo = calcular(digitos[:12] + [primeiro])
    return digitos[12] == primeiro and digitos[13] == segundo


def formatar_cnpj(cnpj: str) -> str:
    """Devolve o CNPJ no formato 00.000.000/0000-00."""
    d = "".join(c for c in cnpj if c.isdigit())
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


@dataclass
class Item:
    descricao: str
    quantidade: Decimal
    valor_unitario: Decimal
    valor_total: Decimal
    categoria: Optional[str] = None


@dataclass
class NotaFiscal:
    cnpj: Optional[str] = None
    cnpj_valido: Optional[bool] = None
    chave_acesso: Optional[str] = None
    data_emissao: Optional[str] = None  # formato ISO: AAAA-MM-DD
    valor_total: Optional[Decimal] = None
    itens: List[Item] = field(default_factory=list)

    def para_dict(self) -> dict:
        """Converte para um dicionário pronto para virar JSON (Decimal vira número)."""

        def converter(valor):
            if isinstance(valor, Decimal):
                return float(valor)
            if isinstance(valor, dict):
                return {k: converter(v) for k, v in valor.items()}
            if isinstance(valor, list):
                return [converter(v) for v in valor]
            return valor

        return converter(asdict(self))

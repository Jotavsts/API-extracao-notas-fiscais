"""Handler AWS Lambda para o API Gateway (POST /notas).

Corpo da requisição (JSON), com exatamente um dos campos:
  - "imagem_base64": a imagem da nota em base64;
  - "chave": a chave de uma imagem já enviada ao bucket S3 configurado.

O bucket nunca vem da requisição: ele é lido da variável BUCKET_NOTAS, e a chave
precisa começar com o prefixo permitido (PREFIXO_NOTAS, padrão "notas/").
"""

import base64
import binascii
import json
import logging
import os
from typing import Any, Dict, List, Optional

from .categorizador import Refinador, categorizar_itens
from .parser import extrair_nota
from .transcricao import (
    TAMANHO_MAXIMO_BYTES,
    ErroTranscricao,
    transcrever_imagem,
    transcrever_objeto_s3,
)

logger = logging.getLogger(__name__)

PREFIXO_PADRAO = "notas/"


class ErroRequisicao(Exception):
    """Problema na requisição do cliente. Vira uma resposta 4xx."""

    def __init__(self, mensagem: str, status: int = 400) -> None:
        super().__init__(mensagem)
        self.status = status


class ErroConfiguracao(Exception):
    """Problema de configuração do serviço. Vira uma resposta 500."""


def _resposta(status: int, corpo: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(corpo, ensure_ascii=False),
    }


def _ler_corpo(evento: Dict[str, Any]) -> Dict[str, Any]:
    corpo = evento.get("body")
    if not corpo:
        raise ErroRequisicao("O corpo da requisição está vazio.")
    if evento.get("isBase64Encoded"):
        corpo = base64.b64decode(corpo).decode("utf-8")
    try:
        dados = json.loads(corpo)
    except json.JSONDecodeError as erro:
        raise ErroRequisicao("O corpo da requisição precisa ser um JSON válido.") from erro
    if not isinstance(dados, dict):
        raise ErroRequisicao("O corpo da requisição precisa ser um objeto JSON.")
    return dados


def _decodificar_imagem(imagem_base64: Any) -> bytes:
    try:
        imagem = base64.b64decode(imagem_base64, validate=True)
    except (binascii.Error, ValueError, TypeError) as erro:
        raise ErroRequisicao("O campo 'imagem_base64' não é um base64 válido.") from erro
    if len(imagem) > TAMANHO_MAXIMO_BYTES:
        raise ErroRequisicao("A imagem excede o limite de 10 MB.", status=413)
    return imagem


def _validar_chave(chave: Any) -> str:
    prefixo = os.environ.get("PREFIXO_NOTAS", PREFIXO_PADRAO)
    if not isinstance(chave, str) or not chave.startswith(prefixo) or ".." in chave:
        raise ErroRequisicao(f"A chave precisa começar com '{prefixo}'.")
    return chave


def _obter_linhas(dados: Dict[str, Any], textract_client: Optional[Any]) -> List[str]:
    imagem_base64 = dados.get("imagem_base64")
    chave = dados.get("chave")
    if bool(imagem_base64) == bool(chave):
        raise ErroRequisicao("Envie exatamente um dos campos: 'imagem_base64' ou 'chave'.")

    if imagem_base64:
        return transcrever_imagem(_decodificar_imagem(imagem_base64), textract_client)

    bucket = os.environ.get("BUCKET_NOTAS")
    if not bucket:
        raise ErroConfiguracao("A variável BUCKET_NOTAS não está definida.")
    return transcrever_objeto_s3(bucket, _validar_chave(chave), textract_client)


def processar(
    evento: Dict[str, Any],
    textract_client: Optional[Any] = None,
    refinador: Optional[Refinador] = None,
) -> Dict[str, Any]:
    """Processa a requisição e devolve a resposta no formato do API Gateway."""
    try:
        linhas = _obter_linhas(_ler_corpo(evento), textract_client)
    except ErroRequisicao as erro:
        return _resposta(erro.status, {"erro": str(erro)})
    except ErroTranscricao as erro:
        return _resposta(502, {"erro": str(erro)})
    except ErroConfiguracao as erro:
        logger.error("Configuração inválida: %s", erro)
        return _resposta(500, {"erro": "Serviço indisponível."})

    nota = extrair_nota(linhas)
    nota.itens = categorizar_itens(nota.itens, refinador)

    corpo = nota.para_dict()
    if not linhas:
        corpo["aviso"] = "Nenhum texto foi encontrado na imagem."
    return _resposta(200, corpo)


def lambda_handler(evento: Dict[str, Any], contexto: Any) -> Dict[str, Any]:
    """Ponto de entrada da função Lambda."""
    try:
        return processar(evento)
    except Exception:  # noqa: BLE001 - última barreira: não vazar detalhes internos
        logger.exception("Erro inesperado ao processar a nota")
        return _resposta(500, {"erro": "Erro interno."})

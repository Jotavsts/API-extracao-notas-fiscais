"""Transcreve imagens de notas fiscais para texto com o Amazon Textract."""

import logging
from typing import Any, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Limite da API síncrona do Textract para documentos enviados em bytes.
TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024


class ErroTranscricao(Exception):
    """Falha ao transcrever o documento (imagem inválida, acesso negado, serviço fora do ar)."""


def _linhas(resposta: dict) -> List[str]:
    """Pega só os blocos do tipo LINE, na ordem em que o Textract devolve."""
    return [
        bloco["Text"]
        for bloco in resposta.get("Blocks", [])
        if bloco.get("BlockType") == "LINE" and bloco.get("Text")
    ]


def _detectar(documento: dict, client: Optional[Any]) -> List[str]:
    cliente = client or boto3.client("textract")
    try:
        resposta = cliente.detect_document_text(Document=documento)
    except (ClientError, BotoCoreError) as erro:
        logger.error("Falha no Textract: %s", erro)
        raise ErroTranscricao("Não foi possível transcrever o documento.") from erro
    return _linhas(resposta)


def transcrever_imagem(imagem: bytes, client: Optional[Any] = None) -> List[str]:
    """Transcreve uma imagem enviada em bytes. Devolve uma lista de linhas de texto."""
    if not imagem:
        raise ErroTranscricao("A imagem está vazia.")
    if len(imagem) > TAMANHO_MAXIMO_BYTES:
        raise ErroTranscricao("A imagem excede o limite de 10 MB.")
    return _detectar({"Bytes": imagem}, client)


def transcrever_objeto_s3(bucket: str, chave: str, client: Optional[Any] = None) -> List[str]:
    """Transcreve uma imagem que já está em um bucket S3."""
    return _detectar({"S3Object": {"Bucket": bucket, "Name": chave}}, client)

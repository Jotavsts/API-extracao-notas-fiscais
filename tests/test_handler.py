import base64
import json

import pytest
from botocore.exceptions import ClientError

from nf_extractor.handler import processar
from nf_extractor.transcricao import TAMANHO_MAXIMO_BYTES, ErroTranscricao, transcrever_imagem


class TextractFalso:
    """Simula o cliente do Textract, devolvendo linhas prontas e guardando as chamadas."""

    def __init__(self, linhas=None, erro=None):
        self.linhas = linhas or []
        self.erro = erro
        self.chamadas = []

    def detect_document_text(self, Document):
        self.chamadas.append(Document)
        if self.erro:
            raise self.erro
        blocos = [{"BlockType": "PAGE"}] + [
            {"BlockType": "LINE", "Text": linha} for linha in self.linhas
        ]
        blocos.append({"BlockType": "WORD", "Text": "ignorada"})
        return {"Blocks": blocos}


def _evento(corpo):
    return {"body": json.dumps(corpo)}


def _imagem_b64(conteudo=b"bytes-de-uma-imagem"):
    return base64.b64encode(conteudo).decode()


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("BUCKET_NOTAS", "bucket-de-teste")
    monkeypatch.delenv("PREFIXO_NOTAS", raising=False)


def test_extrai_e_categoriza_a_partir_de_uma_imagem(linhas_nota_exemplo):
    textract = TextractFalso(linhas_nota_exemplo)
    resposta = processar(_evento({"imagem_base64": _imagem_b64()}), textract)

    assert resposta["statusCode"] == 200
    assert resposta["headers"]["Content-Type"] == "application/json"
    corpo = json.loads(resposta["body"])
    assert corpo["cnpj_valido"] is True
    assert corpo["valor_total"] == 58.67
    assert [i["categoria"] for i in corpo["itens"]] == ["alimentos", "alimentos", "limpeza", "limpeza"]
    assert textract.chamadas == [{"Bytes": b"bytes-de-uma-imagem"}]


def test_le_a_imagem_do_bucket_configurado(linhas_nota_exemplo):
    textract = TextractFalso(linhas_nota_exemplo)
    resposta = processar(_evento({"chave": "notas/cupom-1.jpg"}), textract)

    assert resposta["statusCode"] == 200
    assert textract.chamadas == [{"S3Object": {"Bucket": "bucket-de-teste", "Name": "notas/cupom-1.jpg"}}]


def test_o_bucket_enviado_pelo_cliente_e_ignorado(linhas_nota_exemplo):
    textract = TextractFalso(linhas_nota_exemplo)
    processar(_evento({"chave": "notas/a.jpg", "bucket": "bucket-de-outra-pessoa"}), textract)
    assert textract.chamadas[0]["S3Object"]["Bucket"] == "bucket-de-teste"


@pytest.mark.parametrize("chave", ["outra-pasta/a.jpg", "notas/../segredo.jpg", "/notas/a.jpg", 123])
def test_rejeita_chave_fora_do_prefixo_permitido(chave):
    textract = TextractFalso()
    resposta = processar(_evento({"chave": chave}), textract)
    assert resposta["statusCode"] == 400
    assert textract.chamadas == []


@pytest.mark.parametrize(
    "evento",
    [
        {},
        {"body": ""},
        {"body": "isso não é json"},
        {"body": json.dumps([1, 2, 3])},
        _evento({}),
        _evento({"imagem_base64": _imagem_b64(), "chave": "notas/a.jpg"}),
        _evento({"imagem_base64": "%%%não-é-base64%%%"}),
    ],
)
def test_requisicoes_invalidas_devolvem_400(evento):
    assert processar(evento, TextractFalso())["statusCode"] == 400


def test_imagem_grande_demais_devolve_413():
    grande = _imagem_b64(b"0" * (TAMANHO_MAXIMO_BYTES + 1))
    assert processar(_evento({"imagem_base64": grande}), TextractFalso())["statusCode"] == 413


def test_sem_bucket_configurado_devolve_500_sem_detalhes(monkeypatch):
    monkeypatch.delenv("BUCKET_NOTAS")
    resposta = processar(_evento({"chave": "notas/a.jpg"}), TextractFalso())
    assert resposta["statusCode"] == 500
    assert "BUCKET" not in resposta["body"]


def test_falha_do_textract_devolve_502_sem_detalhes():
    erro = ClientError({"Error": {"Code": "AccessDenied", "Message": "segredo interno"}}, "DetectDocumentText")
    resposta = processar(_evento({"imagem_base64": _imagem_b64()}), TextractFalso(erro=erro))
    assert resposta["statusCode"] == 502
    assert "segredo" not in resposta["body"]


def test_imagem_sem_texto_devolve_aviso():
    resposta = processar(_evento({"imagem_base64": _imagem_b64()}), TextractFalso([]))
    corpo = json.loads(resposta["body"])
    assert resposta["statusCode"] == 200
    assert corpo["aviso"] == "Nenhum texto foi encontrado na imagem."


def test_corpo_em_base64_do_api_gateway():
    corpo = base64.b64encode(json.dumps({"imagem_base64": _imagem_b64()}).encode()).decode()
    resposta = processar({"body": corpo, "isBase64Encoded": True}, TextractFalso(["linha"]))
    assert resposta["statusCode"] == 200


def test_transcrever_imagem_vazia_levanta_erro():
    with pytest.raises(ErroTranscricao):
        transcrever_imagem(b"", TextractFalso())

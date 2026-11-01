from pathlib import Path

import pytest

DIRETORIO_EXEMPLOS = Path(__file__).parent / "exemplos"


@pytest.fixture
def linhas_nota_exemplo():
    """Linhas de um cupom fiscal fictício, no formato transcrito pelo OCR."""
    arquivo = DIRETORIO_EXEMPLOS / "cupom_exemplo.txt"
    return arquivo.read_text(encoding="utf-8").splitlines()

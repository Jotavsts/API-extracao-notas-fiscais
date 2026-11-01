import json
from pathlib import Path

from nf_extractor.cli import main

EXEMPLO = Path(__file__).parent / "exemplos" / "cupom_exemplo.txt"


def test_imprime_o_json_da_nota(capsys):
    codigo = main(["--texto", str(EXEMPLO)])
    saida = json.loads(capsys.readouterr().out)

    assert codigo == 0
    assert saida["cnpj_valido"] is True
    assert saida["valor_total"] == 58.67
    assert saida["itens"][0]["categoria"] == "alimentos"


def test_arquivo_inexistente_devolve_codigo_1(capsys, tmp_path):
    codigo = main(["--texto", str(tmp_path / "nao-existe.txt")])
    assert codigo == 1
    assert "Não foi possível ler o arquivo" in capsys.readouterr().err

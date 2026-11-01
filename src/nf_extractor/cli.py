"""Linha de comando para extrair uma nota fiscal localmente, sem API Gateway nem Lambda."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .categorizador import categorizar_itens
from .parser import extrair_nota
from .transcricao import ErroTranscricao, transcrever_imagem


def construir_argumentos() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nf_extractor",
        description="Extrai e categoriza os dados de uma nota fiscal e imprime o resultado em JSON.",
    )
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("--texto", type=Path, help="arquivo de texto com as linhas já transcritas (não usa a AWS)")
    origem.add_argument("--imagem", type=Path, help="imagem da nota; transcreve com o Textract (exige credenciais AWS)")
    return parser


def _ler_linhas(args: argparse.Namespace) -> List[str]:
    if args.texto:
        return args.texto.read_text(encoding="utf-8").splitlines()
    return transcrever_imagem(args.imagem.read_bytes())


def main(argv: Optional[List[str]] = None) -> int:
    args = construir_argumentos().parse_args(argv)
    try:
        linhas = _ler_linhas(args)
    except OSError as erro:
        print(f"Não foi possível ler o arquivo: {erro}", file=sys.stderr)
        return 1
    except ErroTranscricao as erro:
        print(f"Erro na transcrição: {erro}", file=sys.stderr)
        return 2

    nota = extrair_nota(linhas)
    nota.itens = categorizar_itens(nota.itens)
    print(json.dumps(nota.para_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

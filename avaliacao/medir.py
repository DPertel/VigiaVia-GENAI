"""Avaliação reprodutível: retrieval independente; geração só quando Ollama estiver disponível."""
import argparse
import json
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import KB, answer, THRESHOLD

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "avaliacao" / "casos.json").read_text(encoding="utf-8"))

def retrieval_report(threshold: float):
    positive = [t for t in CASES if t["fontes_esperadas"]]
    details = []
    for test in CASES:
        ranked = KB.search(test["pergunta"], 3)
        accepted = [d["id"] for d in ranked if d["score"] >= threshold]
        expected = set(test["fontes_esperadas"])
        details.append({"caso": test["id"], "esperadas": sorted(expected),
                        "top3": [d["id"] for d in ranked], "scores": [d["score"] for d in ranked],
                        "aceitas": accepted, "recall1": bool(expected.intersection(accepted[:1])) if expected else None,
                        "recall3": bool(expected.intersection(accepted[:3])) if expected else None,
                        "recusa_por_limiar": len(accepted) == 0})
    pos = [d for d in details if d["esperadas"]]
    negative = [d for d in details if not d["esperadas"]]
    return {"limiar": threshold, "n_positivos": len(pos), "n_nao_consta": len(negative),
            "recall_at_1": sum(d["recall1"] for d in pos) / len(pos),
            "recall_at_3": sum(d["recall3"] for d in pos) / len(pos),
            "taxa_abstencao_nao_consta_busca": sum(d["recusa_por_limiar"] for d in negative) / len(negative),
            "detalhes": details}

def gen_report(threshold: float):
    results = {}
    for mode in ["baseline", "rag", "agente"]:
        rows = []
        for test in CASES:
            try:
                result = answer(test["pergunta"], mode, threshold=threshold)
                cited = all(x in KB.by_id for x in result["fontes"])
                refusal_ok = bool(result["recusa"]) == bool(test["nao_consta"])
                # Marcador explícito de revisão manual; não infere correção semântica automaticamente.
                rows.append({"caso": test["id"], "gabarito": test["gabarito"],
                             "resultado": result, "json_valido": True,
                             "fontes_ids_validos": cited, "recusa_correta": refusal_ok,
                             "correcao_semantica_manual": None})
            except Exception as exc:
                rows.append({"caso": test["id"], "erro": type(exc).__name__,
                             "correcao_semantica_manual": None})
        completed = [r for r in rows if "resultado" in r]
        results[mode] = {"casos_executados": len(completed), "total": len(rows),
                         "taxa_json_valido": (sum(r["json_valido"] for r in completed) / len(completed)) if completed else None,
                         "taxa_recusa_correta": (sum(r["recusa_correta"] for r in completed) / len(completed)) if completed else None,
                         "linhas": rows}
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    parser.add_argument("--geracao", action="store_true", help="Executa as 3 configurações com Ollama instalado")
    args = parser.parse_args()
    output = ROOT / "avaliacao" / "resultados_busca.json"
    output.write_text(json.dumps(retrieval_report(args.threshold), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Busca avaliada: {output}")
    if args.geracao:
        path = ROOT / "avaliacao" / "resultados_geracao.json"
        path.write_text(json.dumps(gen_report(args.threshold), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Geração avaliada: {path}. Preencha revisão semântica manual.")

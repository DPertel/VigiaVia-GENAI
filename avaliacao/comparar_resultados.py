"""Compara comportamento estrutural do Ollama, sem confundir recusa com acerto."""
from pathlib import Path
import json,collections
ROOT=Path(__file__).resolve().parent
FILES=[('V4.2 (preservada)',ROOT/'rodada_02_v42_original'/'placar_real.json'),('V4.3 (nova)',ROOT/'placar_real.json')]
for nome,path in FILES:
    if not path.exists():
        print(nome,'- sem execução real:',path.name)
        continue
    data=json.loads(path.read_text(encoding='utf-8'))
    grouped=collections.defaultdict(list)
    for row in data.get('avaliacoes',[]): grouped[row['configuracao']].append(row)
    print('\n'+nome)
    for mode,rows in grouped.items():
        errors=sum(bool(r.get('erro_execucao')) for r in rows)
        wrong_refusal=sum(r.get('saida') is not None and bool(r['saida'].get('recusa')) != bool(r.get('nao_consta_esperado')) for r in rows)
        good_refusal=sum(r.get('saida') is not None and bool(r['saida'].get('recusa')) and bool(r.get('nao_consta_esperado')) for r in rows)
        citations=sum(r.get('saida') is not None and not r['saida'].get('recusa') and bool(r['saida'].get('fontes')) for r in rows)
        print(f'{mode}: n={len(rows)} erros={errors} recusas_inadequadas={wrong_refusal} recusas_corretas={good_refusal} respostas_com_fontes={citations}')
print('\nATENÇÃO: revisão semântica e avaliação de alucinações exigem inspeção humana. Métricas acima não são acurácia.')

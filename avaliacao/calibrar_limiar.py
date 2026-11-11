"""Gera tabela de trade-off da busca, sem executar Ollama.
Métricas de recuperação, não acurácia de geração.
"""
from pathlib import Path
import json
p=Path(__file__).resolve().parent
x=json.loads((p/'rodada_01_original'/'resultados_busca.json').read_text(encoding='utf-8'))
rows=[]
for t in [0.12,0.15,0.16,0.17,0.18,0.19,0.20]:
 pos=[c for c in x['detalhes'] if c['esperadas']]
 neg=[c for c in x['detalhes'] if not c['esperadas']]
 # A ferramenta de busca ordenou os documentos. Aplicar threshold aos top3.
 hit1=sum(c['scores'][0]>=t and c['top3'][0] in c['esperadas'] for c in pos)
 hit3=sum(any(s>=t and d in c['esperadas'] for d,s in zip(c['top3'],c['scores'])) for c in pos)
 abst=sum(c['scores'][0]<t for c in neg)
 rows.append({'limiar':t,'recall_at_1':round(hit1/len(pos),4),'recall_at_3':round(hit3/len(pos),4),
              'recusas_por_limiar_corretas':abst,'perguntas_sem_resposta':len(neg)})
(p/'calibracao_limires.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('Limiar | recall@1 | recall@3 | recusas corretas apenas pelo limiar')
for r in rows:print(f"{r['limiar']:.2f} | {r['recall_at_1']:.2%} | {r['recall_at_3']:.2%} | {r['recusas_por_limiar_corretas']}/{r['perguntas_sem_resposta']}")

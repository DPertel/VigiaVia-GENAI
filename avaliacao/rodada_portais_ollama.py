"""Avalia casos operacionais com Ollama REAL; o julgamento semântico final é manual.
Não confundir com os testes unitários mockados.
"""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.operacao import carregar_relatos
from app.inteligencia_operacional import atender
root=Path(__file__).resolve().parent
cases=json.loads((root/'casos_portais.json').read_text(encoding='utf-8'))
base=carregar_relatos('demo')
results=[]
for c in cases:
    t=time.perf_counter()
    try:
        x=atender(base,c['portal'],c['pergunta'],**c['dados']);err=None
    except Exception as exc:x=None;err=type(exc).__name__+': '+str(exc)
    out={'id':c['id'],'portal':c['portal'],'pergunta':c['pergunta'],
         'gabarito':c['esperado'],'nao_consta_esperado':c['nao_consta'],
         'saida':x,'erro':err,'latencia_ms':round(1000*(time.perf_counter()-t),1),
         'correto_semanticamente':None,'alucinacao':None,'revisao':'PENDENTE - preencher após inspeção humana'}
    results.append(out)
    print(c['id'], 'ERRO' if err else ('recusa='+str(x['resposta_ia']['recusa'])))
(root/'rodada_portais_real.json').write_text(json.dumps({'metodologia':'Qwen2.5 Ollama local, dados demo identificados, revisão manual pendente','avaliacoes':results},ensure_ascii=False,indent=2),encoding='utf-8')
print('Salvo:',root/'rodada_portais_real.json')

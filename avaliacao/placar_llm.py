"""Avalia as três configurações com Ollama real. Não gera resultados fictícios."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import answer
ROOT=Path(__file__).resolve().parent
casos=json.loads((ROOT/'casos.json').read_text(encoding='utf-8'))
rows=[]
for config in ('baseline','rag','agente'):
    for case in casos:
        inicio=time.perf_counter()
        try:
            out=answer(case['pergunta'],config)
            erro=None
        except Exception as e:
            out=None; erro=type(e).__name__+': '+str(e)
        dt=round((time.perf_counter()-inicio)*1000,1)
        row={'configuracao':config,'caso_id':case['id'],'pergunta':case['pergunta'],'gabarito':case['gabarito'],'nao_consta_esperado':case['nao_consta'],'fontes_esperadas':case['fontes_esperadas'],'saida':out,'erro_execucao':erro,'latencia_ms':dt}
        if out:
            row['recusa_correta']=bool(out.get('recusa'))==bool(case['nao_consta'])
            row['fonte_esperada_citada']=bool(set(out.get('fontes',[]))&set(case['fontes_esperadas'])) if case['fontes_esperadas'] else not bool(out.get('fontes'))
        rows.append(row)
        print(config,case['id'],f'{dt:.1f}ms',('ERRO: '+erro) if erro else ('recusa='+str(out.get('recusa'))))
saida={'metodologia':'Execução real de Ollama, revisão manual necessária para correção semântica e alucinações','modelo':'qwen2.5:1.5b (pode ser substituído via OLLAMA_MODEL)','avaliacoes':rows}
(ROOT/'placar_real.json').write_text(json.dumps(saida,ensure_ascii=False,indent=2),encoding='utf-8')
print('Salvo:',ROOT/'placar_real.json')

import json
from app.operacao import carregar_relatos
from app.inteligencia_operacional import atender, evidencias_operacionais, gerar_orientacao

BASE=carregar_relatos('demo')

def test_zeladoria_explicacao_gerada_com_fonte_do_sistema():
    def simular(_prompt):
        return json.dumps({'resposta':'A ocorrência DEMO-001 é prioritária por ter severidade alta, prioridade 9.000 e 4 confirmações.', 'recusa':False})
    res=atender(BASE,'zeladoria','Quais ocorrências precisam de revisão primeiro?',generator=simular)
    ia=res['resposta_ia']
    assert not ia['recusa'] and ia['gerada_por_llm']
    assert 'FILA' in ia['fontes'] and 'DEMO-001' in ia['evidencia_literal']

def test_segunda_tentativa_apos_recusa():
    calls=[]
    def simular(prompt):
        calls.append(prompt)
        if len(calls)==1:
            return json.dumps({'resposta':'não consta','recusa':True})
        return json.dumps({'resposta':'A ocorrência DEMO-001 tem severidade alta e prioridade 9.000.','recusa':False})
    res=atender(BASE,'zeladoria','Quais ocorrências precisam de revisão primeiro?',generator=simular)
    assert not res['resposta_ia']['recusa']
    assert res['resposta_ia']['tentativas']==2

def test_nao_publica_numero_inventado():
    def simular(_):
        return json.dumps({'resposta':'A ocorrência DEMO-001 tem prioridade 999.','recusa':False})
    res=atender(BASE,'zeladoria','Quais ocorrências precisam de revisão primeiro?',generator=simular)
    assert res['resposta_ia']['recusa']
    assert not res['resposta_ia']['gerada_por_llm']

def test_cidadao_mostra_ativos_e_encerrados():
    e=evidencias_operacionais(BASE,'cidadao','proximidade',latitude=-23.560345,longitude=-46.650508)
    fatos=e['fatos']
    assert sum(fatos['por_status'].values())==fatos['quantidade']
    assert fatos['ativos']==fatos['por_status']['pendente']+fatos['por_status']['confirmado']
    assert 'ativo(s)' in e['mensagem']

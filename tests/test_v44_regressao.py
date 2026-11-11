"""Regressão V4.4: triagem, contagem e revisão por fonte decisiva."""
import json
from app import core
from app.inteligencia_operacional import atender, evidencias_operacionais, _verificar_resposta
from app.operacao import carregar_relatos

BASE = carregar_relatos('demo')

def gerar_roteiro(respostas):
    it = iter(respostas)
    return lambda prompt: json.dumps(next(it), ensure_ascii=False)

def test_indicadores_resposta_curta_contagem_e_aceita():
    ev = evidencias_operacionais(BASE,'zeladoria','indicadores')['evidencias']
    ok, causa = _verificar_resposta('São 9 relatos na amostra.',ev,'Quantos relatos estão na amostra?')
    assert ok, causa

def test_indicadores_contagem_inventada_e_rejeitada():
    ev = evidencias_operacionais(BASE,'zeladoria','indicadores')['evidencias']
    ok,_ = _verificar_resposta('São 10 relatos na amostra.',ev,'Quantos relatos estão na amostra?')
    assert not ok

def test_z03_gera_sem_fallback():
    x=atender(BASE,'zeladoria','Quantos relatos estão na amostra?',
              generator=lambda _: json.dumps({'resposta':'São 9 relatos na amostra.','recusa':False}))
    assert not x['resposta_ia']['recusa'] and x['resposta_ia']['gerada_por_llm']

def test_z02_retry_explicita_duplicidade():
    gerador=gerar_roteiro([
        {'resposta':'DEMO-001 está pendente, com severidade alta, 4 confirmações e prioridade 9.000.','recusa':False},
        {'resposta':'O registro DEMO-001 está pendente, severidade alta, 4 confirmações, prioridade 9.000; DEMO-007 está próximo, sendo uma possível duplicidade que precisa de revisão humana.','recusa':False},
    ])
    x=atender(BASE,'zeladoria','Quais os critérios de triagem de DEMO-001?',relato_id='DEMO-001',generator=gerador)
    assert not x['resposta_ia']['recusa'],x['resposta_ia']
    assert x['resposta_ia']['tentativas']==2
    assert 'DEMO-007' in x['resposta_ia']['resposta']

def test_z02_sem_duplicidade_continua_rejeitada():
    x=atender(BASE,'zeladoria','Quais os critérios de triagem de DEMO-001?',relato_id='DEMO-001',
              generator=lambda _:json.dumps({'resposta':'DEMO-001 está pendente, com prioridade 9.000.','recusa':False}))
    assert x['resposta_ia']['recusa']

def test_login_documental_revisado_terceira_tentativa(monkeypatch):
    monkeypatch.setattr(core,'generate',gerar_roteiro([
        {'resposta':'Sim, exige login.','fontes':['V10'],'recusa':False},
        {'resposta':'Não sei.','fontes':[],'recusa':True},
        {'resposta':'No MVP a fila da zeladoria não tem autenticação; Entra ID é previsto para produção.','fontes':['V10'],'recusa':False},
    ]))
    out=core.answer('A fila da zeladoria exige login no MVP?','agente')
    assert not out['recusa'] and out['tentativas']==3

def test_transferencia_documental_revisada(monkeypatch):
    monkeypatch.setattr(core,'generate',gerar_roteiro([
        {'resposta':'Não há transferência internacional.','fontes':['V11'],'recusa':False},
        {'resposta':'A pesquisa pelo Nominatim pode enviar o texto digitado para fora do Brasil, com potencial transferência internacional.','fontes':['V11'],'recusa':False},
    ]))
    out=core.answer('Existe transferência internacional ao pesquisar um endereço?','agente')
    assert not out['recusa'] and out['tentativas']==2

def test_transferencia_contradicao_persistente_recusa(monkeypatch):
    monkeypatch.setattr(core,'generate',lambda _:json.dumps({'resposta':'Não há transferência internacional.','fontes':['V11'],'recusa':False}))
    assert core.answer('Existe transferência internacional ao pesquisar um endereço?','agente')['recusa']

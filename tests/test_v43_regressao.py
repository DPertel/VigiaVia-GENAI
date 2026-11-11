"""Regressão com paráfrases além das perguntas usadas na avaliação original."""
import json
import pytest
from app import core
from app.verificador_semantico import validate, select_evidence
from app.operacao import carregar_relatos
from app.inteligencia_operacional import atender, selecionar_intencao, evidencias_operacionais, _verificar_resposta

BASE = carregar_relatos('demo')

def doc(i): return core.KB.by_id[i]

@pytest.mark.parametrize('pergunta,resposta,id_doc',[
    ('Existe login para a zeladoria no MVP?', 'Sim, exige login.', 'V10'),
    ('A busca de endereço transfere informações internacionalmente?', 'Não há transferência internacional.', 'V11'),
    ('O sistema guarda imagens? E os logs?', 'Não armazena as imagens enviadas.', 'V09'),
    ('Quais são as fontes de dados do detector e dos relatos?', 'Fonte: leia o README.', 'V05'),
    ('Como a detecção chega à zeladoria?', 'O treinamento usa RDD2022.', 'V03'),
])
def test_falhas_semanticas_rejeitadas(pergunta,resposta,id_doc):
    ok,_ = validate(pergunta,resposta,[doc(id_doc)])
    assert not ok

@pytest.mark.parametrize('pergunta,resposta,id_doc',[
    ('A fila da zeladoria exige login no MVP?', 'Não. A fila do MVP não tem autenticação, e o login Entra ID é previsto para produção.', 'V10'),
    ('Existe transferência internacional ao pesquisar um endereço?', 'Há potencial transferência internacional do texto pesquisado pelo Nominatim.', 'V11'),
    ('O sistema guarda fotos e os logs?', 'A API não armazena as imagens enviadas e os logs no Log Analytics são retidos por 30 dias.', 'V09'),
    ('Quais são as fontes de dados do detector e dos relatos?', 'RDD2022 treina o detector; relatos vêm dos cidadãos e os dados de demonstração são simulados.', 'V05'),
])
def test_respostas_documentadas_aceitas(pergunta,resposta,id_doc):
    ok,_=validate(pergunta,resposta,[doc(id_doc)])
    assert ok

def test_selecao_fonte_prioritaria_mesmo_abaixo_do_limiar():
    pergunta='Como funciona a detecção e o envio dos relatos à zeladoria?'
    docs=select_evidence(pergunta,core.KB.search(pergunta,5),core.KB.by_id)
    assert docs[0]['id']=='V03'

def test_agente_refaz_resposta_contraditoria(monkeypatch):
    respostas=iter([
        {'resposta':'Sim, exige login.','fontes':['V10'],'recusa':False},
        {'resposta':'Não. A fila do MVP não tem autenticação; o login Entra ID é previsto para produção.','fontes':['V10'],'recusa':False},
    ])
    monkeypatch.setattr(core,'generate',lambda _: json.dumps(next(respostas),ensure_ascii=False))
    x=core.answer('A fila da zeladoria exige login no MVP?','agente')
    assert not x['recusa'] and x['tentativas']==2 and 'V10' in x['fontes']

def test_agente_bloqueia_duas_contradicoes(monkeypatch):
    monkeypatch.setattr(core,'generate',lambda _:json.dumps({'resposta':'Não há transferência internacional.','fontes':['V11'],'recusa':False}))
    x=core.answer('Existe transferência internacional ao pesquisar um endereço?','agente')
    assert x['recusa'] and not x['fontes']

@pytest.mark.parametrize('texto,intencao',[
    ('Qual ocorrência ativa lidera a fila?', 'prioridades'),
    ('Quem está no topo da fila?', 'prioridades'),
    ('Quantos relatos estão na amostra?', 'indicadores'),
    ('Qual é a situação da fila?', 'indicadores'),
])
def test_roteador_zela(texto,intencao):
    assert selecionar_intencao('zeladoria',texto,None,None,None)==intencao

def test_fila_lider_identificado_sem_llm():
    x=evidencias_operacionais(BASE,'zeladoria','prioridades')
    assert x['fatos']['top_5'][0]['id']=='DEMO-001'

def test_triagem_incompleta_rejeitada():
    x=evidencias_operacionais(BASE,'zeladoria','relato',relato_id='DEMO-001')
    ok,_=_verificar_resposta('O relato DEMO-001 está pendente, severidade alta, 4 confirmações e prioridade 9.000.', x['evidencias'], 'Quais os critérios de triagem de DEMO-001?')
    assert not ok

def test_triagem_sem_urgencia_garantida():
    x=evidencias_operacionais(BASE,'zeladoria','relato',relato_id='DEMO-001')
    ok,_=_verificar_resposta('A ocorrência DEMO-001 requer atenção imediata por prioridade 9.000.',x['evidencias'],'Quais os critérios de triagem de DEMO-001?')
    assert not ok

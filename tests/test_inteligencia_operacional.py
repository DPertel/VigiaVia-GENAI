import json
from fastapi.testclient import TestClient
from app.main import app
from app.operacao import carregar_relatos
from app.inteligencia_operacional import (selecionar_intencao,evidencias_operacionais,gerar_orientacao,atender)

BASE=carregar_relatos('demo')

def test_cidadao_contexto_proximidade():
    result=evidencias_operacionais(BASE,'cidadao','proximidade',latitude=-23.560345,longitude=-46.650508)
    assert result['fatos']['quantidade']>0
    assert result['fatos']['ocorrencias'][0]['id']=='DEMO-001'

def test_cidadao_acompanhar():
    result=evidencias_operacionais(BASE,'cidadao','acompanhar',relato_id='DEMO-001')
    assert result['fatos']['status']=='pendente'

def test_zeladoria_prioridade():
    result=evidencias_operacionais(BASE,'zeladoria','prioridades')
    assert result['fatos']['top_5'][0]['id']=='DEMO-001'

def test_verificador_aceita_citacao_literal():
    docs=[{'id':'FILA','texto':'Existem 3 relatos pendentes.','origem':'teste'}]
    mock=lambda _:json.dumps({'resposta':'Existem 3 relatos pendentes.','fontes':['FILA'],'recusa':False,'evidencia_literal':'Existem 3 relatos pendentes.','proximos_passos':[]})
    out=gerar_orientacao('quantos?',docs,'cidadao',generator=mock)
    assert not out['recusa']

def test_verificador_rejeita_fonte_inventada():
    docs=[{'id':'FILA','texto':'Existem 3 relatos pendentes.','origem':'teste'}]
    mock=lambda _:json.dumps({'resposta':'São 3','fontes':['NADA'],'recusa':False,'evidencia_literal':'Existem 3 relatos pendentes.'})
    assert gerar_orientacao('quantos?',docs,'cidadao',generator=mock)['recusa']

def test_verificador_rejeita_numero_inventado():
    docs=[{'id':'FILA','texto':'Existem 3 relatos pendentes.','origem':'teste'}]
    mock=lambda _:json.dumps({'resposta':'Existem 23 relatos pendentes.','fontes':['FILA'],'recusa':False,'evidencia_literal':'Existem 3 relatos pendentes.'})
    assert gerar_orientacao('quantos?',docs,'cidadao',generator=mock)['recusa']

def test_caso_nao_consta():
    out=atender(BASE,'cidadao','Qual a previsão de conserto do relato?',relato_id='INEXISTENTE',generator=lambda _: '{}')
    assert out['resposta_ia']['recusa']

def test_nao_aceita_outro_papel():
    try:atender(BASE,'administrador','analisar tudo',generator=lambda _: '{}')
    except ValueError:pass
    else:raise AssertionError('Perfil não validado')

def test_api_operacional_validacao():
    c=TestClient(app)
    r=c.post('/api/ia/atender',json={'papel':'cidadao','pergunta':'Existem buracos próximos?','modo':'demo','latitude':-23.56})
    assert r.status_code==422

def test_api_nao_escreve():
    c=TestClient(app)
    r=c.post('/api/ia/atender',json={'papel':'zeladoria','pergunta':'Qual o relato prioritário?','modo':'demo'})
    assert r.status_code==200
    assert r.json()['requer_validacao_humana']
    assert r.json()['dados_verificados']['top_5'][0]['id']=='DEMO-001'

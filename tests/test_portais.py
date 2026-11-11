from fastapi.testclient import TestClient
from app.main import app
from app.operacao import carregar_relatos
from app.portais import consultar_proximos, acompanhar, fila_zeladoria, ficha_triagem

client=TestClient(app)

def test_cidadao_proximos_demo():
    base=carregar_relatos('demo')
    r=consultar_proximos(base,-23.560345,-46.650508,50)
    assert r['modo']=='demo' and r['total']>=2
    assert all(x['distancia_m']<=50 for x in r['relatos'])

def test_cidadao_status_sem_prazo():
    d=acompanhar(carregar_relatos('demo'),'DEMO-001')
    assert d['relato']['status']=='pendente'
    assert 'previsão' in d['aviso']

def test_cidadao_id_ausente():
    assert client.get('/api/cidadao/acompanhar/INEXISTENTE?modo=demo').status_code==404

def test_filtros_zeladoria():
    d=fila_zeladoria(carregar_relatos('demo'),'pendente','alta')
    assert all(r['status']=='pendente' and r['severidade']=='alta' for r in d['fila_priorizada'])

def test_triagem_humana():
    d=ficha_triagem(carregar_relatos('demo'),'DEMO-001')
    assert d['analise']['possiveis_duplicidades_15m']>=1
    assert 'Revisar' in d['analise']['recomendacao']

def test_portais_endpoints():
    r=client.get('/api/cidadao/proximos',params={'lat':-23.560345,'lon':-46.650508,'modo':'demo'})
    assert r.status_code==200 and r.json()['modo']=='demo'
    assert client.get('/api/cidadao/acompanhar/DEMO-001?modo=demo').status_code==200
    assert client.get('/api/zeladoria/fila?modo=demo&status=pendente').status_code==200
    assert client.get('/api/zeladoria/triagem/DEMO-001?modo=demo').status_code==200
    assert 'Portal do cidadão' in client.get('/').text
    assert 'Portal da zeladoria' in client.get('/').text

def test_invalidacao_e_sem_escrita():
    assert client.get('/api/cidadao/proximos?modo=demo&lat=-23&lon=-46&raio_m=9000').status_code==422
    assert client.get('/api/zeladoria/fila?modo=demo&status=naoexiste').status_code==422
    assert client.patch('/api/zeladoria/triagem/DEMO-001').status_code==405
    assert client.post('/api/cidadao/proximos').status_code==405

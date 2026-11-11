from app.operacao import carregar_relatos,painel,resumo_relato,vizinhos,gerar_relatorio,distancia_m
from app.main import app
from fastapi.testclient import TestClient

client=TestClient(app)

def test_demo_rotulada():
    base=carregar_relatos('demo')
    assert base['modo']=='demo' and 'simulada' in base['fonte']
    assert len(base['relatos'])==9

def test_prioridade_e_dashboard():
    p=painel(carregar_relatos('demo'))
    assert p['total']==9 and p['fila_priorizada'][0]['id']=='DEMO-001'
    assert p['por_status']['pendente']==4

def test_triagem_nao_decide_status():
    b=carregar_relatos('demo')
    x=resumo_relato(b['relatos'],'DEMO-001')
    assert x['relato']['status']=='pendente' and 'humana' in x['acao_sugerida']
    assert any(y['id']=='DEMO-007' for y in x['proximidade']['possiveis_duplicatas'])

def test_proximidade_e_ausente():
    b=carregar_relatos('demo')['relatos']
    assert distancia_m(b[0],b[0])==0
    assert vizinhos(b,'DEMO-001')['possiveis_duplicatas']

def test_boletim_referencia_origem():
    r=gerar_relatorio(carregar_relatos('demo'))
    assert 'SIMULADO' in r and 'DEMO-001' in r and 'não equivale automaticamente' in r

def test_endpoints():
    assert client.get('/health').status_code==200
    assert client.get('/api/operacao/painel?modo=demo').json()['total']==9
    assert client.get('/api/operacao/relatos/DEMO-001/triagem?modo=demo').status_code==200
    assert client.get('/api/operacao/relatos/INVALIDO/triagem?modo=demo').status_code==404
    assert client.get('/api/operacao/boletim?modo=demo').status_code==200
    assert client.get('/').status_code==200

def test_sem_rotas_escrita():
    assert client.patch('/api/operacao/relatos/DEMO-001').status_code in {404,405}
    assert client.post('/api/operacao/relatos').status_code==405

def test_live_indisponivel_nao_usa_demo(monkeypatch):
    import app.operacao as op
    def falha(*args,**kwargs):raise op.requests.RequestException('offline')
    monkeypatch.setattr(op.requests,'get',falha)
    import pytest
    with pytest.raises(op.FonteIndisponivel):op.carregar_relatos('live')

def test_rascunho_nao_persiste():
    base=carregar_relatos('demo')
    r=client.post('/api/operacao/rascunho',json={'lat':-23.560345,'lon':-46.650508,'severidade':'alta','modo':'demo'})
    assert r.status_code==200
    data=r.json()
    assert data['enviado'] is False and data['persistido'] is False
    assert data['possiveis_relatos_existentes'][0]['id']=='DEMO-001'
    assert carregar_relatos('demo')['relatos']==base['relatos']

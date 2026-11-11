from app.operacao import carregar_relatos
from app.inteligencia_operacional import atender, selecionar_intencao
from fastapi.testclient import TestClient
from app.main import app

BASE=carregar_relatos('demo')

def test_revisao_e_prioridades():
    assert selecionar_intencao('zeladoria','Quais ocorrências precisam de revisão primeiro?',None,None,None)=='prioridades'

def test_resultado_operacional_e_fallback_identificado():
    # LLM retorna JSON inválido; dados continuam disponíveis, sem falsamente dizer que a IA respondeu.
    r=atender(BASE,'zeladoria','Quais ocorrências precisam de revisão primeiro?',generator=lambda _: 'texto inválido')
    assert r['dados_verificados']['top_5'][0]['id']=='DEMO-001'
    assert r['resposta_ia']['recusa']
    assert r['resposta_ia']['tipo_resposta']=='fallback_extrativo'
    assert r['resposta_ia']['gerada_por_llm'] is False
    assert 'DEMO-001' in r['resposta_ia']['resposta_verificada']

def test_sem_fallback_inventado_quando_nao_ha_evidencia():
    r=atender(BASE,'cidadao','Qual a previsão de reparo amanhã?',generator=lambda _: 'texto inválido')
    assert r['resposta_ia']['recusa']
    assert 'resposta_verificada' not in r['resposta_ia']

def test_endpoint_com_evidencias_operacionais():
    # Usa o comportamento real do backend, independentemente da resposta do Ollama.
    c=TestClient(app)
    r=c.post('/api/ia/atender',json={'papel':'zeladoria','pergunta':'Quais ocorrências precisam de revisão primeiro?','modo':'demo'})
    assert r.status_code==200
    assert r.json()['intencao']=='prioridades'
    assert r.json()['dados_verificados']['top_5'][0]['id']=='DEMO-001'

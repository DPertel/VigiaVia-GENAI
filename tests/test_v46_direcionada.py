import json
import pytest
from app import core
from app.inteligencia_operacional import _verificar_resposta, gerar_orientacao, evidencias_operacionais
from app.verificador_semantico import validate


def test_devsecops_rejeita_dataset_fora_de_contexto():
    doc = core.KB.by_id['V13']
    resposta = 'Gitleaks, Semgrep, pytest, Trivy e SBOM. RDD2022 detecta vulnerabilidades.'
    ok, motivo = validate('Como o pipeline DevSecOps verifica o código?', resposta, [doc])
    assert not ok and 'fora da fonte' in motivo


def test_devsecops_aceita_ferramentas_documentadas():
    doc = core.KB.by_id['V13']
    resposta = 'O pipeline executa Gitleaks, Semgrep, pytest, Docker Compose, Trivy e SBOM.'
    assert validate('Como o pipeline DevSecOps verifica o código?', resposta, [doc])[0]


def test_agente_fonte_decisiva_sem_misturar_rdd2022(monkeypatch):
    prompts=[]
    def fake(prompt):
        prompts.append(prompt)
        return json.dumps({'resposta':'O pipeline executa Gitleaks, Semgrep, pytest, Docker Compose, Trivy e SBOM.',
                           'fontes':['V13'], 'recusa':False})
    monkeypatch.setattr(core,'generate',fake)
    out=core.answer('Como o pipeline DevSecOps verifica o código?',mode='agente')
    assert not out['recusa'] and out['gerada_por_llm']
    assert 'RDD2022' not in prompts[0]
    assert out['fontes'] == ['V13']


def test_contradicao_nao_vira_fallback_extrativo(monkeypatch):
    monkeypatch.setattr(core,'generate',lambda _:json.dumps({'resposta':'Sim, exige login.', 'fontes':['V10'], 'recusa':False}))
    out=core.answer('A fila da zeladoria exige login no MVP?', mode='agente')
    assert out['recusa'] and not out['fontes']


def test_recusa_sem_resposta_pode_extrair_sem_fingir_llm(monkeypatch):
    monkeypatch.setattr(core,'generate',lambda _:json.dumps({'resposta':'não consta','fontes':[],'recusa':True}))
    out=core.answer('Qual problema o VigiaVia resolve?',mode='agente')
    assert not out['recusa']
    assert out['tipo_resposta'] == 'fallback_extrativo'
    assert out['gerada_por_llm'] is False


def test_z03_resposta_curta_aprovada_e_total_errado_rejeitado():
    ev=[{'id':'FILA', 'texto':'A consulta contém 9 relato(s), 4 pendente(s), 2 confirmado(s), 2 resolvido(s) e 4 de alta severidade.'}]
    assert _verificar_resposta('A consulta contém 9 relatos.',ev,'Quantos relatos estão na amostra?')[0]
    assert not _verificar_resposta('A consulta contém 4 relatos.',ev,'Quantos relatos estão na amostra?')[0]
    assert not _verificar_resposta('A consulta contém 9 relatos e 30 resolvidos.',ev,'Quantos relatos estão na amostra?')[0]


def test_z03_prompt_conciso_e_contagem_gerada():
    ev=[{'id':'FILA','texto':'A consulta contém 9 relato(s), 4 pendente(s), 2 confirmado(s), 2 resolvido(s) e 4 de alta severidade.'}]
    prompts=[]
    def fake(p):
        prompts.append(p)
        return json.dumps({'resposta':'A consulta contém 9 relatos.','recusa':False})
    out=gerar_orientacao('Quantos relatos estão na amostra?',ev,'zeladoria',generator=fake)
    assert not out['recusa'] and out['gerada_por_llm']
    assert '4 pendente' not in prompts[0]

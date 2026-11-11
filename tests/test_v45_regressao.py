"""Regressões baseadas em fatos documentais; não são gabaritos injetados na LLM."""
import json
import pytest
from app import core
from app.verificador_semantico import validate
from app.inteligencia_operacional import atender
from app.operacao import carregar_relatos

@pytest.mark.parametrize('resposta', [
    "Sim, na versão MVP a fila requer login. O documento menciona que 'a fila da zeladoria não tem autenticação', mas Entra ID será usado.",
    'A fila da zeladoria exige login e usuários devem autenticar-se.',
    'Login é obrigatório para a fila da zeladoria no MVP.',
    'Sim, o MVP exige autenticação. O Entra ID é futuro.',
])
def test_login_contradicao_composta_bloqueada(resposta):
    ok, _=validate('A fila da zeladoria exige login no MVP?',resposta,[core.KB.by_id['V10']])
    assert not ok

@pytest.mark.parametrize('resposta',[
    'No MVP a fila da zeladoria não tem autenticação; para produção há previsão de Entra ID.',
    'A fila da zeladoria no MVP não exige login, mas o Entra ID está previsto para produção.',
])
def test_login_negacao_documentada_aceita(resposta):
    ok, motivo=validate('A fila da zeladoria exige login no MVP?',resposta,[core.KB.by_id['V10']])
    assert ok,motivo

def test_agente_nao_aceita_citacao_com_afirmacao_contraditoria(monkeypatch):
    texto='Sim, a fila requer login. A documentação afirma que "a fila da zeladoria não tem autenticação".'
    monkeypatch.setattr(core,'generate',lambda _:json.dumps({'resposta':texto,'fontes':['V10'],'recusa':False}))
    out=core.answer('A fila da zeladoria exige login no MVP?','agente')
    assert out['recusa']

def test_agente_t12_fallback_literal_marcado_como_nao_llm(monkeypatch):
    monkeypatch.setattr(core,'generate',lambda _:json.dumps({'resposta':'não consta','recusa':True,'fontes':[]}))
    out=core.answer('Como o pipeline DevSecOps verifica o código?','agente')
    assert not out['recusa']
    assert not out['gerada_por_llm']
    assert out['tipo_resposta']=='fallback_extrativo'
    assert all(term in out['resposta'] for term in ('Gitleaks','Semgrep','pytest','Trivy','SBOM'))

def test_t01_resposta_extra_longa_bloqueada():
    question='Qual problema o VigiaVia resolve?'
    frase='O VigiaVia enfrenta buracos nas vias; chamados manuais são lentos e duplicados.'
    assert validate(question,frase,[core.KB.by_id['V01']])[0]
    assert not validate(question,frase+' ' + ('Detalhes não solicitados. ' * 100),[core.KB.by_id['V01']])[0]

def test_z03_terceira_tentativa_gera_resposta_real():
    n=iter([{'resposta':'não consta','recusa':True},
            {'resposta':'não consta','recusa':True},
            {'resposta':'A consulta contém 9 relatos.','recusa':False}])
    base=carregar_relatos('demo')
    out=atender(base,'zeladoria','Quantos relatos estão na amostra?',generator=lambda _:json.dumps(next(n)))
    assert not out['resposta_ia']['recusa']
    assert out['resposta_ia']['gerada_por_llm']
    assert out['resposta_ia']['tentativas']==3

def test_z03_contagem_falsa_nao_e_aceita():
    base=carregar_relatos('demo')
    out=atender(base,'zeladoria','Quantos relatos estão na amostra?',generator=lambda _:json.dumps({'resposta':'Há 10 relatos.','recusa':False}))
    assert out['resposta_ia']['recusa']
    assert out['resposta_ia']['tipo_resposta']=='fallback_extrativo'

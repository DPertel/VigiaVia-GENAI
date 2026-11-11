"""VigiaVia GenAI Operacional: relatórios e triagem com base operacional somente leitura."""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from .core import KB, answer
from .operacao import carregar_relatos,painel,resumo_relato,vizinhos,gerar_relatorio,resposta_operacional,rascunho_cidadao,FonteIndisponivel
from .portais import consultar_proximos, acompanhar, fila_zeladoria, ficha_triagem

app=FastAPI(title='VigiaVia GenAI — Cidadão e Zeladoria',version='3.0.0',description='Análise da fila VigiaVia + RAG local, sem operações de escrita')
class Pergunta(BaseModel):
    pergunta: str=Field(min_length=3,max_length=500)
    configuracao: str='agente'
class Rascunho(BaseModel):
    lat:float=Field(ge=-90,le=90)
    lon:float=Field(ge=-180,le=180)
    severidade:str
    modo:str='demo'

class Orientacao(BaseModel):
    pergunta: str=Field(min_length=3,max_length=500)
    configuracao: str='agente'
    modo: str='demo'
    relato_id: str|None=None

@app.get('/health')
def health():return {'status':'ok','versao':'3.0.0','trechos':len(KB.docs),'modo_padrao':'demo'}

@app.get('/api/buscar')
def buscar(q:str=Query(min_length=3,max_length=500)):return {'resultados':KB.search(q,3)}

@app.post('/api/perguntar')
def perguntar(req:Pergunta):
    if req.configuracao not in {'baseline','rag','agente'}:raise HTTPException(400,'Configuração inválida')
    try:return answer(req.pergunta,req.configuracao)
    except Exception as e:raise HTTPException(503,'Ollama indisponível ou resposta inválida. Verifique o servidor local.') from e

def _dados(modo:str):
    try:return carregar_relatos(modo)
    except ValueError as e:raise HTTPException(422,str(e)) from e
    except FonteIndisponivel as e:raise HTTPException(503,str(e)) from e

@app.get('/api/operacao/relatos')
def relatos(modo:str='demo', status:str|None=None):
    base=_dados(modo)
    if status:base['relatos']=[r for r in base['relatos'] if r['status']==status]
    return base

@app.get('/api/operacao/painel')
def dashboard(modo:str='demo', status:str|None=None):return painel(_dados(modo),status)

@app.get('/api/operacao/relatos/{rid}/triagem')
def triagem(rid:str,modo:str='demo'):
    try:
        base=_dados(modo)
        return {'fonte':base['fonte'],'modo':modo,**resumo_relato(base['relatos'],rid)}
    except KeyError as e:raise HTTPException(404,str(e)) from e

@app.get('/api/operacao/relatos/{rid}/proximos')
def proximos(rid:str,modo:str='demo',raio_m:float=Query(15,ge=1,le=100)):
    try:return vizinhos(_dados(modo)['relatos'],rid,raio_m)
    except KeyError as e:raise HTTPException(404,str(e)) from e

@app.get('/api/operacao/boletim',response_class=PlainTextResponse)
def boletim(modo:str='demo'):
    return PlainTextResponse(gerar_relatorio(_dados(modo)),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':'attachment; filename="boletim_vigiavia.md"'})

@app.post('/api/operacao/rascunho')
def preparar_rascunho(req:Rascunho):
    try:return rascunho_cidadao(req.lat,req.lon,req.severidade,_dados(req.modo))
    except ValueError as e:raise HTTPException(422,str(e)) from e

@app.post('/api/operacao/assistente')
def assistente(req:Orientacao):
    """Contexto da fila factual e determinístico; LLM só para documentação, nunca para inferir fatos operacionais."""
    if req.configuracao not in {'baseline','rag','agente'}:raise HTTPException(400,'Configuração inválida')
    base=_dados(req.modo); facts=painel(base)
    detalhe=None
    if req.relato_id:
        try:detalhe=resumo_relato(base['relatos'],req.relato_id)
        except KeyError as e:raise HTTPException(404,'Relato não encontrado') from e
    # A pergunta é respondida pela LLM apenas a respeito dos documentos, com origem separada dos dados.
    try:documental=answer(req.pergunta,req.configuracao)
    except Exception:
        documental={'configuracao':req.configuracao,'resposta':'Modelo Ollama indisponível','fontes':[],'recusa':True,'justificativa':'Dados da fila permanecem consultáveis.'}
    operacional=resposta_operacional(req.pergunta,base,req.relato_id)
    return {'pergunta':req.pergunta,'resposta_operacional':operacional,'documentacao':documental,'estado_da_fila':{'origem':facts['origem'],'modo':facts['modo'],'total':facts['total'],'por_status':facts['por_status'],'por_severidade':facts['por_severidade'],'top_5':facts['fila_priorizada'][:5]},'triagem':detalhe,'aviso':'Respostas documentais da LLM são separadas dos indicadores operacionais verificados; não há execução automática de ações.'}

@app.get('/',response_class=HTMLResponse)
def index():return Path(__file__).with_name('index.html').read_text(encoding='utf-8')


# ------------------------ Portal do cidadão (leitura + rascunho sem envio)
@app.get('/api/cidadao/proximos')
def cidadao_proximos(lat:float=Query(ge=-90,le=90),lon:float=Query(ge=-180,le=180),
                    raio_m:float=Query(300,ge=10,le=2000),modo:str='demo',somente_ativos:bool=False):
    try:return consultar_proximos(_dados(modo),lat,lon,raio_m,somente_ativos)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.get('/api/cidadao/acompanhar/{rid}')
def cidadao_acompanhar(rid:str,modo:str='demo'):
    try:return acompanhar(_dados(modo),rid)
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc

# ------------------------ Portal da zeladoria (apenas leitura)
@app.get('/api/zeladoria/fila')
def zeladoria_fila(modo:str='demo',status:str|None=None,severidade:str|None=None):
    try:return fila_zeladoria(_dados(modo),status,severidade)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.get('/api/zeladoria/triagem/{rid}')
def zeladoria_triagem(rid:str,modo:str='demo'):
    try:return ficha_triagem(_dados(modo),rid)
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc

# ------------------------ V4: agente com ferramentas e explicação local auditável
from .inteligencia_operacional import atender as atender_ia  # noqa: E402
from typing import Literal

class PedidoIA(BaseModel):
    papel: Literal['cidadao','zeladoria']
    pergunta: str = Field(min_length=3,max_length=500)
    modo: Literal['demo','live'] = 'demo'
    relato_id: str | None = Field(default=None,max_length=100)
    latitude: float | None = Field(default=None,ge=-90,le=90)
    longitude: float | None = Field(default=None,ge=-180,le=180)
    raio_m: float = Field(default=300,ge=10,le=2000)

@app.post('/api/ia/atender')
def ia_atender(req: PedidoIA):
    """Consulta operacional segura: somente leitura, sem inventar prazos ou alterar registros."""
    if (req.latitude is None) != (req.longitude is None):
        raise HTTPException(422,'Informe latitude e longitude juntas.')
    base=_dados(req.modo)
    try:
        return atender_ia(base,req.papel,req.pergunta,relato_id=req.relato_id,
                          latitude=req.latitude,longitude=req.longitude,raio_m=req.raio_m)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

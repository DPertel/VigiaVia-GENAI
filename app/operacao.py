"""Análise operacional READ-ONLY sobre o contrato /v1/relatos do VigiaVia.
A IA jamais atualiza o status nem chama endpoints de escrita do MVP.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json, math, os, requests

RAIZ = Path(__file__).resolve().parents[1]
PESO = {'baixa':1, 'media':2, 'alta':3}
STATUSES = {'pendente','confirmado','descartado','resolvido'}

class FonteIndisponivel(Exception):
    pass

def carregar_relatos(modo: str = 'demo') -> dict:
    if modo not in {'demo','live'}:
        raise ValueError('Modo inválido')
    if modo == 'demo':
        payload = json.loads((RAIZ/'dados'/'relatos_demo.json').read_text(encoding='utf-8'))
        fonte = 'Demonstração local (simulada; não é dado operacional real)'
    else:
        host = os.getenv('VIGIAVIA_API_URL', 'https://ca-vigiavia-prod.happywave-0bf5b4c3.brazilsouth.azurecontainerapps.io').rstrip('/')
        if not host.startswith('https://') and not (os.getenv('ALLOW_HTTP_LOCAL')=='true' and host.startswith('http://127.0.0.1:')):
            raise FonteIndisponivel('Use HTTPS para API externa ou HTTP localhost explicitamente autorizado.')
        try:
            res = requests.get(host+'/v1/relatos',params={'limite':1000},timeout=12,headers={'Accept':'application/json'})
            res.raise_for_status()
            payload = res.json()
        except (requests.RequestException, ValueError) as exc:
            raise FonteIndisponivel('Fila do VigiaVia indisponível; não foram usados dados de demonstração como substitutos.') from exc
        fonte = host+'/v1/relatos (consulta em tempo real, leitura somente)'
    raw = payload.get('relatos', [])
    if not isinstance(raw, list):
        raise FonteIndisponivel('Formato inválido em /v1/relatos')
    items = []
    for r in raw:
        if not isinstance(r,dict) or not all(k in r for k in ('id','status','severidade','lat','lon')):
            continue
        if r['status'] not in STATUSES or r['severidade'] not in PESO:
            continue
        # No máximo atributos operacionais autorizados. Nunca imagens / evidências ou observações livres.
        try:
            item = {k:r.get(k) for k in ('id','criado_em','atualizado_em','lat','lon','status','severidade','confirmacoes','confianca_max','origem','prioridade')}
            item['lat']=float(item['lat']); item['lon']=float(item['lon']); item['confirmacoes']=max(1,int(item['confirmacoes'] or 1))
            if not (-90<=item['lat']<=90 and -180<=item['lon']<=180):continue
            if item['prioridade'] is None:
                item['prioridade'] = round(PESO[item['severidade']] * (1+math.log2(item['confirmacoes'])),3)
            item['prioridade']=float(item['prioridade'])
            items.append(item)
        except (ValueError,TypeError):
            continue
    return {'modo': modo,'fonte': fonte, 'consultado_em':datetime.now(timezone.utc).isoformat(timespec='seconds'), 'total_declarado':payload.get('total'), 'parcial': isinstance(payload.get('total'),int) and payload['total']>len(raw), 'relatos':items}

def distancia_m(a,b):
    p1,p2 = math.radians(a['lat']),math.radians(b['lat'])
    dp=p2-p1; dl=math.radians(b['lon']-a['lon'])
    c=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*6371000*math.asin(min(1,math.sqrt(c)))

def vizinhos(relatos: list[dict], rid: str, raio:float=15) -> dict:
    alvo = next((r for r in relatos if r['id']==rid),None)
    if not alvo: raise KeyError('Relato não localizado')
    ocorrencias=[]
    for r in relatos:
        if r['id']==rid:continue
        d=distancia_m(alvo,r)
        if d<=raio:
            ocorrencias.append({'id':r['id'],'distancia_m':round(d,1),'status':r['status'],'severidade':r['severidade']})
    return {'relato_id':rid,'raio_m':raio,'possiveis_duplicatas':sorted(ocorrencias,key=lambda x:x['distancia_m']),'observacao':'Proximidade não comprova que se trata do mesmo buraco; a validação é humana.'}

def painel(base:dict, filtro_status:str|None=None) ->dict:
    rows=base['relatos']
    if filtro_status:rows=[r for r in rows if r['status']==filtro_status]
    status=dict(Counter(r['status'] for r in rows)); severidade=dict(Counter(r['severidade'] for r in rows))
    total_confirmacoes=sum(r['confirmacoes'] for r in rows)
    fila=sorted(rows,key=lambda r:(-r['prioridade'], r['criado_em'] or '',r['id']))
    return {'origem':base['fonte'],'modo':base['modo'],'consultado_em':base['consultado_em'],'amostra_parcial':base['parcial'], 'total':len(rows), 'por_status':status,'por_severidade':severidade,'confirmacoes_registradas':total_confirmacoes,'confirmacoes_adicionais':sum(max(0,r['confirmacoes']-1) for r in rows),'fila_priorizada':fila}

def resumo_relato(relatos:list[dict],rid:str)->dict:
    r=next((x for x in relatos if x['id']==rid),None)
    if not r:raise KeyError('Relato não localizado')
    proximos=vizinhos(relatos,rid)
    motivos=[f"Severidade classificada como {r['severidade']}",f"{r['confirmacoes']} confirmação(ões) agregada(s)",f"Prioridade calculada pelo MVP: {r['prioridade']}"]
    if r['status'] in {'descartado','resolvido'}:
        status_acao='Ocorrência encerrada; não sugerir nova intervenção sem análise humana.'
    else:
        status_acao='Revisão humana da ocorrência e da evidência no painel de zeladoria.'
    return {'relato':r,'criterios':motivos,'acao_sugerida':status_acao,'proximidade':proximos,'observacoes':['A prioridade é um indicador de fila, não uma garantia de prazo.','A IA não diagnostica risco estrutural e não altera o status.']}

def gerar_relatorio(base:dict)->str:
    p=painel(base); lines=[f"# Boletim de zeladoria — VigiaVia",'',f"**Fonte:** {p['origem']}", f"**Consulta (UTC):** {p['consultado_em']}",f"**Modo:** {p['modo']} {'(SIMULADO)' if p['modo']=='demo' else '(LEITURA DA API)'}",'',f"## Indicadores da fila",f"- Total de relatos consultados: **{p['total']}**",f"- Distribuição por status: {json.dumps(p['por_status'],ensure_ascii=False)}",f"- Distribuição por severidade: {json.dumps(p['por_severidade'],ensure_ascii=False)}",f"- Confirmações adicionais agregadas: {p['confirmacoes_adicionais']}", '', '## Ocorrências priorizadas (top 10)', '', '| ID | Status | Severidade | Confirmações | Prioridade |', '|---|---|---|---:|---:|']
    for r in p['fila_priorizada'][:10]:
        lines.append(f"| `{r['id']}` | {r['status']} | {r['severidade']} | {r['confirmacoes']} | {r['prioridade']:.3f} |")
    lines += ['', '## Interpretação e limitações', '- Ordenação reproduz o campo `prioridade` retornado pelo MVP; não substitui inspeção humana.', '- O número de confirmações adicionais não equivale automaticamente a duplicatas evitadas em produção.', '- Status `resolvido` significa classificação cadastrada; não comprova execução de obra, sem auditoria externa.', '- Não são inferidos endereço, prazo, responsável, risco de acidente nem custo de reparo.', '- Consultas não modificam a fila do VigiaVia.']
    if p['amostra_parcial']:lines.append('- **ATENÇÃO:** a API indicou mais relatos do que os recuperados; estatísticas sobre amostra parcial.')
    return '\n'.join(lines)+'\n'

def resposta_operacional(pergunta:str, base:dict, relato_id:str|None=None) -> dict:
    """Camada de ferramentas determinísticas para perguntas sobre a fila.
    Não inventa estatísticas e retorna a consulta auditável com sua origem.
    """
    import unicodedata
    def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
    q=norm(pergunta)
    p=painel(base)
    if relato_id:
        try:
            info=resumo_relato(base['relatos'],relato_id)
            t=info['relato']
            msg=(f"Relato {relato_id}: status {t['status']}, severidade {t['severidade']}, "
                f"{t['confirmacoes']} confirmação(ões) e prioridade {t['prioridade']:.3f}. "
                f"{info['acao_sugerida']}")
            return {'resposta':msg,'fontes':[base['fonte'],f'relato:{relato_id}'],'tipo':'dados_operacionais','verificado':True,'triagem':info}
        except KeyError:pass
    if any(x in q for x in ('quantos','quantas','total','numero','resumo','situacao','fila','painel','estatistica','relatorio')):
        msg=(f"Na consulta atual há {p['total']} relato(s): "
            f"{p['por_status'].get('pendente',0)} pendente(s), "
            f"{p['por_status'].get('confirmado',0)} confirmado(s), "
            f"{p['por_status'].get('resolvido',0)} resolvido(s) e "
            f"{p['por_status'].get('descartado',0)} descartado(s). "
            f"Severidade alta: {p['por_severidade'].get('alta',0)}. "
            f"São {p['confirmacoes_adicionais']} confirmações adicionais agregadas.")
        return {'resposta':msg,'fontes':[base['fonte']],'tipo':'dados_operacionais','verificado':True}
    if any(x in q for x in ('priorit','urgente','grave','critico','primeiro','atencao')):
        ativos=[r for r in p['fila_priorizada'] if r['status'] in {'pendente','confirmado'}]
        if not ativos:msg='Não há relatos ativos na consulta atual.'
        else:
            top=ativos[0];msg=(f"A primeira ocorrência ativa na fila calculada é {top['id']}, "
                     f"com severidade {top['severidade']}, {top['confirmacoes']} confirmação(ões) "
                     f"e prioridade {top['prioridade']:.3f}. Isso não garante prazo de reparo; "
                     f"é necessária validação humana.")
        return {'resposta':msg,'fontes':[base['fonte']],'tipo':'dados_operacionais','verificado':True}
    return {'resposta':'Pergunta operacional não identificada. Selecione um relato para triagem ou pergunte sobre quantidade, prioridades e status.', 'fontes':[base['fonte']],'tipo':'orientacao_navegacao','verificado':False}

def rascunho_cidadao(lat:float,lon:float,severidade:str,base:dict,confianca:float=0.5)->dict:
    """Prepara, SEM ENVIAR, um registro compatível com POST /v1/relatos do MVP.

    O campo confianca_max é obrigatório na API original e não deve ser inventado
    como confiança do detector; um relato manual precisa ser marcado como valor
    ainda não aferido. Retornar somente um rascunho não persistido.
    """
    if not -90<=lat<=90 or not -180<=lon<=180 or severidade not in PESO or not 0<=confianca<=1:
        raise ValueError('Coordenadas, severidade ou confiança inválidas')
    candidato={'lat':lat,'lon':lon}
    proximos=[]
    for r in base['relatos']:
        d=distancia_m(candidato,r)
        if d<=15 and r['status'] in {'pendente','confirmado'}:
            proximos.append({'id':r['id'],'distancia_m':round(d,1),'status':r['status']})
    return {'enviado':False,'persistido':False,'modo':base['modo'],'aviso':'Rascunho NÃO enviado. A API exige confianca_max; 0.5 é somente valor ilustrativo, não confiança medida por detector. Conferir antes de registrar manualmente.', 'relato_para_revisao':{'lat':lat,'lon':lon,'severidade':severidade,'confianca_max':confianca,'origem':'cidadao'},'possiveis_relatos_existentes':sorted(proximos,key=lambda x:x['distancia_m'])}

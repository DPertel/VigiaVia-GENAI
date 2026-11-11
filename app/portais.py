"""Serviços compartilhados dos portais de cidadão e zeladoria.

Consultas somente leitura à fila do MVP. Preparação de relato nunca é envio.
"""
from __future__ import annotations
from .operacao import distancia_m, painel, resumo_relato

ATIVOS = {'pendente', 'confirmado'}

def consultar_proximos(base: dict, lat: float, lon: float, raio_m: float = 300, somente_ativos: bool = False) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Coordenadas inválidas')
    if not (10 <= raio_m <= 2000):
        raise ValueError('Raio deve ficar entre 10 e 2000 metros')
    ponto = {'lat': lat, 'lon': lon}
    proximos = []
    for relato in base['relatos']:
        if somente_ativos and relato['status'] not in ATIVOS:
            continue
        distancia = distancia_m(ponto, relato)
        if distancia <= raio_m:
            proximos.append({
                'id': relato['id'], 'status': relato['status'], 'severidade': relato['severidade'],
                'distancia_m': round(distancia, 1), 'confirmacoes': relato['confirmacoes'],
                'prioridade': relato['prioridade'], 'lat': relato['lat'], 'lon': relato['lon'],
            })
    proximos.sort(key=lambda x:(x['distancia_m'], x['id']))
    return {
        'modo': base['modo'], 'fonte': base['fonte'], 'consultado_em': base['consultado_em'],
        'local_consulta': {'lat':lat,'lon':lon,'raio_m':raio_m}, 'total': len(proximos),
        'relatos': proximos,
        'aviso': 'A proximidade é geográfica; não comprova que o problema está na mesma faixa ou via. Em modo demo, todas as ocorrências são simuladas.'
    }

def acompanhar(base: dict, rid: str) -> dict:
    relato = next((r for r in base['relatos'] if r['id'] == rid), None)
    if not relato:
        raise KeyError('Relato não encontrado na consulta atual')
    mensagens = {
        'pendente': 'Registro na fila; ainda depende de validação humana.',
        'confirmado': 'Registro confirmado na fila; isso não estabelece data de reparo.',
        'descartado': 'Registro descartado na fila; a justificativa não está disponível neste módulo.',
        'resolvido': 'Registro marcado como resolvido; a API não comprova execução física da obra.'
    }
    return {
        'modo': base['modo'], 'fonte': base['fonte'], 'consultado_em': base['consultado_em'],
        'relato': {k:relato.get(k) for k in ('id','status','severidade','lat','lon','criado_em','atualizado_em','confirmacoes','prioridade')},
        'explicacao_status': mensagens[relato['status']],
        'aviso': 'Não há previsão de reparo, nome de responsável nem rastreio de solicitação por usuário na API consultada.'
    }

def fila_zeladoria(base: dict, status: str | None = None, severidade: str | None = None) -> dict:
    if status and status not in {'pendente','confirmado','descartado','resolvido'}:
        raise ValueError('Status inválido')
    if severidade and severidade not in {'baixa','media','alta'}:
        raise ValueError('Severidade inválida')
    filtrados = [r for r in base['relatos'] if (not status or r['status']==status) and (not severidade or r['severidade']==severidade)]
    base_filtrada={**base,'relatos':filtrados}
    resultado=painel(base_filtrada)
    resultado['filtros']={'status':status,'severidade':severidade}
    resultado['avisos']=['Ordenação reflete a prioridade numérica da API; a decisão é humana.', 'Não altera status nem envia relatos ao MVP.']
    return resultado

def ficha_triagem(base: dict, rid: str) -> dict:
    d = resumo_relato(base['relatos'],rid)
    return {
        **d, 'modo':base['modo'],'fonte':base['fonte'],'consultado_em':base['consultado_em'],
        'analise': {
            'severidade_reportada':d['relato']['severidade'],
            'prioridade_no_mvp':d['relato']['prioridade'],
            'confirmacoes':d['relato']['confirmacoes'],
            'possiveis_duplicidades_15m':len(d['proximidade']['possiveis_duplicatas']),
            'recomendacao':'Revisar evidência e localização no painel original antes de validar ou encerrar.',
        },
        'integracao':'Somente leitura. Para mudar status use o portal original do MVP após autenticação institucional em produção.'
    }

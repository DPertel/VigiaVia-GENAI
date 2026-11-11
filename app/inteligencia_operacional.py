"""Agente de IA com ferramentas para dois papéis, evidências e validação.

O agente NÃO executa ações na fila e NÃO transforma o texto da LLM em dados oficiais.
Duas camadas: ferramenta determinística produz fatos; Ollama redige uma orientação
apenas se comprovar com trecho literal e referências válidas. Não usa dados pessoais.
"""
from __future__ import annotations
import json
import re
from typing import Any, Literal
from . import core
from .operacao import painel, resumo_relato, vizinhos, distancia_m

PAPEIS = {'cidadao', 'zeladoria'}
INTENCOES = {'proximidade', 'acompanhar', 'relato', 'prioridades', 'indicadores', 'orientacao'}


def _recusa(motivo: str, dados: dict | None = None) -> dict:
    return {'resposta': 'não consta', 'fontes': [], 'recusa': True,
            'justificativa': motivo, 'evidencia_literal': '', 'proximos_passos': [],
            'fatos_verificados': dados or {}}


def selecionar_intencao(papel: str, pergunta: str, relato_id: str | None,
                        latitude: float | None, longitude: float | None) -> str:
    import unicodedata
    q = ''.join(c for c in unicodedata.normalize('NFKD', pergunta.casefold()) if not unicodedata.combining(c))
    if relato_id:
        return 'acompanhar' if papel == 'cidadao' else 'relato'
    if latitude is not None and longitude is not None:
        return 'proximidade'
    if papel == 'zeladoria' and any(w in q for w in ('priorid', 'priorit', 'urgente', 'grave', 'primeiro', 'lidera', 'lider', 'topo da fila', 'ordem da fila', 'ocorrencia ativa', 'critico', 'pendente', 'revisao', 'revisar', 'atencao', 'necessitam', 'precisam', 'triagem')):
        return 'prioridades'
    if any(w in q for w in ('quantos', 'quantas', 'total', 'indicador', 'estatistica', 'resumo da fila', 'quantidade', 'visao geral', 'situacao da fila', 'amostra', 'contagem')):
        return 'indicadores'
    return 'orientacao'


def evidencias_operacionais(base: dict, papel: str, intencao: str,
                             relato_id: str | None = None, latitude: float | None = None,
                             longitude: float | None = None, raio_m: float = 300) -> dict:
    """Constrói um contexto seguro somente de dados operacionais verificados."""
    if papel not in PAPEIS or intencao not in INTENCOES:
        raise ValueError('Papel ou intenção inválida')
    rows = base['relatos']
    origem = base['fonte']
    if intencao == 'orientacao':
        return {'fatos': {}, 'evidencias': [], 'mensagem': 'Pergunta documental: consultar a base de conhecimento.'}
    if intencao == 'proximidade':
        if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError('Informe latitude e longitude válidas')
        if not 10 <= raio_m <= 2000:
            raise ValueError('Raio fora do intervalo')
        proximos=[]
        for r in rows:
            d=distancia_m({'lat':latitude,'lon':longitude},r)
            if d<=raio_m:
                proximos.append({'id':r['id'],'distancia_m':round(d,1),'status':r['status'],'severidade':r['severidade']})
        proximos.sort(key=lambda r:r['distancia_m'])
        status_counts={k:sum(x['status']==k for x in proximos) for k in ('pendente','confirmado','resolvido','descartado')}
        ativos=status_counts['pendente']+status_counts['confirmado']
        facts={'raio_m':raio_m,'quantidade':len(proximos),'ativos':ativos,'por_status':status_counts,'ocorrencias':proximos[:15]}
        msg=(f'A consulta retornou {len(proximos)} relato(s) a até {raio_m:g} metros do ponto informado: '
             f'{ativos} ativo(s), {status_counts["resolvido"]} resolvido(s) e {status_counts["descartado"]} descartado(s).')
        return {'fatos':facts,'evidencias':[{'id':'FILA','texto':msg+' '+ ' '.join(f"Relato {r['id']}: status {r['status']}, severidade {r['severidade']}, distância {r['distancia_m']} metros." for r in proximos[:5]),'origem':origem}], 'mensagem':msg}
    if intencao in {'acompanhar','relato'}:
        if not relato_id:raise ValueError('Informe o ID do relato')
        try: item=resumo_relato(rows,relato_id)
        except KeyError: return {'fatos':{'id_pesquisado':relato_id},'evidencias':[],
                                 'mensagem':'Nenhum relato com esse ID foi localizado na consulta.'}
        r=item['relato']; close=item['proximidade']['possiveis_duplicatas']
        facts={'id':r['id'],'status':r['status'],'severidade':r['severidade'],
               'confirmacoes':r['confirmacoes'],'prioridade':r['prioridade'],
               'possiveis_duplicatas':close}
        msg=(f"O relato {r['id']} está com status {r['status']}, severidade {r['severidade']}, "
             f"{r['confirmacoes']} confirmação(ões) e prioridade {r['prioridade']:.3f}.")
        if papel == 'zeladoria' and close:
            msg += (' Há possível proximidade com '+', '.join(z['id'] for z in close)
                    + '; isso não confirma duplicidade e exige revisão humana.')
        evidence=[{'id':f"RELATO:{r['id']}",'texto':msg,'origem':origem}]
        if close:
            evidence.append({'id':f"PROX:{r['id']}",'texto':f"Há {len(close)} possível(is) relato(s) próximo(s) a até 15 metros: " + ', '.join(f"{z['id']} a {z['distancia_m']} metros" for z in close) + '. Proximidade não confirma duplicidade; exige revisão humana.','origem':origem})
        return {'fatos':facts,'evidencias':evidence,'mensagem':msg}
    p=painel(base)
    if intencao == 'indicadores':
        facts={'total':p['total'],'status':p['por_status'],'severidade':p['por_severidade'],
               'confirmacoes_adicionais':p['confirmacoes_adicionais'],'parcial':p['amostra_parcial']}
        msg=(f"A consulta contém {p['total']} relato(s), "
             f"{p['por_status'].get('pendente',0)} pendente(s), "
             f"{p['por_status'].get('confirmado',0)} confirmado(s), "
             f"{p['por_status'].get('resolvido',0)} resolvido(s) e "
             f"{p['por_severidade'].get('alta',0)} de alta severidade.")
    else:
        ativos=[x for x in p['fila_priorizada'] if x['status'] in {'pendente','confirmado'}]
        facts={'total_ativos':len(ativos),'top_5':[{'id':r['id'],'status':r['status'],
               'severidade':r['severidade'],'prioridade':r['prioridade'],'confirmacoes':r['confirmacoes']} for r in ativos[:5]]}
        if ativos:
            a=ativos[0]
            msg=(f"Há {len(ativos)} relato(s) ativo(s). A primeira ocorrência na fila é {a['id']}, "
                 f"severidade {a['severidade']}, prioridade {a['prioridade']:.3f}, com {a['confirmacoes']} confirmação(ões).")
        else:msg='Não há relatos pendentes ou confirmados na consulta atual.'
    if intencao=='prioridades' and facts.get('top_5'):
        complemento=' '.join(f"Ocorrência {r['id']}: status {r['status']}, severidade {r['severidade']}, prioridade {r['prioridade']:.3f}, confirmações {r['confirmacoes']}." for r in facts['top_5'])
    else: complemento=''
    return {'fatos':facts,'evidencias':[{'id':'FILA','texto':msg+' '+complemento,'origem':origem}],'mensagem':msg}


def _normal(s: str) -> str:
    return ' '.join(s.split()).casefold()


def _verificar_resposta(resposta: str, evidencias: list[dict], pergunta: str) -> tuple[bool, str]:
    """Filtro de suporte lexical, números e restrições de segurança.

    Não garante equivalência semântica; revisão humana permanece obrigatória.
    """
    import unicodedata
    if not resposta or resposta.strip().casefold() in {'não consta','nao consta','não sei','nao sei'}:
        return False, 'Modelo recusou a explicação.'
    if len(resposta) > 700:
        return False, 'Explicação excessivamente longa.'
    def norm(t):
        return ''.join(c for c in unicodedata.normalize('NFKD',t.casefold()) if not unicodedata.combining(c))
    ans=norm(resposta); fontes=norm(' '.join(e['texto'] for e in evidencias))
    if any(x in ans for x in ('prazo garantido','sera reparado amanha','conserto confirmado',
                              'obra ja executada','funcionario responsavel','custo estimado', 'atencao imediata', 'atendimento imediato', 'reparo imediato', 'obrigatoriamente urgente')):
        return False, 'Afirmação não permitida ou não verificável.'
    nums_ans=set(re.findall(r'\d+(?:[.,]\d+)?', resposta))
    nums_src=set(re.findall(r'\d+(?:[.,]\d+)?',' '.join(e['texto'] for e in evidencias)))
    if not nums_ans.issubset(nums_src):
        return False, 'Número ou identificador numérico ausente da fonte.'
    # Proteção adicional para asserções opostas ao status que consta na base.
    status_mention = re.findall(r'\b(?:pendente|confirmado|resolvido|descartado)\b', ans)
    for status in status_mention:
        if status not in fontes:
            return False, 'Status sem fonte.'
    # Menção ao ID mais importante é obrigatória ao discutir prioridades de ocorrências.
    if 'priorid' in norm(pergunta) or 'revisao' in norm(pergunta) or 'revisar' in norm(pergunta):
        ids=re.findall(r'\bDEMO-\d+\b|\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b',' '.join(e['texto'] for e in evidencias))
        if ids and not any(x.casefold() in resposta.casefold() for x in ids):
            return False, 'Explicação não identificou uma ocorrência registrada.'
    stop={'a','o','as','os','de','do','da','dos','das','um','uma','com','para','que','por','em','no','na',
          'e','sao','foi','ser','tem','mais','menos','deve','podem','sobre','se','ao','ate','esse','essa'}
    src_tokens={w for w in re.findall(r'[a-z]{4,}',fontes) if w not in stop}
    ans_tokens={w for w in re.findall(r'[a-z]{4,}',ans) if w not in stop}
    # Perguntas quantitativas curtas podem ser respondidas com 'São 9 relatos'.
    # Não exigir vocabulário extenso quando o total foi conferido na ferramenta.
    quantitative = any(w in norm(pergunta) for w in ('quantos', 'quantas', 'total', 'quantidade'))
    qtd_valida = bool(quantitative and nums_ans and nums_ans.issubset(nums_src)
                      and any(w in ans for w in ('relato', 'ocorrencia', 'registro', 'chamado')))
    # Para consulta de quantidade, o total canônico é a primeira contagem
    # retornada pela ferramenta ('A consulta contém 9 relatos'). Números de
    # status e severidade não podem substituir esse total.
    if quantitative and 'FILA' in [str(e.get('id')) for e in evidencias]:
        inicio = evidencias[0]['texto'].split('.')[0]
        match = re.search(r'\b(?:contem|retornou|ha)\s+(\d+)\s+relato', norm(inicio))
        if match:
            total = int(match.group(1))
            encontrados = [int(n) for n in re.findall(r'\b\d+\b', ans)]
            if total not in encontrados:
                return False, 'O total informado não corresponde ao total de relatos da ferramenta.'
            if any(n != total for n in encontrados):
                return False, 'Resposta de contagem introduziu números alheios à pergunta.'
            qtd_valida = any(w in ans for w in ('relato','ocorrencia','registro','chamado'))
    if len(src_tokens & ans_tokens)<2 and not qtd_valida:
        return False, 'Pouca correspondência com os fatos disponíveis.'
    # Para triagem, a análise precisa mencionar uma possível duplicidade quando
    # a própria ferramenta identificou um registro próximo, sem considerá-lo certo.
    ask=norm(pergunta)
    if 'triagem' in ask and any('PROX:' in e.get('id','') for e in evidencias):
        prox_ids=re.findall(r'(?i)\bDEMO-\d+\b', ' '.join(e['texto'] for e in evidencias if 'PROX:' in e.get('id','')))
        if prox_ids and not any(x.casefold() in resposta.casefold() for x in prox_ids):
            return False, 'Triagem incompleta: possível duplicidade não mencionada.'
        if prox_ids and not any(x in ans for x in ('proxim','possivel','duplic','revis')):
            return False, 'Triagem não advertiu que proximidade requer validação.'
    if ('quantos' in ask or 'quantas' in ask) and re.search(r'\b\d+\b',fontes):
        if not re.search(r'\b\d+\b',ans):
            return False, 'Resposta quantitativa omitiu contagem.'
    return True, 'Explicação passou pelas verificações automáticas de suporte.'


def gerar_orientacao(pergunta: str, evidencias: list[dict], papel: str,
                     *, generator=None) -> dict:
    """Ollama redige uma explicação; IDs e citação são derivados da ferramenta confiável.

    A LLM não precisa copiar o texto literal nem escolher IDs de fonte: esses
    campos são atribuídos pelo software ao contexto que efetivamente foi enviado.
    Nenhuma explicação é aprovada se o filtro de suporte falhar.
    """
    if not evidencias:
        return _recusa('Não há dados documentais/operacionais suficientes para responder.')
    generator=generator or core.generate
    pergunta_quantitativa = any(x in _normal(pergunta) for x in ('quantos', 'quantas', 'total', 'quantidade'))
    if pergunta_quantitativa and evidencias and evidencias[0]['id'] == 'FILA':
        primeira = evidencias[0]['texto'].split(',')[0].split('.')[0].strip() + '.'
        contexto = f'[FILA] {primeira}'
    else:
        contexto='\n'.join(f"[{e['id']}] {e['texto']}" for e in evidencias)
    esquema='{"resposta":"...","recusa":false}'
    instrucao=(
      'Você é um assistente especializado em mobilidade urbana, perfil '+papel+'. '
      'Explique a resposta de forma CURTA, clara e útil em português brasileiro. '
      'Use SOMENTE os FATOS VERIFICADOS. Não invente datas, custos, endereços, status, '
      'obras realizadas ou prazos. Se a evidência contém a informação, RESPONDA e não recuse. '
      'Não copie fontes, não cite URLs, não crie identificadores. '
      'Sua tarefa é EXPLICAR os fatos, não conferir referências. '
      'Responda APENAS JSON simples '+esquema+'. '
      'Quando informar contagem, use o total explícito do contexto. Quando avaliar triagem, cite possíveis registros próximos e diga que não são duplicidades confirmadas. Evite ordenar atenção imediata. '
      'DADOS VERIFICADOS:\n'+contexto+'\nPERGUNTA: '+pergunta)
    if pergunta_quantitativa and evidencias and evidencias[0]['id'] == 'FILA':
        instrucao = ('Responda à pergunta contando o total de relatos mostrado. '
           'Não inclua subtotais ou outras informações. '
           'Responda somente JSON: {"resposta":"A consulta contém N relatos.","recusa":false} '
           'substituindo N pelo número EXATO da evidência. '
           'EVIDÊNCIA: '+contexto+'\nPERGUNTA: '+pergunta)
    problemas=[]
    # Uma tentativa adicional somente para consultas de contagem; outras
    # perguntas continuam limitadas a duas gerações, mantendo latência.
    pergunta_quantitativa = any(x in _normal(pergunta) for x in ('quantos', 'quantas', 'total', 'quantidade'))
    max_tentativas = 3 if pergunta_quantitativa else 2
    for tentativa in range(max_tentativas):
        if tentativa == 0:
            prompt = instrucao
        else:
            complemento = ''
            ids_proximos = re.findall(r'(?:DEMO-\d+|[0-9a-fA-F-]{36})',
                ' '.join(e['texto'] for e in evidencias if str(e.get('id','')).startswith('PROX:')))
            if ids_proximos and 'triagem' in _normal(pergunta):
                complemento = ('Mencione explicitamente o registro próximo '+ids_proximos[0]
                               +' como POSSÍVEL duplicidade a ser revisada por uma pessoa, '
                               'NUNCA como duplicidade confirmada. ')
            if pergunta_quantitativa:
                inicio = evidencias[0]['texto'].split('.')[0]
                complemento += ('Pergunta de contagem, responda exclusivamente ao total da consulta. '
                                'A frase de referência é: '+inicio+'. '
                                'Use apenas uma frase curta, por exemplo estrutura: '
                                '"A consulta contém N relatos." substituindo N pelo total da fonte. '
                                'NÃO diga não consta quando existe um total explícito. ')
            prompt = ('A explicação anterior falhou na verificação: '+problemas[-1]+'. '
                      + complemento + 'Não introduza inferências. Use os dados literalmente. '
                      'Retorne APENAS JSON '+esquema+'\nDADOS VERIFICADOS:\n'+contexto
                      +'\nPERGUNTA: '+pergunta)
        raw=generator(prompt)
        val=core.parse_json(raw)
        if not isinstance(val,dict) or not val:
            problemas.append('JSON inválido');continue
        resposta=val.get('resposta','')
        if val.get('recusa') or not isinstance(resposta,str):
            problemas.append('O modelo optou por recusar');continue
        ok,causa=_verificar_resposta(resposta,evidencias,pergunta)
        if not ok:
            problemas.append(causa);continue
        # Fonte e evidência sempre são atribuídas pelo sistema, nunca inventadas pela LLM.
        referencias=[str(e['id']) for e in evidencias]
        evidencia_literal=evidencias[0]['texto']
        return {'resposta':resposta.strip(),'fontes':referencias,'recusa':False,
                'justificativa':'Explicação gerada pelo Ollama com fonte e evidência atribuídas pelo sistema; revisão humana necessária.',
                'evidencia_literal':evidencia_literal,'proximos_passos':[],
                'tentativas':tentativa+1,'verificacao':causa,'gerada_por_llm':True}
    return _recusa(f'Não foi possível validar a explicação do Ollama em {max_tentativas} tentativas: '+(problemas[-1] if problemas else 'sem resposta'))

def atender(base: dict, papel: str, pergunta: str, *, relato_id: str | None = None,
            latitude: float | None = None, longitude: float | None = None, raio_m:float=300,
            generator=None) -> dict:
    """Resposta ao cidadão/zeladoria, preservando evidência auditável e fatos brutos."""
    if papel not in PAPEIS:raise ValueError('Perfil inválido')
    # Não permita que perguntas não respondíveis sejam convertidas em um resumo
    # genérico de status; não delegue ações ou garantias à LLM.
    import unicodedata
    q=''.join(c for c in unicodedata.normalize('NFKD',pergunta.lower()) if not unicodedata.combining(c))
    proibido=any(w in q for w in ('prazo garantido','quando sera reparad','amanha','previsao de reparo',
         'custo exato','valor exato','telefone oficial','nome do agente','cpf',
         'altere o status','mude o status','marque como resolvido','atualize o status'))
    if proibido:
        return {'papel':papel,'intencao':'fora_do_escopo','modo':base['modo'],
                'fonte_operacional':base['fonte'],'consulta_utc':base['consultado_em'],
                'resposta_ia':_recusa('Não há evidência para garantir essa informação ou executar essa ação.'),
                'dados_verificados':{},'resumo_verificado':None,'evidencias':[],
                'requer_validacao_humana':True,
                'aviso':'Nenhum status foi alterado. A consulta não garante prazos, custos ou identificação de funcionários.'}
    intencao=selecionar_intencao(papel,pergunta,relato_id,latitude,longitude)
    dados=evidencias_operacionais(base,papel,intencao,relato_id,latitude,longitude,raio_m)
    if intencao == 'orientacao':
        # Reutiliza o RAG documental; o baseline e RAG simples seguem disponíveis
        # em /api/perguntar e são avaliados separadamente.
        docs=[d for d in core.KB.search(pergunta,5) if d['score']>=0.16]
        ev=[{'id':d['id'],'texto':d['texto'],'origem':d['url']} for d in docs]
    else:ev=dados['evidencias']
    if not ev: saida=_recusa('Ocorrência ou documento não localizado nesta consulta.')
    else:
        try: saida=gerar_orientacao(pergunta,ev,papel,generator=generator)
        except Exception: saida=_recusa('Ollama indisponível; os fatos operacionais ainda estão disponíveis.')
    # Se a LLM falha na citação, preservamos a recusa original mas exibimos
    # um resumo extrativo comprovado, SEM chamá-lo de geração por IA.
    if saida['recusa'] and intencao != 'orientacao' and dados['evidencias']:
        saida = {**saida, 'resposta_verificada': dados['mensagem'],
                 'tipo_resposta': 'fallback_extrativo', 'gerada_por_llm': False}
    else:
        saida = {**saida, 'tipo_resposta': 'geracao_validada' if not saida['recusa'] else 'recusa',
                 'gerada_por_llm': not saida['recusa']}
    return {'papel':papel,'intencao':intencao,'modo':base['modo'],
            'fonte_operacional':base['fonte'],'consulta_utc':base['consultado_em'],
            'resposta_ia':saida,'dados_verificados':dados['fatos'],
            'resumo_verificado':dados['mensagem'] if intencao!='orientacao' else None,
            'evidencias':[{'id':e['id'],'origem':e['origem'],'texto':e['texto']} for e in ev],
            'requer_validacao_humana':True,
            'aviso':'Não executa reparos, criação de chamados ou alteração de status. Dados demo são simulados.'}

"""Guardrails semânticos do domínio VigiaVia.

Regras independentes de casos de avaliação: sustentadas por documentos do corpus,
sem carregar gabaritos e sem usar IDs T01..T18. Uma citação presente não prova
consistência; o verificador checa obrigações factuais e afirmações contraditórias.
"""
from __future__ import annotations
import re
import unicodedata

def norm(text: str) -> str:
    t = unicodedata.normalize('NFKD', str(text).casefold())
    return ''.join(c for c in t if not unicodedata.combining(c))

def topical(question: str) -> str | None:
    q = norm(question)
    if any(x in q for x in ('autenticacao','login','entra id')) and any(x in q for x in ('fila','zeladoria','mvp')): return 'login'
    if any(x in q for x in ('internacional','nominatim','endereco')) and any(x in q for x in ('transferencia','pesquis','busca','nominatim')): return 'geocodificacao'
    if any(x in q for x in ('foto','imagem','logs','retencao')) and any(x in q for x in ('guard','armazen','log','retencao')): return 'privacidade'
    if any(x in q for x in ('fonte','dados do detector','dados dos relatos')) and any(x in q for x in ('trein','detector','relato','dados')): return 'dados'
    if any(x in q for x in ('deteccao','detect','envio dos relatos')) and any(x in q for x in ('zeladoria','relatos','buracos')): return 'fluxo'
    if any(x in q for x in ('devsecops','pipeline')): return 'devsecops'
    if ('vigiavia' in q or 'sistema' in q) and ('problema' in q or 'resolve' in q or 'objetivo' in q): return 'problema'
    if any(x in q for x in ('docker','executar local','iniciar a api')): return 'execucao'
    return None

# Regras de consistência documental explicitamente verificáveis. Não são saídas da LLM.
RULES = {
 'problema': {'doc':'V01','evidence':('buracos nas vias','chamados manuais'), 'required_any':(('buraco',),('manual','chamado'),('lento','lenta','impreciso','duplicad')),'forbidden':()},
 'login': {'doc':'V10','evidence':('nao tem autenticacao','entra id'), 'required_any':(('nao','sem'),('login','autenticacao')),
           'forbidden':('exige login','sim, exige','possui autenticacao','ja possui login')},
 'geocodificacao': {'doc':'V11','evidence':('transferencia internacional',), 'required_any':(('internacional','exterior'),('envia','transferencia','potencial','pode','nominatim')),
           'forbidden':('nao envolve transferencia internacional','nao ha transferencia internacional','sem transferencia internacional')},
 'privacidade': {'doc':'V09','evidence':('nao armazena as imagens','30 dias'), 'required_any':(('nao armazena','nao guarda','nao salva'),), 'forbidden':('armazena todas as imagens','guarda as imagens enviadas')},
 'dados': {'doc':'V05','evidence':('rdd2022','cidad','simulad'), 'required_any':(('rdd2022',),('cidada','relato'),('simulad','demonstracao')),'forbidden':()},
 'fluxo': {'doc':'V03','evidence':('camera','georreferenciado','validacao humana'), 'required_any':(('camera','detect'),('georreferenc','localiz'),('deduplic','duplic'),('prioriz','priorid'),('validacao','humana')),'forbidden':()},
 'devsecops': {'doc':'V13','evidence':('gitleaks','semgrep','trivy'), 'required_any':(('gitleaks',),('semgrep',),('pytest',),('trivy',),('sbom',)),'forbidden':()},
 'execucao': {'doc':'V15','evidence':('docker compose','preparar_segredos'), 'required_any':(('preparar_segredos','gerar segredos'),('docker compose up',),('8000',)),'forbidden':()},
}

def select_evidence(question: str, candidates: list[dict], corpus_by_id: dict) -> list[dict]:
    """Agente pode chamar documento de domínio além da busca TF-IDF; RAG simples não."""
    topic = topical(question)
    if topic in RULES:
        r = RULES[topic]
        doc = corpus_by_id.get(r['doc'])
        if doc and all(norm(s) in norm(doc['texto']) for s in r['evidence']):
            # preferir fonte principal; outras só se não deslocarem o contexto
            return [{**doc,'score':next((x.get('score',0.0) for x in candidates if x['id']==doc['id']),0.0)},
                    *[x for x in candidates if x['id']!=doc['id']][:2]]
    return candidates

def validate(question: str, answer: str, docs: list[dict]) -> tuple[bool,str]:
    if not answer or norm(answer).strip() in {'nao consta','nao sei'}:
        return False, 'Recusa ou resposta vazia.'
    topic=topical(question)
    if topic not in RULES:
        return True,'Sem regra de domínio específica; revisão humana necessária.'
    r=RULES[topic]
    corpus=' '.join(norm(d['texto']) for d in docs if d['id']==r['doc'])
    if not corpus or not all(norm(s) in corpus for s in r['evidence']):
        return False, 'Fonte de domínio não foi recuperada ou não contém a evidência.'
    a=norm(answer)
    if any(norm(x) in a for x in r['forbidden'] if not (topic == 'login' and norm(x) == 'exige login' and re.search(r'\bnao\s+exige\s+login\b', a))): return False, 'Contradição com a evidência documental.'
    # A mera presença da frase negativa copiada da fonte não pode neutralizar
    # uma afirmação POSITIVA incorreta sobre login em outra oração.
    if topic == 'login':
        # Remova citações textuais somente para a checagem de afirmação do autor;
        # a resposta inteira continua submetida às demais verificações.
        sem_citacoes = re.sub(r'[\"“”‘’][^\"“”‘’]*[\"“”‘’]', ' ', a)
        if re.search(r'\bsim\b\s*[,.:;!?-]?', sem_citacoes[:30]):
            return False, 'A resposta começa afirmando login obrigatório, mas V10 o nega no MVP.'
        padroes_positivos = (
            r'(?<!nao )(?:a fila|o mvp|zeladoria)[^.\n;]{0,90}\b(?:exige|requer|precisa de|necessita|possui|tem)\s+(?:de\s+)?(?:um\s+)?(?:login|autenticacao)',
            r'\blogin\s+(?:e|eh|esta|sera)\s+(?:obrigatorio|necessario|exigido)\b',
            r'\bautenticacao\s+(?:e|eh|esta)\s+(?:obrigatoria|exigida)\b',
        )
        for pat in padroes_positivos:
            for m in re.finditer(pat, sem_citacoes):
                trecho = sem_citacoes[max(0,m.start()-14):m.start()]
                if not re.search(r'\b(?:nao|sem|nunca)\b', trecho + ' ' + m.group()):
                    return False, 'Afirmação positiva de login em contradição com V10.'

    for group in r['required_any']:
        if not any(norm(term) in a for term in group):
            return False, 'Resposta incompleta em relação à pergunta e ao documento.'
    if topic == 'devsecops':
        # Segregar tarefas de segurança do treinamento de visão computacional.
        extra = ('rdd2022','dataset','treinamento de buracos','treino de buracos',
                 'detectar vulnerabilidades com dados','licenca agpl','cameras')
        if any(x in a for x in extra):
            return False, 'Afirmação fora da fonte DevSecOps; misturou domínios.'
    if topic == 'login':
        # Proteção explícita a afirmações compostas: "exige login, embora V10 diga...".
        frases = re.split(r'[.;!?]', a)
        for frase in frases:
            if re.search(r'\b(?:exige|requer|possui|tem)\s+(?:um\s+)?(?:login|autenticacao)\b', frase):
                if not re.search(r'\b(?:nao|nunca|sem)\b[^.;!?]{0,50}\b(?:exige|requer|possui|tem)\b', frase):
                    return False, 'Login obrigatório contradiz V10.'
    if topic=='problema' and len(answer.split()) > 85:
        return False, 'Resposta longa ou fora do escopo; explique somente o problema de mobilidade.'
    if topic=='privacidade' and any(x in norm(question) for x in ('logs','retencao')) and '30' not in a:
        return False, 'Retenção dos logs omitida.'

    if topic=='geocodificacao' and re.search(r'\bnao\b.{0,50}transferencia',a):
        return False, 'Negou uma transferência potencial documentada.'
    return True,'Obrigação factual e compatibilidade semântica verificadas por regras do domínio.'

# Relatório — VigiaVia GenAI Operacional

**Disciplina:** Generative AI for Engineering — FIAP GS 2026.2 · **Professor:** Francisco Elanio Bezerra.

## 1. Integrantes

- Deivison Pertel — RM 550803
- Eduardo Akira Murata — RM 98713
- Wesley Souza de Oliveira — RM 97874

## 2. Ficha técnica e tarefa da IA

A ficha técnica completa está no README. O sistema original identifica buracos em imagens e os registra na fila. A extensão GenAI oferece orientação ao cidadão, análise rastreável da fila de zeladoria, triagem explicável, possíveis duplicidades geográficas e relatórios; a LLM local responde perguntas com base documental e recusa quando não existem fontes. **A triagem é assistiva, e nunca confirma reparos.**

## 3. Pipeline

`documentos → trechos com origem → TF-IDF → top-k e limiar → Qwen2.5 local → verificador de citações → JSON`.

Fluxo independente dos fatos operacionais: `GET /v1/relatos → validação de campos → indicadores / prioridade / proximidade → painel e boletim`. A fila ao vivo não é enviada à LLM nem alterada.

## 4. Base de conhecimento

| Fonte | Formato | Licença declarada | Trechos |
|---|---|---|---:|
| README VigiaVia (ficha técnica, arquitetura, LGPD, execução e segurança) | Markdown, transformado em JSON | AGPL-3.0 | 18 |
| Endpoint `/v1/relatos` do VigiaVia | JSON (operacional, não entra no índice RAG) | Dados de serviço do MVP, sem licença inferida | n/a |
| Nove registros demonstrativos na Bela Vista | JSON sintético rotulado | Criados para esta demonstração acadêmica | n/a |

Verificar `base/trechos.json` para as licenças e URLs de cada trecho. Não misturar as duas espécies de dados na avaliação documental.

## 5. Três configurações e performance

1. **Baseline:** Qwen2.5:1.5b sem trechos.
2. **RAG:** mesmo Qwen, com recuperação TF-IDF e contexto.
3. **Agente:** mesmo RAG e verificador de fontes, segunda tentativa com evidência literal e fallback extrativo específico (V09).

A avaliação documental existente possui 18 casos, incluindo cinco "não consta". `avaliacao/medir.py` mede recall@1 e recall@3; `avaliacao/placar_llm.py` executa os 54 pares modelo/caso com Ollama real e salva latências, citações e recusas. **Não reportamos melhora quantitativa sem executar a avaliação real.** A qualidade semântica deve ser inspecionada por humano usando os gabaritos.

### Indicadores operacionais de demonstração

O conjunto contém **9 relatos fictícios** com status variados. A UI informa explicitamente que são SIMULADOS. Qualquer indicador do modo live deve ser coletado no momento da avaliação, e não interpretado como informação histórica.

## 6. Cinco erros / falhas reais e correções propostas

Os cinco erros requeridos pela banca devem sair de casos observados e registrados — **não são gerados por suposição**. Há um erro real conhecido:

| Nº | Caso | Evidência observada | Causa provável | Correção / reteste |
|---|---|---|---|---|
| 1 | Armazenamento de imagens (fonte V09) | RAG recuperou V09 com score 0,3017, mas Qwen recusou; mesmo após segunda tentativa | Recusa falsa na etapa generativa | Revisão do prompt, fallback extrativo V09, repetir no Ollama |
| 2 | A preencher após teste real | — | — | — |
| 3 | A preencher após teste real | — | — | — |
| 4 | A preencher após teste real | — | — | — |
| 5 | A preencher após teste real | — | — | — |

Outras falhas podem ser extraídas das métricas de recuperação e dos 54 retornos salvos, mas **só devem ser chamadas de erros reais se demonstradas**.

## 7. Conclusão, reprodutibilidade e links

O projeto apresenta implementação de ferramentas úteis à fila da zeladoria e mecanismo local de fundamentação, sem prometer automatizar decisões cívicas. O ganho do agente sobre RAG simples permanece **hipótese a testar empiricamente**, e a extensão não está implantada no mesmo domínio do MVP original.

- Repositório principal: https://github.com/akiramrt/vigiavia-mvp
- Aplicação MVP: https://ca-vigiavia-prod.happywave-0bf5b4c3.brazilsouth.azurecontainerapps.io
- Repositório público da extensão: **a publicar pela equipe**
- Vídeo: **a gravar pela equipe**

## Evolução — dois portais no mesmo MVP

Para atender cidadão e zeladoria de maneira distinta, a aplicação passou a ter navegação por perfis. O **cidadão** consulta relatos em um raio definido, acompanha status por ID, prepara um rascunho para conferência de possível duplicidade e consulta orientações com fontes. A **zeladoria** utiliza um painel com indicadores, filtros por status/severidade, triagem de um relato específico, consulta de possíveis duplicidades e emissão de boletim. Ambos consultam a mesma fila do VigiaVia por leitura, ou uma base explicitamente simulada.

A integração factual é via `GET /v1/relatos`. Não se introduz `POST` nem `PATCH` no MVP original pela extensão: o próprio MVP permanece responsável pelo cadastro de relatos, processamento de imagens e validação humana. São duas interfaces do **mesmo produto**; não um segundo detector de buracos. Esta versão não deve ser apresentada como gerenciamento completo de solicitações com autenticação, rastreio de cidadão e execução de reparos — tais recursos não estão no contrato da API consultado.

**Testes automatizados da extensão:** executar `python -m pytest -q` e anexar resultado real do ambiente da equipe. **Avaliação da LLM:** ainda é necessário executar os experimentos reais no Ollama, interpretar o placar das três configurações e documentar cinco erros concretos de geração/recuperação, em vez de inferir números dos testes unitários.

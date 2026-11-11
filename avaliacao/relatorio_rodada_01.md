# Primeira rodada (11/11/2026) — preservada sem alterações

**Origem:** arquivos fornecidos pelo grupo após execução de `placar_llm.py` com Qwen2.5:1.5B e 18 perguntas. O conteúdo original completo está em `rodada_01_original/`.

| Configuração | Correção estrita (incluindo 5 recusas corretas) | Corretas factuais / 13 | Recusas indevidas |
|---|---:|---:|---:|
| Baseline | 5/18 = 27,8% | 0/13 | 11 |
| RAG simples | 7/18 = 38,9% | 2/13 | 7 |
| Agente verificador | 8/18 = 44,4% | 3/13 | 6 |

Critério de correção: resposta completa e semanticamente consistente com o gabarito. A presença de fonte válida sem resposta correta **não conta como acerto**. As cinco perguntas sem resposta têm recusa correta em todos os modos.

**Recuperação:** limiar 0,19; recall@1=7/13 (53,85%), recall@3=7/13 (53,85%). Sem filtro, documentos de referência são top1 em 12/13, top3 em 13/13; isso não é a mesma métrica filtrada. A redução de limiar melhora cobertura mas exige maior verificação e recusa semântica.

## Cinco erros reais e causas

| Caso | Evidência | Causa provável | Correção proposta |
|---|---|---|---|
| T03 | O RAG/Agente fala de RDD2022, não do fluxo de relatos | V05 foi recuperado acima de V03 pelo limiar | Incluir contexto de fluxo com reranking e validação de aderência à pergunta |
| T05 | O RAG responde apenas “Fontes: [URL]”, sem listar as fontes | Texto curto/incompleto aceito por validação de citação | Checar completude da resposta por gabarito e evidência |
| T09 | Pergunta sobre foto + logs recusada com V09 no top1, score 0,1855 | Limiar de 0,19 descarta documento correto | Calibrar limiar e avaliar recusa com evidência textual |
| T10 | “Sim” para login exigido na fila, citando V10 | Erro semântico apesar de ID válido | Exigir validação de contradições por sentença, não apenas ID |
| T11 | “Não, ... não envolve transferência internacional”, citando V11 | Contradição direta ao texto-fonte | Verificar negação/polaridade; revisão humana em temas LGPD |

A especialização por agente mostra ganho pequeno e insuficiente nesta rodada; não é correto afirmar que eliminou alucinações. O objetivo da V4 é melhorar a estrutura das evidências e o agente operacional, a ser testado com Ollama real no computador do grupo.

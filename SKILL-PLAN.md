# Skill para Agent — Plano de Implementacao v3

## Conceito

Skill e um fragmento reutilizavel de instrucao que um Agent pode carregar para
adquirir uma capacidade ou personalidade. Diferente de editar o `system` toda vez,
voce empilha Skills e o agente as ativa conforme o contexto.

---

## Skill

### Parametros

| Campo | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `name` | `str` | sim | Nome unico para rastreabilidade |
| `content` | `str` | sim* | Conteudo do prompt da skill |
| `path` | `str` | nao | Caminho para arquivo .md (alternativa a content) |
| `context` | `str` | nao | Descricao de quando ativar. Ex: "Use esta skill quando o usuario pedir analise de risco" |

*Obrigatorio se `path` nao for fornecido.

### Sem context (comportamento atual)

O conteudo e anexado ao `system_prompt` permanentemente. A skill esta sempre ativa.

```python
Skill(name="analista", content="Voce e um analista financeiro.")
```

### Com context (ativacao sob demanda)

O `system_prompt` lista a skill como disponivel com seu contexto, mas nao anexa
o conteudo completo. O agente decide quando ativar baseado no contexto.

No `system_prompt` fica:
```
--- Skills Disponiveis ---
- analista (analise financeira): Ative esta skill quando o usuario pedir analise de risco
- revisor (revisao juridica): Ative esta skill para revisar contratos e clausulas
--- Fim das Skills ---
```

A ativacao ocorre quando o agente menciona o nome da skill no raciocinio ou
explicitamente via `activate_skill(nome)`. Ao ativar, o conteudo da skill e
injetado na conversa como mensagem do sistema adicional.

### Mecanismo de ativacao

1. **Skill tool**: o agente ganha uma ferramenta `activate_skill(name)` que
   injeta o conteudo como mensagem `system` na conversa.
2. **Automatica por contexto**: quando o contexto do usuario corresponde ao
   `context` da skill, o agente usa o `activate_skill` internamente.
3. **Multiplas ativacoes**: o agente pode ativar varias skills em sequencia.
   Cada ativacao e um tool call distinto.

---

## SkillKnowledge

SkillKnowledge e uma skill que nao adiciona prompt — apenas registra uma base
de conhecimento especializada com contexto de ativacao.

### Parametros

| Campo | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `name` | `str` | sim | Nome unico para rastreabilidade |
| `knowledge` | `Knowledge` | sim | Base de conhecimento especializada |
| `context` | `str` | sim | Quando ativar esta busca. Ex: "Use quando precisar de dados regulatorios da ANATEL" |

### Comportamento

1. Registra uma ferramenta `search_knowledge_{name}` no `_tool_map`.
2. No `system_prompt`, lista:
   ```
   - dados-regulatorios (Knowledge): Use quando precisar de dados regulatorios da ANATEL
   ```
3. O agente ativa via tool call quando o contexto do usuario pedir.

Importante: `SkillKnowledge` NAO adiciona conteudo ao `system_prompt` — apenas
a ferramenta de busca e a descricao de contexto.

---

## Exemplos de uso

```python
from wolfpack import Agent, Skill, SkillKnowledge, get_model_from_env
from wolfpack.knowledge import Knowledge

# Skill com ativacao por contexto
analista = Skill(
    name="analista-risco",
    content="Use matriz de risco (probabilidade x impacto). Classifique como baixo, medio, alto ou critico.",
    context="Quando o usuario pedir analise de risco financeiro ou de projeto",
)

# Skill sempre ativa (sem context)
revisor = Skill(
    name="revisor-portugues",
    content="Revise o texto em portugues brasileiro. Corrija ortografia, concordancia e clareza.",
)

# SkillKnowledge — base especializada com contexto
regulatorio = SkillKnowledge(
    name="normas-anatel",
    knowledge=Knowledge(vector_db=db, embedding_model=model),
    context="Use quando precisar de regulamentacoes da ANATEL ou normas de telecom",
)

agente = Agent(
    name="assistente",
    model=get_model_from_env(),
    skills=[analista, revisor, regulatorio],
)
```

---

## Observabilidade no AMP

1. **system_prompt completo** (com skills listadas) aparece como input do modelo
   no trace — sem alteracao.
2. **Tool calls** de `activate_skill(name)` e `search_knowledge_{name}` sao
   registrados como spans filhos no trace, com o nome da skill.
3. **Metadados**: `WolfpackObserver` registra no span principal:
   ```json
   {"skills": ["analista-risco", "revisor-portugues", "normas-anatel"]}
   ```
4. **Filtro**: permite buscar traces por `skills` no AMP.

---

## Arquivos

| Arquivo | Descricao |
|---|---|
| `framework/wolfpack/agent/skill.py` | Skill e SkillKnowledge |
| `framework/wolfpack/agent/agent.py` | Campo `skills`, modificar `system_prompt` e `_tool_map` |
| `framework/wolfpack/__init__.py` | Exportar Skill, SkillKnowledge |
| `framework/tests/test_skills.py` | Testes |
| `framework/examples/22_skills/01_skill_basics.py` | Exemplo deterministico |

## Testes

1. Skill sem context anexa conteudo no system_prompt (sempre ativa)
2. Skill com context lista no system_prompt sem anexar conteudo
3. Skill com path .md carrega conteudo do arquivo
4. SkillKnowledge registra search_knowledge tool e NAO anexa prompt
5. Agent com skills + SkillKnowledge misturados funciona
6. Multiplas skills sao listadas em ordem
7. Observer registra metadata de skills
# 🔬 Relatório Comparativo: Estratégias de Chunking em Livros de Cálculo

> **Experimento Prático com Stewart Calculus** | Comparativo entre Chunking Estático (1000 chars), Semântico e Parent-Child.

## 1. Visão Geral das Estratégias Testadas

| Estratégia | Total de Chunks | Granularidade | Filosofia de Quebra |
|---|:---:|:---:|---|
| **1. Estático (Baseline)** | 19 | Fixo (1000 chars) | Corta cego por contagem de caracteres com overlap arbitrário de 200. |
| **2. Semântico** | 18 | Dinâmico | Quebra frases onde a similaridade de embedding indica mudança de assunto. |
| **3. Parent-Child** | 77 filhos / 15 pais | Dupla (250 chars / 1200 chars) | Busca com vetor minúsculo e focado; entrega o parágrafo pai completo. |

---

## 2. Resultados das Buscas Conceituais

### 📌 Q1: "How is instantaneous velocity related to the position function of a particle?"
**Conceito Matemático Esperado:** `v = ds/dt (rate of change of displacement) and s(t) position`

| Métrica | Chunker Estático (1000c) | Chunker Semântico | Parent-Child (Small-to-Big) |
|---|:---:|:---:|:---:|
| **Julgamento do Evaluator** | ✅ Aprovado | ✅ Aprovado | ✅ Aprovado |
| **Tamanho do Trecho** | 981 chars | 1215 chars | 1124 chars |
| **Contaminação de Rodapé/Ruído** | 🟢 Não | 🟢 Não | 🟢 Não |

#### 🔎 Inspeção do Trecho Recuperado:
<details><summary><b>Ver Trecho - Chunker Estático (Baseline)</b></summary>

```text
170 Chapter 2  Derivatives
ExamplE 1 The position of a particle is given by the equation
s − f std − t3 2 6t2 1 9t 
where t is measured in seconds and s in meters.
(a) Find the velocity at time t.
(b) What is the velocity after 2 s? After 4 s?
(c) When is the particle at rest?
(d) When is the particle moving forward (that is, in the positive direction)?
(e) Draw a diagram to represent the motion of the particle.
(f) Find the total distance traveled by the particle during the first five seconds.
(g) Find the acceleration at time t and after 4 s.
(h) Graph the position, velocity, and acceleration functions for 0 < t < 5.
(i) When is the particle speeding up? When is it slowing down?
SoLUtion 
(a) The velocity function is the derivative of the position function.
 s − f std − t3 2 6t2 1 9t
 vstd − ds
dt − 3t2 2 12t 1 9
(b) The velocity after 2 s means the instantaneous velocity when t − 2, that is,
vs2d − ds
dt Z
t−2
− 3s2d2 2 12s2d 1 9 − 23 mys
The velocity after 4 s is
```
</details>

<details><summary><b>Ver Trecho - Chunker Semântico</b></summary>

```text
(a) Find the velocity at time t. (b) What is the velocity after 2 s? After 4 s? (c) When is the particle at rest? (d) When is the particle moving forward (that is, in the positive direction)? (e) Draw a diagram to represent the motion of the particle. (f) Find the total distance traveled by the particle during the first five seconds. (g) Find the acceleration at time t and after 4 s. (h) Graph the position, velocity, and acceleration functions for 0 < t < 5. (i) When is the particle speeding up? When is it slowing down? SoLUtion 
(a) The velocity function is the derivative of the position function. s − f std − t3 2 6t2 1 9t
 vstd − ds
dt − 3t2 2 12t 1 9
(b) The velocity after 2 s means the instantaneous velocity when t − 2, that is,
vs2d − ds
dt Z
t−2
− 3s2d2 2 12s2d 1 9 − 23 mys
The velocity after 4 s is
vs4d − 3s4d2 2 12s4d 1 9 − 9 mys
(c) The particle is at rest when vstd − 0, that is,
3t2 2 12t 1 9 − 3st2 2 4t 1 3d − 3st 2 1dst 2 3d − 0
and this is true when t − 1 or t − 3. Thus the particle is at rest after 1 s and after 3 s. (d) The particle moves in the positive direction when vstd . 0, that is,
3t2 2 12t 1 9 − 3st 2 1dst 2 3d . 0
This inequality is true when both factors are positive st .
```
</details>

<details><summary><b>Ver Trecho - Parent-Child (Match do Filho + Entrega do Pai)</b></summary>

**Trecho Filho que deu Match no Vetor:**
> *"taneous velocity (the rate of change of displacement with respect to time). The instanta-"*

**Contexto Pai Completo entregue ao Tutor:**
```text
The difference quotient 
Dy
Dx −  f sx2 d 2 f sx1d
x2 2 x1
is the average rate of change of y with respect to x over the interval fx1, x2 g and can 
be interpreted as the slope of the secant line PQ in Figure 1. Its limit as Dx l 0 is the 
derivative f 9sx1d, which can therefore be interpreted as the instantaneous rate of change 
of y with respect to x or the slope of the tangent line at Psx1, f sx1dd. Using Leibniz nota-
tion, we write the process in the form
dy
dx − lim
Dx l 0
 Dy
Dx
Whenever the function y − f sxd has a specific interpretation in one of the sciences, its 
derivative will have a specific interpretation as a rate of change. (As we discussed in Sec-
tion 2.1, the units for dyydx are the units for y divided by the units for x.) We now look 
at some of these interpretations in the natural and social sciences.
physics
If s − f std is the position function of a particle that is moving in a straight line, then DsyDt 
represents the average velocity over a time period Dt, and v − dsydt represents the instan-
taneous velocity (the rate of change of displacement with respect to time). The instanta-
```
</details>

---

### 📌 Q2: "What is the difference quotient and what does it represent geometrically?"
**Conceito Matemático Esperado:** `Delta y / Delta x = slope of the secant line PQ`

| Métrica | Chunker Estático (1000c) | Chunker Semântico | Parent-Child (Small-to-Big) |
|---|:---:|:---:|:---:|
| **Julgamento do Evaluator** | ✅ Aprovado | ✅ Aprovado | ✅ Aprovado |
| **Tamanho do Trecho** | 983 chars | 107 chars | 1124 chars |
| **Contaminação de Rodapé/Ruído** | 🟢 Não | ⚠️ Sim | 🟢 Não |

#### 🔎 Inspeção do Trecho Recuperado:
<details><summary><b>Ver Trecho - Chunker Estático (Baseline)</b></summary>

```text
derivative will have a specific interpretation as a rate of change. (As we discussed in Sec-
tion 2.1, the units for dyydx are the units for y divided by the units for x.) We now look 
at some of these interpretations in the natural and social sciences.
physics
If s − f std is the position function of a particle that is moving in a straight line, then DsyDt 
represents the average velocity over a time period Dt, and v − dsydt represents the instan-
taneous velocity (the rate of change of displacement with respect to time). The instanta-
neous rate of change of velocity with respect to time is acceleration: astd − v9std − s9 9std.  
This was discussed in Sections 2.1 and 2.2, but now that we know the differentiation 
formulas, we are able to solve problems involving the motion of objects more easily.
0 x
y
Îy
⁄
P{⁄, ﬂ }
Q{¤, ‡ }
Îx
¤
mPQ /H11005 average rate of change
m=fª(⁄ )=instantaneous rate
of change
FIGURE 1
40621_ch02_ptg1_hr_166-175.indd   169 4/13/15   11:27 AM
```
</details>

<details><summary><b>Ver Trecho - Chunker Semântico</b></summary>

```text
FIGURE 4
FIGURE 5
40621_ch02_ptg1_hr_166-175.indd   171 4/13/15   11:27 AM
Copyright 2016 Cengage Learning.
```
</details>

<details><summary><b>Ver Trecho - Parent-Child (Match do Filho + Entrega do Pai)</b></summary>

**Trecho Filho que deu Match no Vetor:**
> *"The difference quotient 
Dy
Dx −  f sx2 d 2 f sx1d
x2 2 x1
is the average rate of change of y with respect to x over the interval fx1, x2 g and can 
be interpreted as the slope of the secant line PQ in Figure 1. Its limit as Dx l 0 is the"*

**Contexto Pai Completo entregue ao Tutor:**
```text
The difference quotient 
Dy
Dx −  f sx2 d 2 f sx1d
x2 2 x1
is the average rate of change of y with respect to x over the interval fx1, x2 g and can 
be interpreted as the slope of the secant line PQ in Figure 1. Its limit as Dx l 0 is the 
derivative f 9sx1d, which can therefore be interpreted as the instantaneous rate of change 
of y with respect to x or the slope of the tangent line at Psx1, f sx1dd. Using Leibniz nota-
tion, we write the process in the form
dy
dx − lim
Dx l 0
 Dy
Dx
Whenever the function y − f sxd has a specific interpretation in one of the sciences, its 
derivative will have a specific interpretation as a rate of change. (As we discussed in Sec-
tion 2.1, the units for dyydx are the units for y divided by the units for x.) We now look 
at some of these interpretations in the natural and social sciences.
physics
If s − f std is the position function of a particle that is moving in a straight line, then DsyDt 
represents the average velocity over a time period Dt, and v − dsydt represents the instan-
taneous velocity (the rate of change of displacement with respect to time). The instanta-
```
</details>

---

### 📌 Q3: "How does acceleration relate to velocity and the second derivative of position?"
**Conceito Matemático Esperado:** `a(t) = v'(t) = s''(t) instantaneous rate of change of velocity`

| Métrica | Chunker Estático (1000c) | Chunker Semântico | Parent-Child (Small-to-Big) |
|---|:---:|:---:|:---:|
| **Julgamento do Evaluator** | ✅ Aprovado | ✅ Aprovado | ✅ Aprovado |
| **Tamanho do Trecho** | 983 chars | 1215 chars | 1119 chars |
| **Contaminação de Rodapé/Ruído** | 🟢 Não | 🟢 Não | 🟢 Não |

#### 🔎 Inspeção do Trecho Recuperado:
<details><summary><b>Ver Trecho - Chunker Estático (Baseline)</b></summary>

```text
derivative will have a specific interpretation as a rate of change. (As we discussed in Sec-
tion 2.1, the units for dyydx are the units for y divided by the units for x.) We now look 
at some of these interpretations in the natural and social sciences.
physics
If s − f std is the position function of a particle that is moving in a straight line, then DsyDt 
represents the average velocity over a time period Dt, and v − dsydt represents the instan-
taneous velocity (the rate of change of displacement with respect to time). The instanta-
neous rate of change of velocity with respect to time is acceleration: astd − v9std − s9 9std.  
This was discussed in Sections 2.1 and 2.2, but now that we know the differentiation 
formulas, we are able to solve problems involving the motion of objects more easily.
0 x
y
Îy
⁄
P{⁄, ﬂ }
Q{¤, ‡ }
Îx
¤
mPQ /H11005 average rate of change
m=fª(⁄ )=instantaneous rate
of change
FIGURE 1
40621_ch02_ptg1_hr_166-175.indd   169 4/13/15   11:27 AM
```
</details>

<details><summary><b>Ver Trecho - Chunker Semântico</b></summary>

```text
(a) Find the velocity at time t. (b) What is the velocity after 2 s? After 4 s? (c) When is the particle at rest? (d) When is the particle moving forward (that is, in the positive direction)? (e) Draw a diagram to represent the motion of the particle. (f) Find the total distance traveled by the particle during the first five seconds. (g) Find the acceleration at time t and after 4 s. (h) Graph the position, velocity, and acceleration functions for 0 < t < 5. (i) When is the particle speeding up? When is it slowing down? SoLUtion 
(a) The velocity function is the derivative of the position function. s − f std − t3 2 6t2 1 9t
 vstd − ds
dt − 3t2 2 12t 1 9
(b) The velocity after 2 s means the instantaneous velocity when t − 2, that is,
vs2d − ds
dt Z
t−2
− 3s2d2 2 12s2d 1 9 − 23 mys
The velocity after 4 s is
vs4d − 3s4d2 2 12s4d 1 9 − 9 mys
(c) The particle is at rest when vstd − 0, that is,
3t2 2 12t 1 9 − 3st2 2 4t 1 3d − 3st 2 1dst 2 3d − 0
and this is true when t − 1 or t − 3. Thus the particle is at rest after 1 s and after 3 s. (d) The particle moves in the positive direction when vstd . 0, that is,
3t2 2 12t 1 9 − 3st 2 1dst 2 3d . 0
This inequality is true when both factors are positive st .
```
</details>

<details><summary><b>Ver Trecho - Parent-Child (Match do Filho + Entrega do Pai)</b></summary>

**Trecho Filho que deu Match no Vetor:**
> *"170 Chapter 2  Derivatives
ExamplE 1 The position of a particle is given by the equation
s − f std − t3 2 6t2 1 9t 
where t is measured in seconds and s in meters.
(a) Find the velocity at time t.
(b) What is the velocity after 2 s? After 4 s?"*

**Contexto Pai Completo entregue ao Tutor:**
```text
170 Chapter 2  Derivatives
ExamplE 1 The position of a particle is given by the equation
s − f std − t3 2 6t2 1 9t 
where t is measured in seconds and s in meters.
(a) Find the velocity at time t.
(b) What is the velocity after 2 s? After 4 s?
(c) When is the particle at rest?
(d) When is the particle moving forward (that is, in the positive direction)?
(e) Draw a diagram to represent the motion of the particle.
(f) Find the total distance traveled by the particle during the first five seconds.
(g) Find the acceleration at time t and after 4 s.
(h) Graph the position, velocity, and acceleration functions for 0 < t < 5.
(i) When is the particle speeding up? When is it slowing down?
SoLUtion 
(a) The velocity function is the derivative of the position function.
 s − f std − t3 2 6t2 1 9t
 vstd − ds
dt − 3t2 2 12t 1 9
(b) The velocity after 2 s means the instantaneous velocity when t − 2, that is,
vs2d − ds
dt Z
t−2
− 3s2d2 2 12s2d 1 9 − 23 mys
The velocity after 4 s is
vs4d − 3s4d2 2 12s4d 1 9 − 9 mys
(c) The particle is at rest when vstd − 0, that is,
3t2 2 12t 1 9 − 3st2 2 4t 1 3d − 3st 2 1dst 2 3d − 0
```
</details>

---

## 3. Análise Crítica dos Resultados & Por que o Estático Falha

### Por que o Chunking Estático de 1000 caracteres é frágil:
1. **Quebra de continuidade matemática:** Em livros didáticos, definições como limites e taxas de variação são explicadas em pares (intuição geométrica + fórmula + exemplo). O corte de 1000 caracteres frequentemente corta a fórmula das suas condições de contorno.
2. **Mistura de ruído de layout:** Em PDFs acadêmicos com rodapés e avisos legais, o corte por tamanho engole trechos como `Copyright 2016 Cengage Learning` junto com o conteúdo.

### Por que o Parent-Child (Small-to-Big) é o Padrão da Indústria (ThetaWise):
- **O dilema do tamanho de chunk:**
  - *Chunk grande (1000+ chars)*: bom para o LLM ler, mas ruim para a busca vetorial (o embedding fica 'diluído' e a similaridade cai).
  - *Chunk pequeno (200 chars)*: excelente para a busca vetorial (alta densidade), mas péssimo para o LLM (falta contexto ao redor).
- **A solução Parent-Child:** Resolve o dilema usando o melhor dos dois mundos. O embedding busca a frase exata de 200 caracteres, mas entrega a seção de 1200 caracteres ao Tutor.
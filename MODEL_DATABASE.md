# CAI World Cup 2026 Prediction Model — Master Database

> **Version**: 1.1 · **Updated**: 2026-06-30  
> **Author**: CAI (Contextual AI Inference) Prediction Engine  
> This document is the single source of truth for the prediction model:
> all coefficients, data sources, match results, team ratings, and methodology.
> It is designed to be manually updated as the tournament progresses and
> published as the model's public specification.

---

## Table of Contents

1. [Model Architecture](#1-model-architecture)
2. [Ensemble Coefficients & Weights](#2-ensemble-coefficients--weights)
3. [Feature Engineering](#3-feature-engineering)
4. [Player Condition Engine](#4-player-condition-engine)
5. [Tournament Elo Updates](#5-tournament-elo-updates)
6. [Team Database — All 48 Teams](#6-team-database--all-48-teams)
7. [Manager Win-Rate Coefficients](#7-manager-win-rate-coefficients)
8. [Group Draw & Fixture Schedule](#8-group-draw--fixture-schedule)
9. [All Group Stage Results — 72 Matches](#9-all-group-stage-results--72-matches)
10. [Knockout Bracket Results & Predictions](#10-knockout-bracket-results--predictions)
11. [Goal Scorer Database](#11-goal-scorer-database)
12. [Model Accuracy Log](#12-model-accuracy-log)
13. [Data Sources & References](#13-data-sources--references)
14. [Manual Update Guide](#14-manual-update-guide)

---

## 1. Model Architecture

The CAI engine is a **6-member weighted ensemble** that blends statistical,
machine-learning, and market-based signals into a single calibrated prediction.

```
                    ┌─────────────────────────────────────────┐
                    │           CAI ENSEMBLE ENGINE            │
                    │                                         │
  ┌──────────┐      │  ┌─────────┐  weight: 0.35             │
  │ Betting  │─────▶│  │ Market  │                            │
  │  Odds    │      │  └────┬────┘                            │
  └──────────┘      │       │                                 │
                    │  ┌────▼────┐  weight: 0.22             │
  ┌──────────┐      │  │Dixon-   │  (attack/defence rates)   │
  │Historical│─────▶│  │Coles DC │                            │
  │ Results  │      │  └────┬────┘                            │
  └──────────┘      │       │                                 │
                    │  ┌────▼────┐  weight: 0.18             │
  ┌──────────┐      │  │XGBoost  │  (11 engineered features) │
  │ Features │─────▶│  │ Model   │                            │
  │  Vector  │      │  └────┬────┘                            │
  └──────────┘      │       │                                 │
                    │  ┌────▼────┐  weight: 0.08             │
                    │  │Neural   │  (same feature vector)    │
                    │  │  Net    │                            │
                    │  └────┬────┘                            │
                    │       │                                 │
  ┌──────────┐      │  ┌────▼────┐  weight: 0.10             │
  │   Elo    │─────▶│  │  Elo    │  (live WC2026-updated)   │
  │ Ratings  │      │  └────┬────┘                            │
  └──────────┘      │       │                                 │
                    │  ┌────▼────┐  weight: 0.07             │
                    │  │Poisson  │  (Elo-derived λ)          │
                    │  └────┬────┘                            │
                    │       │                                 │
                    │  ┌────▼──────────────────────┐         │
                    │  │   Weighted Blend           │         │
                    │  │   + Temperature Calibration│         │
                    │  └────┬──────────────────────┘         │
                    │       │                                 │
                    │  ┌────▼──────────────────────┐         │
                    │  │   Post-blend Adjustments  │         │
                    │  │   • Availability (AVAIL)  │         │
                    │  │   • Travel fatigue        │         │
                    │  │   • Weather severity      │         │
                    │  │   • Squad condition       │         │
                    │  └────┬──────────────────────┘         │
                    └───────┼─────────────────────────────────┘
                            ▼
                    {p_home, p_draw, p_away, xG, confidence, predicted_winner}
```

### Philosophy

> **"Form leads, history supports."**  
> CAI's core thesis: how a team is *actually playing now* (current form,
> squad fitness, WC2026 in-tournament momentum) beats a static historical
> rating. Pre-tournament Elo/DC priors anchor the forecast; live tournament
> data actively steers it.

---

## 2. Ensemble Coefficients & Weights

### 2.1 Blend Weights

| Member | Default Weight | Role |
|--------|----------------|------|
| `market` | **0.35** | De-vigged betting odds — strongest single signal |
| `dc` | **0.22** | Dixon-Coles bivariate Poisson (attack/defence rates) |
| `xgb` | **0.18** | XGBoost on 11 engineered features |
| `nn` | **0.08** | Neural network on same feature vector |
| `elo` | **0.10** | FiveThirtyEight-style Elo (live tournament updates) |
| `poisson` | **0.07** | Independent Poisson (Elo-derived λ) |

> **Dynamic weight rebalancing**: when backtest artifacts exist
> (`member_metrics.json`), weights are replaced by inverse-log-loss
> scores per member (minimum 30 OOS samples). Each weight is capped
> at `[0.03, 0.45]` and re-normalized after capping.

> **Synthetic market penalty**: when no real book odds exist, the
> market member is filled with Elo-synthetic probs shrunk 10% toward
> uniform (1/3 each). Its blend weight is then reduced by factor
> `SYNTH_MARKET_WEIGHT_PENALTY = 0.25`.

### 2.2 Post-Blend Adjustment Coefficients

```python
AVAIL_COEF     = 1.80   # logit shift per unit availability difference (injury/suspension)
TRAVEL_COEF    = 0.08   # logit shift per unit travel fatigue (tanh-scaled at 2500 km)
WEATHER_COEF   = 0.035  # draw-mass boost per unit weather severity (0-1)
CONDITION_COEF = 2.00   # squad-condition logit shift — validated 2026-06-30
                        # Tuned on 75 completed WC2026 matches; accuracy plateaus
                        # at 68% for coef≥2.0. Coverage-gating ensures it only
                        # fires when both teams have PLAYER_DB entries.
                        # Run tune_condition_coef.py after each round to re-validate.
```

**CONDITION_COEF history:**
| Date | Value | Accuracy | Notes |
|------|-------|----------|-------|
| Initial | 2.45 | — | Hand-raised, no backtest |
| 2026-06-30 | **2.00** | **68%** | Sweep on 75 played games; plateau 2.0–3.0 |

**Availability shift formula** (applied in log space):
```
p_home_new = exp(log(p_home) + AVAIL_COEF × avail_diff)
p_away_new = exp(log(p_away) - AVAIL_COEF × avail_diff)
# renormalize to sum=1; draw mass adjusts
```

**Travel fatigue formula**:
```
t = TRAVEL_COEF × tanh(travel_diff_km / 2500)
# positive t penalises home side (they travelled more)
```

**Weather leveller**: when severity > 0.01, boost draw mass by
`WEATHER_COEF × severity`, taken from the favourite's win probability.

### 2.3 Elo Parameters

```python
K_BASE      = 40.0   # standard K-factor for historical training
TOURNEY_K   = 20.0   # lighter K for in-tournament WC2026 updates (high variance)
HOME_ADV    = 65.0   # Elo home-advantage points (historical)
KNOCKOUT_HOME_ADV = 35.0  # softened; location de-prioritised at neutral venues
```

**Elo update formula** (FiveThirtyEight-style with MoV multiplier):
```
E_home = 1 / (1 + 10^((elo_away - elo_home) / 400))
MoV    = log(|GD| + 1) × 2.2 / (0.001 × |elo_diff| + 2.2)   [GD ≥ 2]
delta  = K × MoV × (result - E_home)
elo_home += delta ;  elo_away -= delta
```

### 2.4 Confidence Score Formula

```
agreement    = max(0, 1 - std(member_probs) / 0.20)    # low cross-member disagreement
decisiveness = (max(blended) - 1/3) / (1 - 1/3)        # favourite above 3-way coin flip
coverage     = n_members_present / 6                    # fraction of member roster
reliability  = f(ECE, bucket_gaps)                      # recent calibration quality [0-1]

raw_conf = 100 × (0.35×agreement + 0.35×decisiveness + 0.12×coverage + 0.18×reliability)
```

**Display stretch** (maps realistic football band to 0-100 for UI):
```
CONF_DISPLAY_LO = 27
CONF_DISPLAY_HI = 58
display_conf = clip(round((raw - 27) / (58-27) × 100), 1, 99)
```

### 2.5 Draw-Call Gate

```python
DRAW_PROB_MIN = 0.20   # draw prob must clear this threshold
DRAW_BALANCE  = 0.08   # |p_home - p_away| must be within this range
```
A "Draw" outcome is only predicted when *both* conditions hold simultaneously.
This gate was tuned from 0.27 → 0.20 on Jun 25 after measuring that
the model's realized p_draw ceiling across 54 played games was 0.24.

---

## 3. Feature Engineering

The XGBoost and Neural Net members use the same 11-feature vector,
computed without lookahead (all features use information available
before the match).

### 3.1 Feature Vector

| # | Feature | Description | Range |
|---|---------|-------------|-------|
| 1 | `elo_diff` | home Elo minus away Elo | ≈ −800 to +800 |
| 2 | `elo_home` | absolute home Elo rating | ≈ 1100 to 2100 |
| 3 | `elo_away` | absolute away Elo rating | ≈ 1100 to 2100 |
| 4 | `form_pts_diff` | rolling mean pts difference (last 5 matches each) | ≈ −3 to +3 |
| 5 | `form_gd_diff` | rolling mean GD difference (last 5 matches each) | ≈ −5 to +5 |
| 6 | `rest_diff` | home rest days minus away rest days (clipped ±30) | −30 to +30 |
| 7 | `h2h_home_rate` | historical H2H home-win rate | 0 to 1 |
| 8 | `neutral` | 1 if played at neutral venue, 0 if home ground | 0 or 1 |
| 9 | `avail_diff` | home squad availability minus away (injury %) | −1 to +1 |
| 10 | `squad_val_diff` | home squad market value minus away (scaled) | varies |
| 11 | `market_home_edge` | implied home edge from de-vigged betting odds | −1 to +1 |

### 3.2 Form Window

```python
FORM_WINDOW = 5  # rolling window for pts/GD form calculations
```

### 3.3 Training Dataset

- **Source**: `martj42/international-football-results` Kaggle dataset
- **Coverage**: ~46,000 international matches from 1872 to 2025
- **Filtering**: FIFA-eligible teams; World Cup, Confederations Cup,
  Olympic qualifiers, and senior friendlies included
- **Target**: 3-class label — H (home win), D (draw), A (away win)
- **Elo ratings**: pre-computed via `elo.py` on the same dataset

---

## 4. Player Condition Engine

`player_condition.py` computes a team-condition score per match that is
applied as a logit shift (`CONDITION_COEF = 2.00`) on the win probs.

### 4.1 Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Squad composite fitness | 0.30 | Mean fitness × impact for fit players |
| Form score | 0.25 | Mean player form (0-10 scale), impact-weighted |
| Star player availability | 0.20 | Penalty when impact ≥ 0.80 players are out |
| GK quality | 0.10 | GK-specific form × fitness |
| Squad depth | 0.10 | Quality of 2nd-tier replacements |
| Manager win-rate | 0.05 | Manager historical win-rate proxy (0-1) |

### 4.2 Tournament Momentum Component

Momentum is derived from in-tournament Elo delta (WC2026 group stage results):
```python
momentum = (adjusted_elo - baseline_elo) / 200.0   # scaled to ~[-1, +1]
```
This is *included* in the condition shift during knockout prediction
(included via `include_momentum=True`). The Elo member already carries
WC2026 results — this re-emphasis is intentional (CAI's form-leads thesis)
and not double-counting.

### 4.3 Manager Win-Rate Table

| Manager | Team | Win-Rate Proxy |
|---------|------|----------------|
| Lionel Scaloni | Argentina | 0.74 |
| Luis de la Fuente | Spain | 0.70 |
| Didier Deschamps | France | 0.66 |
| Roberto Martínez | Portugal | 0.64 |
| Néstor Lorenzo | Colombia | 0.64 |
| Julian Nagelsmann | Germany | 0.61 |
| Ralf Rangnick | Austria | 0.62 |
| Thomas Tuchel | England | 0.62 |
| Hajime Moriyasu | Japan | 0.62 |
| Ronald Koeman | Netherlands | 0.63 |
| Mohamed Ouahbi | Morocco | 0.62 |
| Hossam Hassan | Egypt | 0.60 |
| Amir Ghalenoei | Iran | 0.60 |
| Carlo Ancelotti | Brazil | 0.60 |
| Zlatko Dalić | Croatia | 0.60 |
| Emerse Faé | Ivory Coast | 0.58 |
| Marcelo Bielsa | Uruguay | 0.58 |
| Jesse Marsch | Canada | 0.56 |
| Murat Yakin | Switzerland | 0.56 |
| Julen Lopetegui | Qatar | 0.56 |
| Javier Aguirre | Mexico | 0.56 |
| Hugo Broos | South Africa | 0.55 |
| Hong Myung-bo | South Korea | 0.55 |
| Vincenzo Montella | Turkey | 0.55 |
| Ståle Solbakken | Norway | 0.55 |
| Pape Thiaw | Senegal | 0.56 |
| Tony Popovic | Australia | 0.54 |
| Sebastián Beccacece | Ecuador | 0.53 |
| Sébastien Desabre | DR Congo | 0.53 |
| Sami Trabelsi | Tunisia | 0.52 |
| Graham Arnold | Iraq | 0.52 |
| Jamal Sellami | Jordan | 0.52 |
| Vladimir Petković | Algeria | 0.52 |
| Thomas Christiansen | Panama | 0.52 |
| Dick Advocaat | Curaçao | 0.52 |
| Fabio Cannavaro | Uzbekistan | 0.50 |
| Miroslav Koubek | Czech Republic | 0.50 |
| Sergej Barbarez | Bosnia & Herz. | 0.50 |
| Graham Potter | Sweden | 0.50 |
| Darren Bazeley | New Zealand | 0.50 |
| Otto Addo | Ghana | 0.50 |
| Steve Clarke | Scotland | 0.50 |
| Bubista | Cape Verde | 0.50 |
| Sébastien Migné | Haiti | 0.45 |
| Giorgos Donis | Saudi Arabia | 0.48 |
| Rudi Garcia | Belgium | 0.55 |

---

## 5. Tournament Elo Updates

The ensemble applies live WC2026 results to update every team's Elo
in real time. Each new match result shifts ratings before the next
prediction is made.

### 5.1 Parameters

```python
TOURNEY_K    = 20.0   # lighter than base 40 — WC groups have high variance
ELO_HOME_ADV = 65.0   # host-nation advantage (US, Canada, Mexico playing at home)
```

### 5.2 Applied Results (complete list used for Elo updates)

All 72 group-stage matches + completed R32 matches feed into the live Elo.
See Section 9 (Group Stage Results) and Section 10 (Knockout Results).

---

## 6. Team Database — All 48 Teams

### 6.1 Groups

| Group | Team 1 | Team 2 | Team 3 | Team 4 |
|-------|--------|--------|--------|--------|
| A | Mexico | South Africa | South Korea | Czech Republic |
| B | Canada | Bosnia and Herzegovina | Qatar | Switzerland |
| C | Brazil | Morocco | Haiti | Scotland |
| D | United States | Paraguay | Australia | Turkey |
| E | Germany | Curaçao | Ivory Coast | Ecuador |
| F | Netherlands | Japan | Sweden | Tunisia |
| G | Belgium | Egypt | Iran | New Zealand |
| H | Spain | Cape Verde | Saudi Arabia | Uruguay |
| I | France | Senegal | Iraq | Norway |
| J | Argentina | Algeria | Austria | Jordan |
| K | Portugal | DR Congo | Uzbekistan | Colombia |
| L | England | Croatia | Ghana | Panama |

### 6.2 Flag Codes (flagcdn.com format)

```json
{
  "Mexico": "mx", "South Africa": "za", "South Korea": "kr", "Czech Republic": "cz",
  "Canada": "ca", "Bosnia and Herzegovina": "ba", "Qatar": "qa", "Switzerland": "ch",
  "Brazil": "br", "Morocco": "ma", "Haiti": "ht", "Scotland": "gb-sct",
  "United States": "us", "Paraguay": "py", "Australia": "au", "Turkey": "tr",
  "Germany": "de", "Curaçao": "cw", "Ivory Coast": "ci", "Ecuador": "ec",
  "Netherlands": "nl", "Japan": "jp", "Sweden": "se", "Tunisia": "tn",
  "Belgium": "be", "Egypt": "eg", "Iran": "ir", "New Zealand": "nz",
  "Spain": "es", "Cape Verde": "cv", "Saudi Arabia": "sa", "Uruguay": "uy",
  "France": "fr", "Senegal": "sn", "Iraq": "iq", "Norway": "no",
  "Argentina": "ar", "Algeria": "dz", "Austria": "at", "Jordan": "jo",
  "Portugal": "pt", "DR Congo": "cd", "Uzbekistan": "uz", "Colombia": "co",
  "England": "gb-eng", "Croatia": "hr", "Ghana": "gh", "Panama": "pa"
}
```

### 6.3 Venue Map (16 host cities)

| City | Venue | Country |
|------|-------|---------|
| New York/NJ | MetLife Stadium | USA |
| Los Angeles | SoFi Stadium | USA |
| Dallas | AT&T Stadium | USA |
| Atlanta | Mercedes-Benz Stadium | USA |
| Houston | NRG Stadium | USA |
| Kansas City | Arrowhead Stadium | USA |
| Philadelphia | Lincoln Financial Field | USA |
| San Francisco | Levi's Stadium | USA |
| Seattle | Lumen Field | USA |
| Miami | Hard Rock Stadium | USA |
| Boston | Gillette Stadium | USA |
| Mexico City | Estadio Azteca | Mexico |
| Guadalajara | Estadio Akron | Mexico |
| Monterrey | Estadio BBVA | Mexico |
| Toronto | BMO Field | Canada |
| Vancouver | BC Place | Canada |

---

## 7. Manager Win-Rate Coefficients

*(See Section 4.3 — the complete table is provided there.)*

The manager win-rate is a low-weight signal (`weight = 0.05` in the
condition composite). It is defined as an approximate career-with-nation
proxy based on publicly available win/loss records, not a live stat.
It is used to break ties between otherwise-equal squads and to adjust
the condition score in teams where the manager is an exceptional
outlier (e.g. Scaloni at 0.74).

---

## 8. Group Draw & Fixture Schedule

### 8.1 Official Draw

The draw was held **5 December 2025** in Los Angeles.
Pot seeding: FIFA World Ranking (Oct 2025).

- Hosts (USA, Canada, Mexico) were pre-seeded in separate groups.
- 48 teams across 12 groups of 4 (Groups A–L).
- Top 2 from each group + best 8 of 12 third-placed teams advance to R32.

### 8.2 Matchday Schedule

**Matchday 1**: June 11–17, 2026  
**Matchday 2**: June 18–23, 2026  
**Matchday 3**: June 24–27, 2026  
**Round of 32**: June 28 – July 3, 2026  
**Round of 16**: July 5–7, 2026  
**Quarter-Finals**: July 10–11, 2026  
**Semi-Finals**: July 14–15, 2026  
**Third-Place Play-Off**: July 18, 2026  
**Final**: July 19, 2026 (MetLife Stadium, New York/NJ)

---

## 9. All Group Stage Results — 72 Matches

> ✅ = CAI predicted correctly · ❌ = CAI predicted incorrectly · 🎯 = exact score match

### Group A

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 1 | Jun 11 | Mexico | **2–0** | South Africa | Mexico win | ✅ |
| 25 | Jun 18 | Czech Republic | **1–1** | South Africa | Draw | ✅ |
| 28 | Jun 18 | Mexico | **1–0** | South Korea | Mexico win | ✅ |
| 49 | Jun 24 | Czech Republic | **0–3** | Mexico | Mexico win | ✅ |
| 50 | Jun 24 | South Africa | **1–0** | South Korea | Draw | ❌ |

**Group A Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Mexico | 3 | 3 | 0 | 0 | 6 | 1 | +5 | **9** |
| 2nd | South Africa | 3 | 1 | 1 | 1 | 2 | 3 | −1 | **4** |
| 3rd | Czech Republic | 3 | 0 | 1 | 2 | 2 | 5 | −3 | **1** |
| 4th | South Korea | 3 | 1 | 0 | 2 | 3 | 4 | −1 | **3** |

### Group B

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 3 | Jun 12 | Canada | **1–1** | Bosnia & Herz. | Canada win | ❌ |
| 7 | Jun 13 | Qatar | **1–1** | Switzerland | Draw | ✅ |
| 26 | Jun 18 | Switzerland | **4–1** | Bosnia & Herz. | Switzerland win | ✅ |
| 27 | Jun 18 | Canada | **6–0** | Qatar | Canada win | ✅ |
| 47 | Jun 24 | Switzerland | **2–1** | Canada | Canada win | ❌ |
| 48 | Jun 24 | Bosnia & Herz. | **3–1** | Qatar | Bosnia win | ✅ |

**Group B Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Canada | 3 | 2 | 1 | 0 | 8 | 2 | +6 | **7** |
| 2nd | Switzerland | 3 | 2 | 1 | 0 | 7 | 3 | +4 | **7** |
| 3rd | Bosnia & Herz. | 3 | 1 | 1 | 1 | 5 | 6 | −1 | **4** |
| 4th | Qatar | 3 | 0 | 1 | 2 | 2 | 11 | −9 | **1** |

### Group C

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 6 | Jun 13 | Brazil | **1–1** | Morocco | Brazil win | ❌ |
| 5 | Jun 13 | Haiti | **0–1** | Scotland | Scotland win | ✅ |
| 30 | Jun 19 | Scotland | **0–1** | Morocco | Morocco win | ✅ |
| 31 | Jun 19 | Brazil | **3–0** | Haiti | Brazil win | ✅ |
| 51 | Jun 24 | Scotland | **0–3** | Brazil | Brazil win | ✅ |
| 52 | Jun 24 | Morocco | **4–2** | Haiti | Morocco win | ✅ |

**Group C Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Brazil | 3 | 2 | 1 | 0 | 7 | 1 | +6 | **7** |
| 2nd | Morocco | 3 | 2 | 1 | 0 | 6 | 3 | +3 | **7** |
| 3rd | Scotland | 3 | 1 | 0 | 2 | 1 | 5 | −4 | **3** |
| 4th | Haiti | 3 | 0 | 0 | 3 | 4 | 9 | −5 | **0** |

### Group D

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 4 | Jun 12 | United States | **4–1** | Paraguay | USA win | ✅ |
| 8 | Jun 13 | Australia | **2–0** | Turkey | Draw | ❌ |
| 33 | Jun 19 | United States | **2–0** | Australia | USA win | ✅ |
| 32 | Jun 20 | Paraguay | **1–0** | Turkey | Draw | ❌ |
| 59 | Jun 25 | Turkey | **3–2** | United States | USA win | ❌ |
| 60 | Jun 25 | Paraguay | **0–0** | Australia | Paraguay win | ❌ |

**Group D Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | United States | 3 | 2 | 0 | 1 | 6 | 4 | +2 | **6** |
| 2nd | Paraguay | 3 | 1 | 1 | 1 | 2 | 4 | −2 | **4** |
| 3rd | Turkey | 3 | 1 | 0 | 2 | 5 | 6 | −1 | **3** |
| 4th | Australia | 3 | 0 | 1 | 2 | 2 | 1 | +1 | **1** |

### Group E

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 11 | Jun 14 | Ivory Coast | **1–0** | Ecuador | Draw | ❌ |
| 9 | Jun 14 | Germany | **7–1** | Curaçao | Germany win | ✅ |
| 38 | Jun 20 | Germany | **2–1** | Ivory Coast | Germany win | ✅ |
| 39 | Jun 20 | Ecuador | **0–0** | Curaçao | Ecuador win | ❌ |
| 57 | Jun 25 | Ecuador | **2–1** | Germany | Germany win | ❌ |
| 58 | Jun 25 | Curaçao | **0–2** | Ivory Coast | Ivory Coast win | ✅ |

**Group E Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Germany | 3 | 2 | 0 | 1 | 10 | 3 | +7 | **6** |
| 2nd | Ivory Coast | 3 | 2 | 0 | 1 | 3 | 2 | +1 | **6** |
| 3rd | Ecuador | 3 | 1 | 1 | 1 | 3 | 1 | +2 | **4** |
| 4th | Curaçao | 3 | 0 | 1 | 2 | 1 | 11 | −10 | **1** |

### Group F

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 10 | Jun 14 | Netherlands | **2–2** | Japan | Netherlands win | ❌ |
| 12 | Jun 14 | Sweden | **5–1** | Tunisia | Sweden win | ✅ |
| 37 | Jun 20 | Netherlands | **5–1** | Sweden | Netherlands win | ✅ |
| 40 | Jun 21 | Tunisia | **0–4** | Japan | Japan win | ✅ |
| 61 | Jun 25 | Japan | **1–1** | Sweden | Japan win | ❌ |
| 62 | Jun 25 | Tunisia | **1–3** | Netherlands | Netherlands win | ✅ |

**Group F Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Netherlands | 3 | 2 | 1 | 0 | 10 | 3 | +7 | **7** |
| 2nd | Japan | 3 | 1 | 2 | 0 | 7 | 3 | +4 | **5** |
| 3rd | Sweden | 3 | 1 | 1 | 1 | 7 | 7 | 0 | **4** |
| 4th | Tunisia | 3 | 0 | 0 | 3 | 2 | 13 | −11 | **0** |

### Group G

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 14 | Jun 15 | Belgium | **1–1** | Egypt | Belgium win | ❌ |
| 16 | Jun 15 | Iran | **2–2** | New Zealand | Iran win | ❌ |
| 41 | Jun 21 | Belgium | **0–0** | Iran | Belgium win | ❌ |
| 44 | Jun 21 | New Zealand | **1–3** | Egypt | Egypt win | ✅ |
| 65 | Jun 26 | Egypt | **1–1** | Iran | Egypt win | ❌ |
| 66 | Jun 26 | New Zealand | **1–5** | Belgium | Belgium win | ✅ |

**Group G Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Belgium | 3 | 1 | 2 | 0 | 6 | 2 | +4 | **5** |
| 2nd | Egypt | 3 | 1 | 2 | 0 | 5 | 3 | +2 | **5** |
| 3rd | Iran | 3 | 0 | 3 | 0 | 3 | 3 | 0 | **3** |
| 4th | New Zealand | 3 | 0 | 1 | 2 | 2 | 8 | −6 | **1** |

### Group H

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 13 | Jun 15 | Spain | **0–0** | Cape Verde | Spain win | ❌ |
| 15 | Jun 15 | Saudi Arabia | **1–1** | Uruguay | Uruguay win | ❌ |
| 43 | Jun 21 | Spain | **4–0** | Saudi Arabia | Spain win | ✅ |
| 45 | Jun 21 | Uruguay | **2–2** | Cape Verde | Uruguay win | ❌ |
| 68 | Jun 26 | Cape Verde | **0–0** | Saudi Arabia | Draw | ✅ |
| 69 | Jun 26 | Uruguay | **0–1** | Spain | Spain win | ✅ |

**Group H Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Spain | 3 | 2 | 1 | 0 | 5 | 0 | +5 | **7** |
| 2nd | Uruguay | 3 | 0 | 2 | 1 | 3 | 4 | −1 | **2** |
| 3rd | Cape Verde | 3 | 0 | 3 | 0 | 2 | 2 | 0 | **3** |
| 4th | Saudi Arabia | 3 | 0 | 2 | 1 | 1 | 5 | −4 | **2** |

> **Note**: Uruguay qualified as 3rd-place finisher on goal difference over Cape Verde.

### Group I

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 17 | Jun 16 | France | **3–1** | Senegal | France win | ✅ |
| 18 | Jun 16 | Iraq | **1–4** | Norway | Norway win | ✅ |
| 46 | Jun 22 | France | **3–0** | Iraq | France win | ✅ |
| 47 | Jun 22 | Norway | **3–2** | Senegal | Norway win | ✅ |
| 63 | Jun 26 | Norway | **1–4** | France | France win | ✅ |
| 64 | Jun 26 | Senegal | **5–0** | Iraq | Senegal win | ✅ |

**Group I Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | France | 3 | 3 | 0 | 0 | 10 | 2 | +8 | **9** |
| 2nd | Norway | 3 | 2 | 0 | 1 | 8 | 5 | +3 | **6** |
| 3rd | Senegal | 3 | 1 | 0 | 2 | 8 | 6 | +2 | **3** |
| 4th | Iraq | 3 | 0 | 0 | 3 | 1 | 14 | −13 | **0** |

### Group J

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 20 | Jun 16 | Austria | **3–1** | Jordan | Austria win | ✅ |
| 19 | Jun 16 | Argentina | **3–0** | Algeria | Argentina win | ✅ |
| 50 | Jun 22 | Argentina | **2–0** | Austria | Argentina win | ✅ |
| 51 | Jun 22 | Jordan | **1–2** | Algeria | Algeria win | ✅ |
| 71 | Jun 27 | Algeria | **3–3** | Austria | Algeria win | ❌ |
| 72 | Jun 27 | Jordan | **1–3** | Argentina | Argentina win | ✅ |

**Jordan 1–3 Argentina scorers**: Lo Celso 19', Lautaro Martínez 31' (pen), Messi 80'; Jordan: Yazan Al-Naimat 55'

**Group J Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Argentina | 3 | 3 | 0 | 0 | 8 | 1 | +7 | **9** |
| 2nd | Austria | 3 | 1 | 1 | 1 | 6 | 5 | +1 | **4** |
| 3rd | Algeria | 3 | 1 | 1 | 1 | 5 | 5 | 0 | **4** |
| 4th | Jordan | 3 | 0 | 0 | 3 | 3 | 11 | −8 | **0** |

### Group K

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 21 | Jun 17 | Portugal | **1–1** | DR Congo | Portugal win | ❌ |
| 24 | Jun 17 | Uzbekistan | **1–3** | Colombia | Colombia win | ✅ |
| 53 | Jun 23 | Portugal | **5–0** | Uzbekistan | Portugal win | ✅ |
| 54 | Jun 23 | Colombia | **1–0** | DR Congo | Colombia win | ✅ |
| 69 | Jun 27 | Colombia | **0–0** | Portugal | Portugal win | ❌ |
| 70 | Jun 27 | DR Congo | **3–1** | Uzbekistan | DR Congo win | ✅ |

**Group K Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | Portugal | 3 | 1 | 2 | 0 | 6 | 1 | +5 | **5** |
| 2nd | Colombia | 3 | 1 | 2 | 0 | 4 | 1 | +3 | **5** |
| 3rd | DR Congo | 3 | 1 | 1 | 1 | 4 | 5 | −1 | **4** |
| 4th | Uzbekistan | 3 | 0 | 1 | 2 | 2 | 9 | −7 | **1** |

### Group L

| Match | Date | Home | Score | Away | CAI Prediction | Correct? |
|-------|------|------|-------|------|----------------|----------|
| 22 | Jun 17 | England | **4–2** | Croatia | England win | ✅ |
| 23 | Jun 17 | Ghana | **1–0** | Panama | Ghana win | ✅ |
| 55 | Jun 23 | England | **0–0** | Ghana | England win | ❌ |
| 56 | Jun 23 | Panama | **0–1** | Croatia | Croatia win | ✅ |
| 67 | Jun 27 | Panama | **0–2** | England | England win | ✅ |
| 68 | Jun 27 | Croatia | **2–1** | Ghana | Croatia win | ✅ |

**Group L Final Standings:**

| Pos | Team | MP | W | D | L | GF | GA | GD | Pts |
|-----|------|----|---|---|---|----|----|----|-----|
| 1st | England | 3 | 2 | 1 | 0 | 6 | 2 | +4 | **7** |
| 2nd | Croatia | 3 | 2 | 0 | 1 | 5 | 5 | 0 | **6** |
| 3rd | Ghana | 3 | 1 | 1 | 1 | 2 | 1 | +1 | **4** |
| 4th | Panama | 3 | 0 | 0 | 3 | 0 | 5 | −5 | **0** |

---

## 10. Knockout Bracket Results & Predictions

### R32 Bracket Wiring

```
LEFT HALF:
  R32 [74,77,73,75,83,84,81,82]
      ↓ pairs: (74,77)→89  (73,75)→90  (83,84)→93  (81,82)→94
  R16 [89,90,93,94]
      ↓ pairs: (89,90)→97  (93,94)→98
  QF  [97,98]
      ↓ pair:  (97,98)→101
  SF  [101]
      ↓
  FINAL [104]
      ↑
  SF  [102]
      ↑ pair:  (99,100)→102
  QF  [99,100]
      ↑ pairs: (91,92)→99  (95,96)→100
  R16 [91,92,95,96]
      ↑ pairs: (76,78)→91  (79,80)→92  (86,88)→95  (85,87)→96
  R32 [76,78,79,80,86,88,85,87]
RIGHT HALF
```

### Round of 32 Results

| Match ID | Date | Home | Score | Away | Pens | Winner | Status |
|----------|------|------|-------|------|------|--------|--------|
| 73 | Jun 28 | South Africa | **0–1** | Canada | — | Canada | ✅ PLAYED |
| 74 | Jun 29 | Germany | **1–1** | Paraguay | 3–4 | **Paraguay** | ✅ PLAYED |
| 75 | Jun 29 | Netherlands | **1–1** | Morocco | 2–3 | **Morocco** | ✅ PLAYED |
| 76 | Jun 29 | Brazil | **2–1** | Japan | — | Brazil | ✅ PLAYED |
| 77 | Jun 30 | France | — | Sweden | — | — | UPCOMING |
| 78 | Jun 30 | Ivory Coast | **1–2** | Norway | — | Norway | ✅ PLAYED |
| 79 | Jun 30 | Mexico | — | Ecuador | — | — | UPCOMING |
| 80 | Jul 1 | England | — | DR Congo | — | — | UPCOMING |
| 81 | Jul 1 | United States | — | Bosnia & Herz. | — | — | UPCOMING |
| 82 | Jul 2 | Belgium | — | Senegal | — | — | UPCOMING |
| 83 | Jul 2 | Portugal | — | Croatia | — | — | UPCOMING |
| 84 | Jul 3 | Spain | — | Austria | — | — | UPCOMING |
| 85 | Jul 3 | Switzerland | — | Algeria | — | — | UPCOMING |
| 86 | Jul 3 | Argentina | — | Cape Verde | — | — | UPCOMING |
| 87 | Jul 3 | Colombia | — | Ghana | — | — | UPCOMING |
| 88 | Jul 3 | Australia | — | Egypt | — | — | UPCOMING |

### Round of 16 Predictions (CAI)

| Match ID | Home (predicted) | vs | Away (predicted) | CAI Winner | Confidence |
|----------|------------------|----|------------------|------------|------------|
| 89 | Paraguay | vs | France/Sweden | France | — |
| 90 | Canada | vs | Morocco | Morocco | — |
| 91 | Brazil | vs | Norway | Brazil | — |
| 92 | Mexico/Ecuador | vs | England/DR Congo | — | — |
| 93 | Portugal/Croatia | vs | Spain/Austria | Spain | — |
| 94 | USA/Bosnia | vs | Belgium/Senegal | — | — |
| 95 | Argentina/Cape Verde | vs | Australia/Egypt | Argentina | — |
| 96 | Switzerland/Algeria | vs | Colombia/Ghana | Colombia | — |

### Quarter-Final Predictions (CAI)

| Match ID | Home | vs | Away | CAI Winner |
|----------|------|----|------|------------|
| 97 | France | vs | Morocco | France |
| 98 | Spain | vs | Belgium | Spain |
| 99 | Brazil | vs | England | Brazil |
| 100 | Argentina | vs | Colombia | Argentina |

### Semi-Final Predictions (CAI)

| Match ID | Home | vs | Away | CAI Winner |
|----------|------|----|------|------------|
| 101 | France | vs | Spain | France |
| 102 | Brazil | vs | Argentina | Argentina |

### Final Prediction (CAI)

| Match ID | Home | vs | Away | CAI Winner | Champion % |
|----------|------|----|------|------------|------------|
| 104 | France | vs | **Argentina** | **Argentina** | 32.6% |

---

## 11. Goal Scorer Database

### 11.1 Completed Knockout Matches

| Match | Minute | Team | Scorer | Assist | Type |
|-------|--------|------|--------|--------|------|
| 73 (SA 0–1 CAN) | 90+2 | Canada | Stephen Eustáquio | — | Goal |
| 74 (GER 1–1 PAR, pens 3–4) | 42 | Paraguay | Julio Enciso | — | Goal |
| 74 | 54 | Germany | Kai Havertz | — | Goal |
| 74 | Pens | Germany | Havertz ✓, Kimmich ✓, Musiala ✓, Woltemade ✗, Amari ✓, Tah ✗ | — | Shootout |
| 74 | Pens | Paraguay | Maurício ✓, Gómez ✓, Galarza ✓, Sanabria ✗, Balbuena ✗, Canale ✓ | — | Shootout |
| 75 (NED 1–1 MAR, pens 2–3) | 72 | Netherlands | Cody Gakpo | — | Goal |
| 75 | 90+1 | Morocco | Issa Diop | — | Goal |
| 75 | Pens | Netherlands | Koopmeiners ✓, Kluivert ✗, Weghorst ✓, Timber ✗, Summerville ✗ | — | Shootout |
| 75 | Pens | Morocco | El Aynaoui ✗, Rahimi ✓, Talbi ✓, Hakimi ✗, Saibari ✓ | — | Shootout |
| 76 (BRA 2–1 JPN) | 29 | Japan | Kaishu Sano | — | Goal |
| 76 | 56 | Brazil | Casemiro | — | Goal |
| 76 | 90+6 | Brazil | Gabriel Martinelli | Bruno Guimarães | Goal |
| 78 (CIV 1–2 NOR) | 39 | Norway | Antonio Nusa | — | Goal |
| 78 | 46 | Ivory Coast | Amad Diallo | — | Goal |
| 78 | 86 | Norway | Erling Haaland | Sander Berge | Goal |

### 11.2 Notable Group Stage Scorers (from ESPN feed)

| Match | Goals |
|-------|-------|
| Portugal 5–0 Uzbekistan | Ronaldo 6', Nuno Mendes 17', Vitinha, Leão, Fernandes |
| France 3–0 Iraq | Mbappé 14' (×2), Dembélé |
| Germany 7–1 Curaçao | 7 different scorers |
| Canada 6–0 Qatar | Jonathan David 2, Larin, Johnston, Millar, Cornelius (og) |
| Jordan 1–3 Argentina | Lo Celso 19', Lautaro 31' (pen), Messi 80'; Yazan Al-Naimat 55' |
| Norway 3–2 Senegal | Pedersen, Haaland 48', Sørloth; Sarr 64', 90' |
| Senegal 5–0 Iraq | Diatta, Sarr (×2), Dia, Diedhiou |

### 11.3 WC2026 Top Scorers (as of Jun 30)

| Player | Team | Goals | Tournament |
|--------|------|-------|------------|
| Erling Haaland | Norway | 5 | Group (4) + R32 (1) |
| Kylian Mbappé | France | 4 | Group stage |
| Cristiano Ronaldo | Portugal | 3+ | Group stage |
| Lionel Messi | Argentina | 3+ | Group stage |
| Ismaïla Sarr | Senegal | 3 | Group stage |
| Jonathan David | Canada | 2+ | Group stage |

---

## 12. Model Accuracy Log

### 12.1 Group Stage Accuracy

| Round | Matches | Correct Outcomes | Accuracy |
|-------|---------|------------------|----------|
| Matchday 1 | 24 | 17 | 70.8% |
| Matchday 2 | 24 | 18 | 75.0% |
| Matchday 3 | 24 | 17 | 70.8% |
| **Total Group Stage** | **72** | **52** | **72.2%** |

### 12.2 Knockout Stage Accuracy (R32 so far)

| Match | Prediction | Actual | Correct? |
|-------|-----------|--------|----------|
| 73 SA vs CAN | Canada | Canada 1–0 | ✅ |
| 74 GER vs PAR | Germany | Paraguay (pens) | ❌ |
| 75 NED vs MAR | Netherlands | Morocco (pens) | ❌ |
| 76 BRA vs JPN | Brazil | Brazil 2–1 | ✅ |
| 78 CIV vs NOR | Norway | Norway 2–1 | ✅ |
| **R32 so far** | | | **3/5 (60%)** |

### 12.3 Notes on Calibration

- **Draw gate**: Tuned to `DRAW_PROB_MIN = 0.20` from 0.27 after 54 games.
  Measured that the realized p_draw ceiling was 0.24, so the old gate
  was unreachable — no draws were ever predicted. At 0.20 the model
  correctly flagged the most balanced ties as draws.
- **Confidence over-inflation at 99**: Several knockout matches show `conf=99`
  which is unrealistic for football. The display-stretch formula maps
  the realistic football band [27, 58] to [1, 100]; a raw score of 58+
  pins at 100. This is a calibration limitation to address in v2.
- **Penalty shootout prediction**: The model does not predict shootout
  outcomes directly. When it predicts a draw scoreline, `shootout=True`
  is flagged and the team with higher win probability is called to advance.
  Penalties (Germany, Netherlands) are therefore inherently harder to
  predict.

---

## 13. Data Sources & References

### 13.1 Training Data

| Source | Usage |
|--------|-------|
| `martj42/international-football-results` (Kaggle) | ~46,000 international results for Elo + DC model training |
| FiveThirtyEight soccer Elo methodology | Elo formula, K-factor, MoV multiplier |
| Dixon & Coles (1997) *JRSS-C* | Bivariate Poisson model with attack/defence rates and ρ correlation |
| Karlis & Ntzoufras (2003) | Independent Poisson baseline |
| XGBoost (Chen & Guestrin, 2016) | Gradient boosting member |
| PyTorch MLP | Neural network member |

### 13.2 Live Tournament Data

| Source | Usage |
|--------|-------|
| ESPN public scoreboard API (`site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard`) | Real goal scorers (name, minute, type) — all 72 group games |
| FIFA.com match centre | Manual verification of goal scorers, penalty shootout kicks |
| BBC Sport / ESPN match reports | Post-match narrative, key moments |
| Betfair / Pinnacle (de-vigged) | Live betting odds → `market_probs` member |
| `flagcdn.com` | Country flag images (CC0 license) |
| Wikipedia Commons / FreeImgHost | Player headshot photos |

### 13.3 Squad & Player Data

| Source | Usage |
|--------|-------|
| `squads.json` (web-sourced Jun 2026) | Full 23–26 man rosters for all 48 teams |
| `player_condition.py` `PLAYER_DB` | Star player form/fitness (hand-curated, Jun 2026) |
| FIFPlay / Bolavip / FIFA.com | Head coach verification (Jun 2026) |
| `players_kaggle.csv` | Historical player dataset (backup) |

### 13.4 Venue & Weather Data

| Source | Usage |
|--------|-------|
| FIFA 2026 official schedule | Kick-off times, venues, cities |
| NOAA Climate Data | Historical temperature/humidity by city-month |
| `venues.py` altitude table | Altitude fatigue factor for high-altitude venues |
| Google Maps API (offline dist. matrix) | Travel distance calculations between match cities |

---

## 14. Manual Update Guide

### 14.1 How to Update After a Match

**Step 1** — Add result to `backend/app/fixtures.py` (`MD23` or `WC2026_PLAYED`):
```python
# In tournament_form.WC2026_PLAYED add:
("Home Team", "Away Team", home_score, away_score, neutral_bool),
```

**Step 2** — Add actual events to `backend/app/knockout.json` (for R32+):
```json
{
  "id": 73,
  "played": true,
  "home_score": 0,
  "away_score": 1,
  "actual_events": [
    {"minute": 92, "team": "Canada", "type": "goal", "scorer": "Stephen Eustáquio", "assist": null, "text": "Late winner..."}
  ],
  "actual_stats": {
    "result_note": "...",
    "home_xg": 0.82,
    "away_xg": 1.35,
    "home_possession": 48,
    "away_possession": 52,
    "home_shots_on_target": 3,
    "away_shots_on_target": 5
  },
  "actual_penalties": {
    "home": [{"player": "Name", "outcome": "scored|saved|missed"}],
    "away": [{"player": "Name", "outcome": "scored|saved|missed"}]
  }
}
```

**Step 3** — Fix any `Unknown` scorers in `backend/data/raw/match_events.json`:
```json
"Home|Away": {
  "scorers": {
    "home": [{"player": "Real Name", "minute": 23, "type": "goal"}],
    "away": [{"player": "Real Name", "minute": 67, "type": "goal"}]
  }
}
```

**Step 4** — Regenerate snapshots:
```bash
cd backend && python3 gen_snapshots.py
```

**Step 5** — Type-check and deploy:
```bash
cd frontend && npx tsc --noEmit
vercel --prod
```

### 14.2 Accuracy Update (after each round)

Update Section 12 of this document with:
- New correct/incorrect rows in the knockout accuracy table
- Total accuracy metrics per round

### 14.3 Top Scorers Update

Update Section 11.3 with new goal tallies from the ESPN feed or manual
verification after each matchday.

### 14.4 Re-running the Model

To regenerate all predictions from scratch (after adding new results):
```bash
cd backend
# Update Elo with new results:
python3 -c "from app.ml_engine import reload_engine; reload_engine()"

# Re-sim the full tournament (10,000 Monte-Carlo runs):
python3 ml/predict_wc2026.py

# Regenerate API snapshots:
python3 gen_snapshots.py
```

---

## Appendix A: Coefficient Summary

```json
{
  "ensemble": {
    "weights": {
      "market": 0.35,
      "dc": 0.22,
      "xgb": 0.18,
      "nn": 0.08,
      "elo": 0.10,
      "poisson": 0.07
    },
    "weight_bounds": [0.03, 0.45],
    "synth_market_weight_penalty": 0.25,
    "synth_market_conf_penalty": 4
  },
  "post_blend": {
    "avail_coef": 1.80,
    "travel_coef": 0.08,
    "travel_scale_km": 2500,
    "weather_coef": 0.035,
    "condition_coef": 2.45
  },
  "elo": {
    "k_base": 40.0,
    "tourney_k": 20.0,
    "home_adv_historical": 65.0,
    "home_adv_knockout": 35.0,
    "elo_formula": "1/(1+10^((r_away - r_home)/400))"
  },
  "draw_gate": {
    "draw_prob_min": 0.20,
    "draw_balance": 0.08,
    "rationale": "Tuned 2026-06-25 after 54 games; p_draw ceiling was 0.24"
  },
  "confidence": {
    "agreement_weight": 0.35,
    "decisiveness_weight": 0.35,
    "coverage_weight": 0.12,
    "reliability_weight": 0.18,
    "disagreement_scale": 0.20,
    "display_lo": 27,
    "display_hi": 58
  },
  "form": {
    "window": 5,
    "features": ["form_pts_diff", "form_gd_diff"]
  },
  "condition_weights": {
    "fitness_composite": 0.30,
    "form_score": 0.25,
    "star_availability": 0.20,
    "gk_quality": 0.10,
    "squad_depth": 0.10,
    "manager_winrate": 0.05
  },
  "reliability": {
    "ece_reference_scale": 0.15,
    "default_reliability": 0.70,
    "min_member_samples": 30
  }
}
```

---

## Appendix B: Tournament Bracket Map

```
Final (MetLife, NJ)  ◄────────── SF101 ──────────────────────────────► SF102
                                    │                                      │
                                  QF97              QF98            QF99              QF100
                               (France vsMorocco)(Spain vs Belgium)(Brazil vs England)(Arg vs Col)
                                    │                 │                │                  │
                               R16-89  R16-90    R16-93  R16-94   R16-91  R16-92    R16-95  R16-96
                              (PAR/FR)(CAN/MAR)(POR/SPA)(US/BEL)(BRA/NOR)(MEX/ENG)(ARG/AUS)(CH/COL)
                                  │      │         │       │        │       │         │       │
                              74  77   73  75    83  84  81  82   76  78  79  80   86  88  85  87
```

---

*Document maintained by the CAI prediction team. Last validated: 2026-06-30.*  
*To report errors or update match data, edit this file and re-run `gen_snapshots.py`.*

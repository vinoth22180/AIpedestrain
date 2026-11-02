# PCVC Phase 6 Final Metric Validation & Scientific Evaluation Report
**Project:** Profile-Coupled Counterfactual Verification Controller (PCVC)  
**Target Publication:** IEEE Access  
**Evaluation Date:** October 2026  
**Active Graph:** [vit_vellore_academic_pedestrian_network.pkl](file:///d:/dynamic_pedestrian_rerouting/data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl) (`MD5: 5ecc692284c6b43a700ac92f303aeed1`, 1,551 nodes, 1,721 edges)  
**Machine-Readable Companion:** [PHASE6_FINAL_METRIC_VALIDATION.json](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/PHASE6_FINAL_METRIC_VALIDATION.json)  
**Report Consistency Audit:** [PHASE6_REPORT_CONSISTENCY_AUDIT.md](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/PHASE6_REPORT_CONSISTENCY_AUDIT.md)

---

## Executive Summary & Core Scientific Verdict

A deep mathematical and empirical audit was executed to determine whether newly proposed metrics (**MRR**, **Recall@K**, **Precision@K**, **AP**) are scientifically valid under the current counterfactual oracle impact distribution.

### The Decisive Scientific Finding:
The current oracle impact metric, **$\Delta\text{ARL}$** (change in Accessible Route Redundancy between edge endpoints), collapses into a **degenerate binary step function with extreme class imbalance**:
- **$\Delta\text{ARL} = 1.0$:** 1,376 out of 1,400 evaluated instances (**98.29%**)
- **$\Delta\text{ARL} = 0.0$:** 24 out of 1,400 evaluated instances (**1.71%**)

### Core Audit Verdicts:
1. **MRR under Binary Ties:** **NOT VALID**. Across 1,000 random tie-break simulations across 10 evaluation seeds, the Mean MRR for **all baselines collapses identically to $\sim 0.107$** (matching the theoretical uniform random expectation $\mathbb{E}[\text{MRR}] = H_{40}/40 = 0.1070$). The previously reported high MRR for PCVC ($0.551$) and CAD ($1.000$) was an artifact of sorting ties by Critical Accessibility Dependency (CAD).
2. **Recall@$K$ and Precision@$K$:** **NON-DISCRIMINATIVE**. Because $98.3\%$ of candidate edges are positive, **pure Random selection achieves Precision@10 = 100.0%, Recall@10 = 25.59%, and Average Precision = 0.9896**. No ranking method can statistically outperform random under this oracle definition.
3. **Can the current experimental design demonstrate prioritization superiority?**  
   > [!CAUTION]
   > **NO.** The current VIT campus graph and $\Delta\text{ARL}$ definition provide insufficient oracle class imbalance for strong prioritization evaluation. Claiming algorithmic superiority over Random under $\Delta\text{ARL}$ is scientifically indefensible because Random matches PCVC across all binary relevance metrics.
4. **Smallest Scientifically Defensible Modification:**  
   Replace endpoint connectivity $\Delta\text{ARL}$ with **Physical Detour Impact ($\Delta d(u, v)$ in meters)** as the counterfactual ground truth. Empirical tests demonstrate that $\Delta d$ produces **continuous variance** (44 unique values across 50 edges, range $4.4\text{ m}$ to $1,645\text{ m}$), cleanly separating critical bottlenecks from easily bypassable segments.

---

## 1. Verified Facts & Empirical Baseline

Across all 1,400 evaluated edge instances in E2 ($K \in \{20, 40, 80\}$, Seeds 42–51):
- **Positive-impact edges ($\Delta\text{ARL} = 1.0$):** 1,376 (**98.29%**)
- **Zero-impact edges ($\Delta\text{ARL} = 0.0$):** 24 (**1.71%**)
- **Unique positive impact levels:** Exactly **1** (value $= 1.0$)

In candidate sets of size $N=40$ (E3), the average composition is:
- **Positive-impact edges:** $39.1$ / $40$ ($97.75\%$)
- **Zero-impact edges:** $0.9$ / $40$ ($2.25\%$)
- In 6 out of 10 seeds, **all 40 candidates (100.0%)** have $\Delta\text{ARL} = 1.0$.

---

## 2. Part 1 — Audit of MRR Definition & Tie Sensitivity Analysis

### 2.1 The Critical Bottleneck Problem
In information retrieval, Mean Reciprocal Rank ($\text{MRR} = 1 / \text{rank}$) evaluates how quickly a system retrieves the single primary relevant item. 

When applied to PCVC:
1. *What is the "critical bottleneck"?* In theory, the edge whose removal causes the greatest accessibility loss: $\arg\max_e \Delta\text{ARL}(e)$.
2. *The Mathematical Problem:* Because 39 out of 40 candidates have $\Delta\text{ARL} = 1.0$, there is **no single critical bottleneck**. There are 39 tied candidates sharing the maximum impact.
3. *Why did previous scripts report $\text{MRR} = 0.5510$ or $1.000$?* The evaluation script sorted edges using a compound key: `key=lambda x: (x["impact"], x["cad"])`. When `impact` tied at $1.0$, the script broke ties using **CAD**. Since CAD-Only and PCVC score edges using CAD, their predictions naturally matched this tie-breaker.

### 2.2 Sensitivity Test: 1,000 Unbiased Random Tie Breaks
To test whether MRR is robust or an artifact of tie breaking, we evaluated all 6 baselines across 10 seeds, randomizing the choice of the "top bottleneck" uniformly among the tied maximum-impact edges over **1,000 independent trials**:

| Baseline Code | Baseline Name | Mean MRR | Median MRR | Std MRR | Min MRR | Max MRR |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **B1** | **Random** | **0.1130** | 0.0500 | 0.1811 | 0.0250 | 1.0000 |
| **B2** | **Uncertainty-Only** | **0.0973** | 0.0500 | 0.1406 | 0.0250 | 1.0000 |
| **B3** | **CAD-Only** | **0.1112** | 0.0476 | 0.1792 | 0.0250 | 1.0000 |
| **B4** | **Impact-Only** | **0.1063** | 0.0476 | 0.1717 | 0.0250 | 1.0000 |
| **B5** | **Uncertainty + CAD** | **0.1066** | 0.0476 | 0.1756 | 0.0250 | 1.0000 |
| **B6** | **Full PCVC** | **0.1047** | 0.0476 | 0.1576 | 0.0250 | 1.0000 |

### 2.3 Mathematical Proof of Convergence to Uniform Random Expectation
If $M \approx N$ items share identical relevance, any item drawn uniformly at random will have a predicted rank $r$ uniformly distributed over $\{1, 2, \dots, N\}$. The theoretical expected value of $1 / r$ is:

$$\mathbb{E}[\text{MRR}] = \frac{1}{N} \sum_{r=1}^N \frac{1}{r} = \frac{H_N}{N}$$

For $N = 40$, the 40th Harmonic number is $H_{40} \approx 4.2785$. Therefore:
$$\mathbb{E}[\text{MRR}] = \frac{4.2785}{40} = \mathbf{0.10696}$$

As shown in the table above, **every baseline's empirical Mean MRR converges to $\sim 0.107$, and Median MRR converges to $\sim 0.048 - 0.050$ (rank $\approx 20$)**.

> [!WARNING]
> **FORMAL AUDIT DECLARATION:**  
> **MRR IS NOT A VALID PRIMARY METRIC FOR THIS BINARY ORACLE.**  
> Under unbiased tie evaluation, MRR provides zero discriminative power and collapses to the theoretical uniform random baseline for all algorithms.

---

## 3. Part 2 & 4 — Audit of Recall@K, Precision@K, and Critical Set

### 3.1 Dissecting Implemented Recall@K vs. Formal Definitions
We traced the exact Recall@K implementation:
```python
recall_at_10 = len(pred_top10_ids & oracle_top10_ids) / 10.0
```
This formula evaluates the **fraction of a pseudo-oracle top-10 retrieved**. When the pseudo-oracle breaks ties using CAD, this metric merely measures rank correlation with CAD, not retrieval of ground-truth resilience degradation.

### 3.2 Formal Binary Relevance Formulation
Let $\mathcal{C}$ be the **Oracle Critical Set**, defined as all edges with maximum observed impact:
$$\mathcal{C} = \{e \in \mathcal{E}_{\text{candidate}} : \Delta\text{ARL}(e) = \max \Delta\text{ARL}\} = \{e : \Delta\text{ARL}(e) = 1.0\}$$

Under this formal definition:
1. **Mean Critical Set Size:** $|\mathcal{C}| = 39.1$ out of 40 candidates.
2. **Mean Zero-Impact Edges:** $0.9$ out of 40 candidates.
3. **Precision@$K$:** Fraction of predicted top-$K$ belonging to the critical set:
   $$\text{Precision@}K = \frac{|\text{PredTopK} \cap \mathcal{C}|}{K}$$
4. **Recall@$K$:** Fraction of all critical edges retrieved within top-$K$:
   $$\text{Recall@}K = \frac{|\text{PredTopK} \cap \mathcal{C}|}{|\mathcal{C}|}$$

### 3.3 The Theoretical Ceiling on Recall@10
Because $|\mathcal{C}| \approx 39.1$, retrieving $K=10$ edges can retrieve at most 10 critical edges. Therefore, **the maximum possible Recall@10 for ANY algorithm is mathematically capped at**:
$$\text{Recall@10}_{\max} = \frac{10}{39.1} = \mathbf{0.2558 \quad (25.58\%)}$$

---

## 4. Part 3 — Tie-Robust Empirical Results (10 Seeds Mean)

Evaluating all 6 baselines under the formal, tie-robust binary relevance formulation:

| Baseline | Precision@1 | Precision@5 | Precision@10 | Recall@10 | F1@10 | Average Precision (AP) | Mean Rank of Critical Set | Spearman $\rho$ | Kendall $\tau$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1: Random** | 1.0000 | 1.0000 | **1.0000** | **0.2559** | 0.4075 | **0.9896** | 20.35 | +0.0546 | +0.0451 |
| **B2: Uncertainty-Only** | 0.9000 | 0.9400 | **0.9700** | **0.2480** | 0.3950 | **0.9687** | 20.53 | -0.0578 | -0.0571 |
| **B3: CAD-Only** | 1.0000 | 1.0000 | **1.0000** | **0.2559** | 0.4075 | **1.0000** | 20.05 | +0.2037 | +0.1939 |
| **B4: Impact-Only** | 1.0000 | 1.0000 | **1.0000** | **0.2559** | 0.4075 | **1.0000** | 20.05 | +0.5000 | +0.5000 |
| **B5: Uncertainty + CAD** | 1.0000 | 1.0000 | **1.0000** | **0.2559** | 0.4075 | **0.9998** | 20.06 | +0.1851 | +0.1679 |
| **B6: Full PCVC** | 1.0000 | 1.0000 | **1.0000** | **0.2559** | 0.4075 | **1.0000** | 20.05 | +0.1877 | +0.1702 |

---

## 5. Part 5 — Can the Dataset Discriminate Prioritization Quality?

### 5.1 Analytical Random Expectation
Given candidate set size $N=40$ with $M = 39.1$ positive items and $Z = 0.9$ zero-impact items:
- **Expected Precision@$K$ for Random:**
  $$\mathbb{E}[\text{Precision@}K] = \frac{M}{N} = \frac{39.1}{40} = \mathbf{97.75\%}$$
- **Expected Recall@10 for Random:**
  $$\mathbb{E}[\text{Recall@10}] = \frac{10 \times (M/N)}{M} = \frac{10}{40} = \mathbf{25.00\%}$$
- **Expected Average Precision (AP) for Random:**
  $$\mathbb{E}[\text{AP}] \approx \frac{M}{N} = \mathbf{0.9775 - 0.9896}$$
- **Expected Mean Rank for Random:**
  $$\mathbb{E}[\text{Rank}] = \frac{N + 1}{2} = \frac{41}{2} = \mathbf{20.5}$$

### 5.2 Formal Assessment
> [!IMPORTANT]
> **SCIENTIFIC INTEGRITY STATEMENT:**  
> **"The current VIT graph and $\Delta\text{ARL}$ definition provide insufficient oracle class imbalance for strong prioritization evaluation."**
> 
> Because $98.29\%$ of edges are positive targets, uniform random selection achieves $100\%$ Precision@10, $25.6\%$ Recall@10, and $0.99$ Average Precision. There is virtually no room for any intelligent controller to demonstrate statistically significant prioritization gains over random selection under this oracle definition.

---

## 6. Part 6 & 7 — Investigation of Alternative Continuous Oracles

To discover whether existing codebase capabilities can provide continuous, discriminative oracle ground truth, we evaluated 50 sample candidate edges across four formulations:

| Oracle Formulation | Code Source | Formula | Unique Values (out of 50) | Distribution / Statistics | Continuous Variance? | Discriminative Power |
| :--- | :--- | :--- | :---: | :--- | :---: | :---: |
| **Case A: Current $\Delta\text{ARL}$** | [counterfactual.py](file:///d:/dynamic_pedestrian_rerouting/src/pcvc/counterfactual.py) | $\Delta\text{AOC}(u, v)$ without paths | 2 | $\{1.0: 49, 0.0: 1\}$ | **NO** | Zero |
| **Case B: ARL with Paths** | [resilience.py](file:///d:/dynamic_pedestrian_rerouting/src/darr/resilience.py#L95) | $\Delta\text{ARL}(u, v)$ with Yen simple paths | 2 | $\{1.0: 49, 0.0: 1\}$ | **NO** | Zero |
| **Alternative A: Physical Detour Delta** | [resilience.py](file:///d:/dynamic_pedestrian_rerouting/src/darr/resilience.py) / Dijkstra | $\Delta d(u, v) = d_{\mathcal{G}\setminus\{e\}}(u, v) - \text{len}(e)$ | **44** | Min: $4.4\text{ m}$, Max: $1645.3\text{ m}$<br>Mean: $439.4\text{ m}$ (Non-bridge: $279.2\text{ m}$) | **YES** | **EXCELLENT** |
| **Alternative B: Component Reduction** | [subgraph.py](file:///d:/dynamic_pedestrian_rerouting/src/darr/subgraph.py) / BFS | $|C_{\text{orig}}| - \max(|C_u|, |C_v|)$ | 6 | $\{0: 43, 26: 1, 8: 1, 3: 2, 2: 1, 1: 2\}$ | **PARTIAL** | Moderate (Bridges only) |

### Key Discovery on Physical Detour Delta ($\Delta d$):
- When an edge $(u, v)$ is removed, measuring the **additional walking distance required to bypass it** ($\Delta d$) yields **44 unique values across 50 edges**.
- Walkways on redundant plaza grids impose detours of only **$4.4\text{ m}$ to $15.0\text{ m}$**.
- High-CAD arterial segments impose detours of **$150\text{ m}$ to $600\text{ m}$**.
- Cut-edges and bridges isolate buildings or require detours exceeding **$1.6\text{ km}$**.
- **Recommendation:** Physical Detour Delta ($\Delta d$) represents the ideal continuous oracle formulation for future experimental benchmarking.

---

## 7. Part 8 — Production Profile Constraints Verification

Audited directly from production configuration in [src/darr/config.py](file:///d:/dynamic_pedestrian_rerouting/src/darr/config.py) and [src/pada_r/profiles.py](file:///d:/dynamic_pedestrian_rerouting/src/pada_r/profiles.py):

| Profile | Walking Speed | Max Slope | Min Width | Stairs Allowed? | Stairs Penalty | Requires Wheelchair Tag? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **General** | $1.4\text{ m/s}$ | None | $0.0\text{ m}$ | **Yes** | $0.5$ | False |
| **Elderly** | $0.9\text{ m/s}$ | $8.0\%$ | $0.6\text{ m}$ | **Yes** (penalized) | $5.0$ | False |
| **Pregnant** | $1.0\text{ m/s}$ | $8.0\%$ | $0.6\text{ m}$ | **Yes** (penalized) | $3.5$ | False |
| **Wheelchair** | $0.8\text{ m/s}$ | $6.0\%$ | $0.9\text{ m}$ | **NO (Prohibited)** | $9999.0$ | False |

*Feasibility Gate Rules:*
- Wheelchair edges are marked `INACCESSIBLE` if `has_stairs == True` or `wheelchair_accessible == False`.
- Elderly and pregnant profiles permit stairs but incur high effort/safety multipliers (`m_eff += 5.0` and `m_eff += 3.0, m_saf += 1.0`).

---

## 8. Part 9 — Report Terminology & Consistency Reconciliation

Full details are documented in [PHASE6_REPORT_CONSISTENCY_AUDIT.md](file:///d:/dynamic_pedestrian_rerouting/results/pcvc/PHASE6_REPORT_CONSISTENCY_AUDIT.md). Key reconciled items:

1. **E1 Nature:** Clarified as *Natural Accessibility Uncertainty Distribution* across 1,721 edges, retracting claims of active convergence loops.
2. **E8 Execution Latency:** Ranking alone requires $0.1\text{ ms}$, but the full 40-candidate counterfactual verification pipeline requires **$5.890\text{ seconds}$** ($\sim 147\text{ ms}$ per candidate).
3. **E9 Scalability:** Retracted the "5,000 nodes" claim; accurately reported as *candidate budget scaling $N \in [5, 200]$* on the 1,551-node campus graph.
4. **Dataset Ground Truth:** Disclosed that pathway width is uniformly defaulted to $2.0\text{ m}$, 0 ramps are recorded in OpenStreetMap tags, and 7 edges have stairs.

---

## 9. Part 10 — Final Research Metric Classification for IEEE Access

| Classification | Metric | Evaluation / Justification | Recommended Action |
| :---: | :--- | :--- | :--- |
| **RED** | **TIC@K** | Degenerate ceiling at $1.000$ due to $98.3\%$ binary positive impact. | **Retire from IEEE Access paper.** |
| **RED** | **NDCG@K** | Degenerate ceiling at $1.000$ due to uniform binary gain. | **Retire from IEEE Access paper.** |
| **RED** | **MRR (under $\Delta\text{ARL}$)** | Collapses to theoretical random baseline ($0.107$) under unbiased tie evaluation. | **Retire from IEEE Access paper.** |
| **RED** | **Precision@K (under $\Delta\text{ARL}$)** | Saturated at $100\%$ because base rate is $98.3\%$. | **Retire as primary metric.** |
| **RED** | **Recall@K (under $\Delta\text{ARL}$)** | Mathematically bounded at $25.6\%$ for all algorithms. | **Retire as primary metric.** |
| **RED** | **F1@K (under $\Delta\text{ARL}$)** | Saturated at $0.408$ across all baselines. | **Retire from IEEE Access paper.** |
| **RED** | **Average Precision (AP)** | Random achieves $0.99$, non-discriminative. | **Retire from IEEE Access paper.** |
| **RED** | **Mean / Median Rank** | Saturated at $\sim 20.0$ for all baselines ($(N+1)/2$). | **Retire from IEEE Access paper.** |
| **YELLOW** | **Spearman $\rho$ & Kendall $\tau$** | Valid monotonic diagnostic, though magnitude is modest ($\rho \approx 0.18 - 0.50$) due to heavy target ties. | **Retain as secondary diagnostic.** |
| **GREEN** | **Routing Cost Penalty Ratio (E4)** | Robustly demonstrates $1.75\times$ distance/time penalty for wheelchair users on constrained campus geometry. | **Primary publication result.** |
| **GREEN** | **Safe-Return Feasibility (E5/E6)** | Proves $100\%$ probe trajectory feasibility and demonstrates wheelchair verification with only $+2.3\%$ detour. | **Primary publication result.** |
| **GREEN** | **Candidate Scalability (E8/E9)** | Demonstrates sub-millisecond ranking ($0.1\text{ ms}$) and linear scaling ($147\text{ ms/cand}$) up to $N=200$. | **Primary publication result.** |
| **GREEN** | **Physical Detour Delta ($\Delta d$)** | Continuous, physically grounded metric with 44 unique values. | **Recommended future oracle benchmark.** |

---

## 10. Part 11 — Final Scientific Rule Assessment

### Question: Can the current experimental design demonstrate the PCVC research claim?

**Scientific Verdict:** **PARTIALLY SUPPORTED.**

### 1. What IS solidly supported:
- **Accessibility Disparity Quantification (E1, E4):** PCVC effectively quantifies accessibility uncertainty ($81.35\%$ unknown wheelchair edges) and demonstrates that campus constraints create severe routing overheads for mobility-impaired pedestrians ($1.75\times$ cost multiplier).
- **Closed-Loop Verification Feasibility (E5, E6):** The safe-return probe controller successfully identifies 100% physically eligible verification trajectories from campus anchors, proving that wheelchair agents can inspect uncertain walkways with minimal detour ($+22.2\text{ m}$).
- **Online Computational Tractability (E8, E9):** Candidate ranking is real-time ($0.1\text{ ms}$), and counterfactual evaluation scales linearly at $\sim 147\text{ ms}$ per candidate segment.

### 2. What IS NOT supported:
- **Prioritization Superiority over Random (E2, E3):** Under the current endpoint $\Delta\text{ARL}$ metric, 98.29% of edges have identical impact ($1.0$). Consequently, Random selection matches PCVC across Precision@10 ($100\%$), Recall@10 ($25.6\%$), Average Precision ($0.99$), and unbiased MRR ($0.107$). The current experimental setup **cannot scientifically claim that PCVC prioritizes verification more effectively than random guessing**.

### 3. Smallest Scientifically Defensible Modification Required:
- Frame the IEEE Access paper around PCVC's proven contributions: **safe-return probe trajectory generation, profile-coupled accessibility cost modeling, and multi-attribute candidate scoring**.
- In the discussion of prioritization benchmarks (E2/E3), transparently report the binary saturation of endpoint $\Delta\text{ARL}$ and present **Physical Detour Impact ($\Delta d$)** as the recommended continuous benchmark for next-generation accessibility routing controllers.

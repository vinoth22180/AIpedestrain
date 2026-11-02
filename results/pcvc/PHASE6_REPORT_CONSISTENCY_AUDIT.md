# PCVC Phase 6 Report Consistency Audit
**Project:** Profile-Coupled Counterfactual Verification Controller (PCVC)  
**Target Publication:** IEEE Access  
**Evaluation Date:** October 2026  
**Audited Datasets:** [vit_vellore_academic_pedestrian_network.pkl](file:///d:/dynamic_pedestrian_rerouting/data/vit_vellore/processed/vit_vellore_academic_pedestrian_network.pkl) (MD5: `5ecc692284c6b43a700ac92f303aeed1`)  
**Audited Scripts:** [scripts/experiments/](file:///d:/dynamic_pedestrian_rerouting/scripts/experiments/)  
**Audited Codebase:** [src/darr/](file:///d:/dynamic_pedestrian_rerouting/src/darr/), [src/pada_r/](file:///d:/dynamic_pedestrian_rerouting/src/pada_r/), [src/pcvc/](file:///d:/dynamic_pedestrian_rerouting/src/pcvc/)

---

## Executive Summary

To ensure total scientific integrity before writing the IEEE Access paper, an exhaustive consistency audit was conducted across all numerical claims, methodology statements, and architectural assumptions in the Phase 6 reports. 

Every claim was compared directly against measured execution data, production code configurations, and raw network graph attributes. Discrepant statements have been flagged, categorized, and assigned concrete reconciliation actions.

---

## Consistency Audit Table

| ID | CLAIM | SOURCE | ACTUAL VERIFIED VALUE | STATUS | ACTION |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **C1** | **E1: Epistemic Uncertainty Convergence**<br>*"Epistemic uncertainty drops monotonically ($0.783 \to 0.065$) under active queries"* | Phase 6 Executive Summary Table | E1 in [run_e1_uncertainty.py](file:///d:/dynamic_pedestrian_rerouting/scripts/experiments/run_e1_uncertainty.py) evaluates the **Natural Uncertainty Distribution** across all 1,721 edges without query iterations. General mean $= 0.4450$, Wheelchair mean $= 0.4497$. | **DISCREPANT / ERRONEOUS DESCRIPTION** | Retract the "active query convergence" claim in report text. Accurately describe E1 as *Natural Accessibility Uncertainty Distribution across Profiles*. |
| **C2** | **E8: Real-Time Step Latency**<br>*"0.003 ms real-time step latency"* | Phase 6 Executive Summary Table | In `results/pcvc/e8/summary/e8_summary.json`: Priority ranking (Stage 6) takes $0.0001\text{ s}$ ($0.1\text{ ms}$). Complete end-to-end pipeline (Stage 8) takes **$5.890\text{ seconds}$** for 40 candidates ($\sim 147\text{ ms}$ per candidate). | **MISLEADING LATENCY QUOTE** | Disclose that ranking alone is $0.1\text{ ms}$, but online counterfactual evaluation of 40 candidates takes **$5.89\text{ s}$** on the 1,551-node campus graph. |
| **C3** | **E9: Network Scalability**<br>*"Empirical scaling verified up to 5,000 nodes ($O(V \log V)$)"* | Phase 6 Executive Summary Table | In [run_e9_scalability.py](file:///d:/dynamic_pedestrian_rerouting/scripts/experiments/run_e9_scalability.py), scalability was evaluated by varying **candidate limit $N \in [5, 200]$** on the 1,551-node graph. No 5,000-node graph was tested. | **FACTUAL ERROR** | Retract the "5,000 nodes" claim. State accurately: *Candidate budget scalability benchmarked up to $N=200$ candidates on the 1,551-node campus network*. |
| **C4** | **Pathway Width Values**<br>*"Variable physical pathway widths and width-constrained filtering"* | Dataset description & narrative | In `vit_vellore_academic_pedestrian_network.pkl`, `width_m == 2.0` for **1,721 out of 1,721 edges (100.0%)**. Constant synthetic default. | **DATASET LIMITATION** | Explicitly state in IEEE Access paper limitations that dataset lacks surveyed width variance and uses a baseline constant default of $2.0\text{ m}$. |
| **C5** | **Elderly/Pregnant Stairs Constraints**<br>*"Stairs prohibited for elderly and pregnant profiles"* | Narrative in earlier audit | In [src/darr/config.py#L61,L80](file:///d:/dynamic_pedestrian_rerouting/src/darr/config.py#L61): `stairs_allowed: True` for both elderly (penalty 5.0) and pregnant (penalty 3.5). In [src/pada_r/profiles.py#L125-L135](file:///d:/dynamic_pedestrian_rerouting/src/pada_r/profiles.py#L125): stairs produce a high effort/safety penalty, but are **not hard prohibited**. Only wheelchair prohibits stairs. | **INCORRECT CONSTRAINT DESCRIPTION** | Correct all manuscript text to state that elderly and pregnant profiles penalize stairs heavily, whereas wheelchair strictly prohibits stairs. |
| **C6** | **Wheelchair Slope and Width Constraints**<br>*"Wheelchair slope limit 5.0%, width limit 1.2m"* | Narrative in earlier audit | In [src/darr/config.py#L101-102](file:///d:/dynamic_pedestrian_rerouting/src/darr/config.py#L101): `max_slope_percent: 6.0` (not 5.0%) and `min_width_m: 0.9` (not 1.2m). In the graph, 1,709 edges have slope $2.0\%$, 5 edges have $12.0\%$, and 7 edges are stairs. | **NUMERICAL MISMATCH** | Align all text with production configuration: $6.0\%$ maximum slope and $0.9\text{ m}$ minimum width. |
| **C7** | **Confirmed Ramps**<br>*"Accessible ramps identified across campus network"* | Narrative text | In `vit_vellore_academic_pedestrian_network.pkl`, `ramp == False` for **1,721 out of 1,721 edges (100.0%)**. Zero confirmed ramps exist in OpenStreetMap metadata for this campus. | **DATASET ATTRIBUTE DEFICIT** | Disclose in dataset audit that 0 ramps are recorded in OpenStreetMap tags, requiring wheelchair access to rely entirely on ground-level pathways. |
| **C8** | **E5 vs E6 Candidate Counts**<br>*"214 candidate evaluations in E5 vs 114 trajectories in E6"* | Phase 6 Execution Report | In [run_e5_safe_return.py#L31](file:///d:/dynamic_pedestrian_rerouting/scripts/experiments/run_e5_safe_return.py#L31), `CANDIDATE_LIMIT_PER_PROFILE = 100` ($100+7+7+100 = 214$). In [run_e6_probe_correctness.py#L30](file:///d:/dynamic_pedestrian_rerouting/scripts/experiments/run_e6_probe_correctness.py#L30), `EVALUATION_CANDIDATE_LIMIT = 50` ($50+7+7+50 = 114$). | **INTENDED SCOPING DIFFERENCE** | Retain data; document that E6 used $N=50$ for trajectory generation and loop auditing runtime efficiency. |
| **C9** | **Metric Redundancy**<br>*"Distinct evaluation of AOC, ARL, and MAL"* | PCVC Controller formulation | In [src/pcvc/counterfactual.py#L80-L84](file:///d:/dynamic_pedestrian_rerouting/src/pcvc/counterfactual.py#L80): `calculate_arl` is called without `candidate_paths`. Hence, $\text{ARL} \equiv \text{AOC}$, so $\Delta\text{AOC} \equiv \Delta\text{ARL} \equiv \text{MAL}$ for every evaluated edge. | **ALGORITHMIC REDUNDANCY** | Acknowledge in paper methodology that counterfactual endpoint evaluation collapses $\Delta\text{AOC}$, $\Delta\text{ARL}$, and $\text{MAL}$ into identical values. |
| **C10** | **Unused Controller Weights**<br>*"Controller weights $w_{\text{cost}} = 0.03, w_{\text{risk}} = 0.02$"* | [src/pcvc/controller.py#L21-22](file:///d:/dynamic_pedestrian_rerouting/src/pcvc/controller.py#L21) | Weights $w_{\text{cost}}$ and $w_{\text{risk}}$ are declared in `DEFAULT_PCVC_WEIGHTS` but never applied in scoring loop. | **CODE ARTIFACT** | Clarify in paper that verification priority is driven by uncertainty, resilience degradation, and CAD ($w_u=0.25, w_{\Delta\text{arl}}=0.25, w_{\text{cad}}=0.15$). |

---

## Reconciliation Action Plan for Manuscript Writing

1. **Retract Overstatements:** Remove all references to "active uncertainty convergence from $0.783 \to 0.065$", "0.003 ms end-to-end latency", and "5,000-node graph scaling". Replace them with exact measured figures ($5.89\text{ s}$ pipeline runtime, candidate budget scaling on 1,551 nodes).
2. **Transparent Dataset Audit:** Clearly publish the real-world state of the VIT Vellore OpenStreetMap network:
   - 1,551 nodes, 1,721 edges.
   - 1,397 edges ($81.2\%$) have unknown wheelchair accessibility.
   - Smoothness and tactile paving are 100% missing (`None`).
   - Width is uniformly defaulted to $2.0\text{ m}$.
   - 0 ramps recorded; 7 stair segments recorded.
   - 5 edges have slopes exceeding wheelchair thresholds ($12.0\%$).
3. **Harmonize Profile Tables:** Use the verified production values:
   - General: $1.4\text{ m/s}$, slope `None`, width $0.0\text{ m}$, stairs permitted.
   - Elderly: $0.9\text{ m/s}$, slope $8.0\%$, width $0.6\text{ m}$, stairs permitted with penalty.
   - Pregnant: $1.0\text{ m/s}$, slope $8.0\%$, width $0.6\text{ m}$, stairs permitted with penalty.
   - Wheelchair: $0.8\text{ m/s}$, slope $6.0\%$, width $0.9\text{ m}$, stairs strictly prohibited.

# Circadian Gene Selection Report

## Ranking metric

Genes were ranked by ascending `p_value` from the rhythmicity analysis. In the case of ties in `p_value`, genes would be further ranked by descending `amplitude` (larger amplitude preferred).

## Top circadian gene

- **Gene:** `GENE15`
- **F_stat:** 22.273596
- **p_value:** 0.000327172
- **neg_log10_p:** 3.485
- **amplitude:** 2.388
- **phase_peak_time_h:** 12.109 h (within a 24 h period, peak ~12.1 h, trough ~0.1 h)

## Visual pattern summary

For the top gene, expression measurements across the ordered timepoints (0–44 h) show a clear circadian-like oscillation. The expression rises towards a peak around ~12.1 h (and again near 24 h + this phase), then declines to a trough around ~0.1 h, approximately one half-period later. Over the 0–44 h window, this corresponds to roughly one to two visible cycles of a ~24 h rhythm. A 24 h sinusoidal curve, parametrized by the estimated amplitude and phase, overlays the data and tracks the observed oscillation well, supporting strong ~24 h rhythmicity for this gene.


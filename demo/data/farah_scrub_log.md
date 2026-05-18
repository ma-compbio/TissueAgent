# Farah MERFISH scrub log
From the raw UCSC `hoc/all-merfish/` dataset (228635 cells × 238 genes), the following columns were removed from `adata.obs` to prevent the recovery benchmark from being trivially solved by reading the published label.

## Dropped: `Communities`
Original value counts:

- `Outer-LV`: 60810
- `Inner-LV`: 28263
- `Right Atria`: 27613
- `Valve`: 21087
- `Outer-RV`: 19901
- `Left Atria`: 17940
- `Inner-RV`: 16369
- `Subepicardial`: 9106
- `Mus. Valve Leaf.`: 7661
- `VCS`: 6956
- `OFT`: 5135
- `AVN/AV Ring`: 4003
- `IFT/SAN`: 3791

## Dropped: `Zone_Cluster`
Original value counts:

- `8`: 60810
- `2`: 28263
- `3`: 27613
- `1`: 21087
- `6`: 19901
- `9`: 17940
- `0`: 16369
- `11`: 9106
- `5`: 7661
- `10`: 6956
- `7`: 5135
- `4`: 4003
- `12`: 3791

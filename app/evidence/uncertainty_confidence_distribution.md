# Confidence-distribution evidence (tau=0.60)

| Bucket | Count | Min | Median | Max | Count below tau |
|---|---:|---:|---:|---:|---:|
| holdout_split_top1 | 993 | 0.515814 | 1.000000 | 1.000000 | 2 |
| single_symptom_sparse_top1 | 131 | 0.333080 | 0.720671 | 0.999423 | 57 |
| dataset_vignette_top1 | 10 | 0.817507 | 0.994893 | 1.000000 | 0 |
| independent_vignette_top1 | 6 | 0.597846 | 0.940219 | 0.997171 | 1 |

- **Chosen tau:** 0.60
- **Basis:** threshold from app inference config, validated against holdout/sparse/vignette confidence distributions and independent vignette outcomes.

# Statistical analysis

Analysis first excludes runs without a successful integrity record. It pairs conditions by seed, averages normal and swapped physical-side runs within each seed, and reports the number of matched independent seeds. The primary measure is terminal ticket balance. Mean/median paired differences, standard deviation, paired standardized effect, 95% t interval, and seed-level bootstrap interval are reported. A two-sided sign-flip test is exact up to 16 seeds and Monte Carlo above that. Secondary outcomes receive Benjamini-Hochberg q-values.

With one seed, no population-level confidence interval or confirmatory test is claimed. Bootstrap intervals with few seeds are unstable. Check distribution and design assumptions before interpretation; neither p-values nor attractive plots replace the prespecified protocol. Exclusions, incomplete pairs, and technical failures remain visible in run manifests and validation output.

# Reference typed-configuration results

The committed [CSV](reference-quick.csv), [figure](reference-quick.png), and [effective configuration](reference-quick.config.json) record a pinned quick run on 2026-10-26 at 20:47 UTC using CPython 3.13.15 on macOS arm64. DIPL/SNT3 0.9.11, Pydantic 2.14.1, PyYAML 6.0.3, Pint 0.26.2, and Matplotlib 3.11.2 were used. The run covered 10, 100, and 1,000 parameters, with five timed samples and two warmups. Every output matched the common expected structure, and each participant rejected five malformed cases.

Timestamped runs are ignored by Git and pruned to the newest ten. To refresh the reference, run `./setup.sh --benchmark typed-config`, review the software and platform metadata, then deliberately copy the resulting CSV, figure, and effective configuration to the `reference-quick` names.

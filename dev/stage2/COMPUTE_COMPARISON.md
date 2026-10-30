# Where to run stage 2: Colab versus a Google Cloud machine (1 Nov 2026)

Prices below are third-party readings of public price lists on 1 Nov 2026; the Colab unit rate in particular differs between sources and must be read from the runtime pane of a live session ("Resources" shows the units per hour the current runtime consumes). Units in hand: about 430.

## Workload to place

| Part | Estimate | Basis |
|---|---|---|
| Full-release label extraction (all comers, labels of the 20,000 already-labelled stays reused) | about 170 batch-hours of CPU work in total: 21 h with 8 batches in parallel, 11 h with 16, 55 h with 3 | stage-1 timings per 500 stays (MIMIC 8.5 min, eICU 21 min) on 94,000 + 201,000 candidate stays |
| Raw-table scan and hourly features for the all-comers cohort | roughly one day on 12 CPUs, half a day on 32 | scales with CPU count (feature batches run in parallel) |
| GPU arms, seed-tiered (three seeds for arms 1 to 5, one for 6 to 9) | about 250 to 290 A100-hours | the eight-fold scaling of the 10,000-stay runs |

## Cost

| | Colab Pro+ | Google Cloud, on-demand | Google Cloud, spot |
|---|---|---|---|
| A100 40 GB, per hour | 5.4 units (one 2026 reading) to 13 units (older readings); at $0.10 per unit that is $0.54 to $1.30 | $3.67 (a2-highgpu-1g, 12 vCPU, 85 GB) | about $1.35 to $1.85, can be interrupted |
| 270 A100-hours | 1,460 to 3,500 units; after the 430 in hand, 1,030 to 3,070 to buy, about $100 to $310 (Pro+ adds 500 units a month for $50; extra units $10 per 100) | about $990 | about $370 to $500, plus about a tenth for interrupted epochs |
| Label extraction | CPU high-RAM runtime, 3 batches in parallel (about 51 GB RAM), 2 to 3 sessions: a few tens of units | n2-highmem-32 (32 vCPU, 256 GB), 16 batches in parallel, about 12 h: about $25 (check the live rate, about $1.9 per hour) | about a third of that |
| Storage | the Drive plan already in use | 300 to 500 GB balanced persistent disk, $30 to $50 a month while the project lives | same |
| L4 instead of A100 | 1.7 units per hour but 2 to 3 times slower per epoch: no saving in units, three times the calendar time | g2-standard-8 $0.85 per hour, 600 to 800 hours: about $550 to $700 and a month of wall time | |

Reading: if the live Colab rate is near 5 to 6 units per hour, Colab is the cheapest option by a wide margin and about equal to spot Google Cloud without the set-up. If it is near 13, a spot A100 on Google Cloud is cheaper for the GPU arms, but only once the quota exists and the environment has been rebuilt there.

## Speed and calendar time

| | Colab | Google Cloud |
|---|---|---|
| Per-epoch compute | same GPU, same speed | same |
| Reading the feature shards | from Drive through the mount (slower; the local-disk copy of the raw data already works around this for extraction) | local SSD |
| CPU-parallel stages (labels, features) | 12 vCPU on the A100 runtime, about 51 GB RAM on the CPU high-RAM runtime: 3 label batches at a time | 32 vCPU and 256 GB: 16 label batches at a time, features about 2.5 times faster |
| Session limit | 24 hours; a manual Run-all restart each day; the code resumes from the last epoch and the last completed batch, so a restart costs at most one epoch plus the start-up | none on-demand; spot machines are interrupted at any time, which the same checkpoints absorb |
| Calendar estimate, all arms | about 12 to 14 days of GPU time plus 2 to 3 days of data build, with roughly one restart a day | about 11 days of GPU time plus about 1 day of data build, unattended |
| GPU availability | not guaranteed; when an A100 is unavailable the runtime falls back to an L4 or T4 and the day's work slows | guaranteed once the quota is granted (on-demand); spot capacity can be short in a region |

## Other items

| Item | Colab | Google Cloud |
|---|---|---|
| Set-up effort | none; the notebooks run as they are | one to two days: a GPU image with drivers, the R and YAIB environment rebuilt from the project's set-up script on a plain Ubuntu machine (never tested there), the raw data copied in, Jupyter or papermill in tmux |
| GPU quota | not applicable | new or personal accounts start at 0 GPUs; A100 quota requests are often refused or routed to sales, L4 is granted more readily; the $300 trial credit usually does not come with GPU quota |
| Data governance | data stay in the credentialed owner's Drive, as now | the project must sit in the credentialed owner's own Google account, billed to it; PhysioNet links the Google account to the PhysioNet profile and then serves MIMIC-IV and eICU directly inside Google Cloud (BigQuery and Cloud Storage), so the raw files can be pulled within the cloud; the partner's account still holds no data |
| Monitoring | Pro+ background execution keeps the notebook running with the browser closed, within the 24 h limit | ssh and logs; email alerts can be scripted |
| Failure modes | daily restarts forgotten; GPU downgraded; Drive quota | preemption (handled); quota refusal; forgetting to stop the machine (billing continues) |
| Reproducibility | identical code; runtime versions recorded in `run_protocol.json` | identical code; the environment is pinned by the same set-up script |

## Recommendation

1. Start on Colab now with the units in hand: the data build and arm 1 (the project model, three seeds). This also yields the two numbers the decision needs: the live unit rate and the measured epoch time on the full cohort.
2. Decide after arm 1. If the rate is about 5 to 6 units per hour, finish everything on Colab (total about $150 to $250 beyond the subscription). If it is about 13, and a Google Cloud account with A100 quota is available or can be obtained within a week, move arms 2 to 5 to a spot A100 and keep the one-seed arms on Colab; if the quota is not available, buying units (about $300) costs less than the engineering time of migrating.
3. Whatever the choice, the label extraction benefits most from a many-core machine; a one-off n2-highmem-32 for a day (about $25) is the one Google Cloud step worth taking even if training stays on Colab, provided the environment rebuild is tested first on the fixture.

Nothing runs on real data before the freeze (signed tag, hash deposit).

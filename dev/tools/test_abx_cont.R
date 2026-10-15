# Test of the V11_EMPTY_ABX_FIX for YAIB abx_cont() (see HANDOVER_FOR_NEXT_CLAUDE.md, error #7).
# Setup (CRAN is blocked in the cloud session; build from GitHub mirrors):
#   git clone https://github.com/eth-mds/ricu /home/user/eth-mds/ricu           # ricu 0.6.0 sources
#   git clone https://github.com/rvandewater/YAIB-cohorts && git -C YAIB-cohorts checkout 74ac699f
#   cp YAIB-cohorts/ricu-extensions/callbacks/callback-sepsis.R orig.R
#   python3 -c "from pathlib import Path; COHORT_REPO=Path('.'); exec(open('dev/work/cells/fix_4c_abx_cont.py').read().split('if DATA_SOURCE')[0]); open('patched.R','w').write(open('orig.R').read().replace(_OLD,_NEW))"
#   for p in rlang glue cli lifecycle vctrs data.table assertthat; do git clone --depth 1 https://github.com/cran/$p; R CMD INSTALL -l ../rlib $p; done
# Run from the folder holding orig.R/patched.R:  Rscript test_abx_cont.R
.libPaths(c("../rlib", .libPaths()))
suppressPackageStartupMessages({library(rlang); library(vctrs); library(cli); library(data.table); library(assertthat)})
fails <- character()
for (f in list.files("/home/user/eth-mds/ricu/R", full.names = TRUE)) { if (basename(f) == "tbl-base.R") { txt <- gsub("utils::packageVersion\\(\"(prt|pillar)\"\\)", "package_version(\"0.2.0\")", readLines(f)); txt <- gsub("prt::format_dt|prt::trunc_dt", "print", txt); eval(parse(text = txt), envir = globalenv()); next }
  r <- try(sys.source(f, envir = globalenv()), silent = TRUE)
  if (inherits(r, "try-error")) fails <- c(fails, basename(f))
}
cat("ricu files that failed to source:", fails, "\n")
load_cb <- function(path) {
  txt <- gsub("ricu:::?", "", readLines(path))
  e <- new.env(parent = globalenv()); eval(parse(text = txt), envir = e); e
}
O <- load_cb("orig.R"); P <- load_cb("patched.R")

mk_abx <- function(ids, times, durs) {
  as_win_tbl(data.table(patientunitstayid = as.integer(ids),
                        infusionoffset = as.difftime(times, units = "hours"),
                        abx_duration = TRUE,
                        dur_var = as.difftime(durs, units = "hours")),
             id_vars = "patientunitstayid", index_var = "infusionoffset",
             dur_var = "dur_var", interval = hours(1L), by_ref = TRUE)
}
mk_death <- function(ids, times) {
  as_ts_tbl(data.table(patientunitstayid = as.integer(ids),
                       index_var = as.difftime(times, units = "hours"),
                       death_icu = TRUE),
            id_vars = "patientunitstayid", index_var = "index_var",
            interval = hours(1L), by_ref = TRUE)
}
run <- function(env, abx, death) env$abx_cont(abx_duration = copy(abx), death_icu = copy(death), interval = hours(1L))

cat("\n--- Case A: batch with no antibiotic records at all ---\n")
abxA <- mk_abx(integer(), numeric(), numeric()); deathA <- mk_death(c(1, 2), c(10, 20))
a1 <- try(run(O, abxA, deathA), silent = TRUE)
cat("original:", if (inherits(a1, "try-error")) conditionMessage(attr(a1, "condition")) else "no error", "\n")
a2 <- run(P, abxA, deathA)
cat("patched: rows =", nrow(a2), "| cols =", colnames(a2), "| class =", class(a2)[1],
    "| index =", index_var(a2), "| interval =", format(interval(a2)), "\n")

cat("\n--- Case A2: antibiotics only AFTER death (filtered to empty) ---\n")
abxA2 <- mk_abx(c(1, 2), c(15, 30), c(2, 2))
b1 <- try(run(O, abxA2, deathA), silent = TRUE)
cat("original:", if (inherits(b1, "try-error")) conditionMessage(attr(b1, "condition")) else "no error", "\n")
b2 <- run(P, abxA2, deathA); cat("patched: rows =", nrow(b2), "| cols =", colnames(b2), "\n")

cat("\n--- Case B: normal batch (must be identical) ---\n")
set.seed(1)
abxB <- mk_abx(c(1,1,1,2,2,3,4,4,4,4), c(0,10,30,5,100,7,0,20,40,90), c(12,12,4,1,24,48,6,6,6,6))
deathB <- mk_death(c(3), c(30))
o <- run(O, abxB, deathB); p <- run(P, abxB, deathB)
cat("identical:", identical(o, p), "| rows:", nrow(o), "| cols:", colnames(o), "\n")
print(as.data.frame(o))

cat("\n--- Downstream: susp_inf_alt + sep3_alt with the empty abx_cont (si_mode='abx') ---\n")
samp <- as_ts_tbl(data.table(patientunitstayid = 1:2, chartoffset = as.difftime(c(3, 4), units = "hours"), samp = TRUE),
                  id_vars = "patientunitstayid", index_var = "chartoffset", interval = hours(1L), by_ref = TRUE)
si <- P$susp_inf_alt(abx_cont = copy(a2), samp = samp, si_mode = "abx", interval = hours(1L))
cat("susp_inf_alt rows =", nrow(si), "| cols =", colnames(si), "\n")
sofa <- as_ts_tbl(data.table(patientunitstayid = rep(1:2, each = 5), chartoffset = as.difftime(rep(0:4, 2), units = "hours"),
                             sofa = c(0,1,3,4,5, 0,0,1,1,1)),
                  id_vars = "patientunitstayid", index_var = "chartoffset", interval = hours(1L), by_ref = TRUE)
s3 <- P$sep3_alt(sofa = sofa, susp_inf_alt = si, interval = hours(1L))
cat("sep3_alt rows =", nrow(s3), "| cols =", colnames(s3), "\n")

cat("\n--- Control: same downstream with a NON-empty abx_cont gives a sepsis label ---\n")
pc <- run(P, mk_abx(c(1,1), c(2,5), c(72,72)), mk_death(9, 99)); si2 <- P$susp_inf_alt(abx_cont = copy(pc), samp = samp, si_mode = "abx", interval = hours(1L))
s32 <- P$sep3_alt(sofa = sofa, susp_inf_alt = si2, interval = hours(1L))
print(as.data.frame(s32))

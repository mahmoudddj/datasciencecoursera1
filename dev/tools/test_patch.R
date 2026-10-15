# ricu (0969a52) definitions, verbatim semantics
obeys_interval <- function(x, interval, na_rm = TRUE, tolerance = as.difftime(1e-3, units="secs")) {
  all(as.double(x) %% as.double(interval, units = units(x)) < as.double(tolerance, units = units(x)), na.rm = na_rm)
}
round_to <- function(x, to = 1) if (isTRUE(all.equal(to, 1))) trunc(x) else trunc(x / to) * to
re_time <- function(x, interval) round_to(`units<-`(x, units(interval)), as.double(interval))
.v9_original_interval_difftime <- function(x) {
  dif <- diff(x); res <- min(dif[dif > 0], na.rm = TRUE)
  if (!obeys_interval(x, res)) stop("x is not compatible with an interval of ", format(res))
  res
}
.v9_gcd2 <- function(a, b) { a <- abs(as.numeric(a)); b <- abs(as.numeric(b)); while (b > 0) { z <- b; b <- a %% b; a <- z }; a }
source("patched_block.R")
x <- as.difftime(c(2, 5, 9, 12), units = "hours")          # sparse grid: min diff 3h does not divide 7h-2h
r1 <- tryCatch(.v9_original_interval_difftime(x), error = function(e) conditionMessage(e))
cat("ricu original      :", r1, "\n")
r2 <- .v9_interval_difftime(x)
cat("patched fallback   :", format(r2), "| units:", units(r2), "\n")
stopifnot(identical(units(r2), "hours"), as.numeric(r2) == 1)
dense <- as.difftime(c(0,1,2,3), units="hours")
cat("dense (no fallback):", format(.v9_interval_difftime(dense)), "\n")
cat("re_time keeps hours:", units(re_time(dense, r2)), "\n")
# old behaviour for contrast
old <- as.difftime(3600, units="secs")
cat("old fallback re_time units:", units(re_time(dense, old)), "(mismatch with hour-based tables)\n")

.v9_interval_difftime <- function(x) {

            tryCatch(

                .v9_original_interval_difftime(x),

                error = function(e) {

                    msg <- conditionMessage(e)

                    if (!grepl(
                        "not compatible with an interval",
                        msg,
                        fixed = TRUE
                    )) {
                        stop(e)
                    }

                    sec <- as.numeric(x, units = "secs")
                    sec <- sec[is.finite(sec)]

                    if (length(sec) < 2L) {
                        stop(e)
                    }

                    sec_int <- round(sec)

                    # Refuse fallback if timestamps are not exact to whole seconds.
                    if (any(abs(sec - sec_int) > 1e-6)) {
                        stop(e)
                    }

                    vals <- abs(sec_int[sec_int != 0])

                    if (!length(vals)) {
                        stop(e)
                    }

                    grid_sec <- Reduce(.v9_gcd2, vals)

                    if (!is.finite(grid_sec) || grid_sec <= 0) {
                        stop(e)
                    }

                    res <- as.difftime(grid_sec, units = "secs")
                    # Return the interval in the SAME units as the time column, exactly
                    # like ricu's interval.difftime(); a seconds-valued interval makes
                    # re_time()/sep3 windows convert some tables to secs and others not.
                    units(res) <- units(x)

                    # Preserve ricu's own compatibility criterion.
                    if (!isTRUE(obeys_interval(x, res))) {
                        stop(e)
                    }

                    message(
                        "V9_INTERVAL_NAMESPACE_FALLBACK: ",
                        format(res),
                        " instead of sparse inferred interval"
                    )

                    res
                }
            )
        }

        

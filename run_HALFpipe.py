#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import shutil
import re

# Config: change path to FreeSurfer license here:
fs_license_source = "/data_wgs04/ag-sensomotorik/mritb-master/license.txt"

def ensure_freesurfer_license(workdir: str, license_source: str, filename: str = "license.txt") -> str:
    # Ensure FreeSurfer license file exists in workdir; if missing, copy from license_source.
    dest = os.path.join(workdir, filename)

    # If already present: do nothing
    if os.path.isfile(dest):
        return dest

    # Otherwise copy from source; change path in main()
    if not os.path.isfile(license_source):
        raise RuntimeError(f"FreeSurfer license source file not found: {license_source}")

    try:
        shutil.copy2(license_source, dest)  # preserves timestamps/metadata
    except PermissionError as e:
        raise RuntimeError(f"No permission to copy FreeSurfer license to {dest}: {e}")
    except OSError as e:
        raise RuntimeError(f"Failed to copy FreeSurfer license to {dest}: {e}")

    return dest


def add_common_flags(cmd, args):
    if args.verbose:
        cmd.append("--verbose")
    if args.debug:
        cmd.append("--debug")
    return cmd


def add_halfpipe_advanced_flags(cmd, args):
    if args.only_step:
        cmd.append(f"--only-{args.only_step}")
        # only-run requires workdir
        if args.only_step in ("run", "workflow"):
            cmd += ["--workdir", args.workdir]
    # TODO: implement --uuid if --only-run is used often

    if args.skip_step:
        cmd.append(f"--skip-{args.skip_step}")
        # skipping spec-ui also requires workdir
        if args.skip_step == "spec-ui":
            cmd += ["--workdir", args.workdir]

    if not os.path.isdir(args.workdir):
        raise RuntimeError(
            f"--workdir {args.workdir} does not exist but is required for {args.only_step or args.skip_step}"
        )

    return cmd

_RANGE_RE = re.compile(r"^(?P<a>sub-\d+|\d+)\s*-\s*(?P<b>sub-\d+|\d+)$")


def _normalize_one_subject_token(tok: str) -> str:
    tok = tok.strip()
    if not tok:
        raise ValueError("Empty subject token")

    # If token already starts with sub-, strip prefix for processing
    if tok.startswith("sub-"):
        core = tok[4:]
    else:
        core = tok

    # If purely numeric -> pad to 2 digits
    if core.isdigit():
        return f"sub-{core.zfill(2)}"

    # Otherwise: allow arbitrary labels (BIDS allows non-numeric subject labels)
    # Ensure it has 'sub-' prefix
    if core.isalnum():
        return f"sub-{core}"

    raise ValueError(
        f"Invalid subject identifier '{tok}'. "
        "Expected formats are for example: "
        "'01', '1', 'sub-01', '01-03', or 'sub-01-sub-03'."
    )


def expand_subject_tokens(tokens):
    """
    Expand a list of tokens that may include ranges like '01-09' or '1-9' or 'sub-01-sub-09'
    into a list of normalized subject labels ('sub-01', ...).
    """
    expanded = []
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue

        # Range like 01-09 or sub-01-sub-09
        m = _RANGE_RE.match(tok.replace("sub-", "sub-"))  # no-op, just clarity
        if m:
            a_raw = m.group("a")
            b_raw = m.group("b")

            # normalize endpoints but keep numeric value
            a_norm = _normalize_one_subject_token(a_raw)
            b_norm = _normalize_one_subject_token(b_raw)

            a_num = int(a_norm.split("-")[1])
            b_num = int(b_norm.split("-")[1])

            step = 1 if b_num >= a_num else -1
            for n in range(a_num, b_num + step, step):
                expanded.append(f"sub-{str(n).zfill(2)}")
            continue

        # Not a range -> normal token
        expanded.append(_normalize_one_subject_token(tok))

    # de-duplicate while preserving order
    seen = set()
    out = []
    for s in expanded:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def add_subject_flags(cmd, args):
    if args.subject_include:
        try:
            include_subjects = expand_subject_tokens(args.subject_include)
        except ValueError as e:
            raise RuntimeError(f"Error while parsing --subject-include:\n  {e}")
        for sub in include_subjects:
            cmd += ["--subject-include", sub]

    if args.subject_exclude:
        try:
            exclude_subjects = expand_subject_tokens(args.subject_exclude)
        except ValueError as e:
            raise RuntimeError(f"Error while parsing --subject-exclude:\n  {e}")
        for sub in exclude_subjects:
            cmd += ["--subject-exclude", sub]

    return cmd


def build_command(args):
    """Return the full singularity command list based on the selected mode."""
    halfpipe_sif = os.getenv("HALFpipe_sif")
    if not halfpipe_sif:
        raise RuntimeError("Environment variable HALFpipe_sif is not set.")
    if not os.path.exists(halfpipe_sif):
        raise RuntimeError(f"HALFpipe_sif does not exist: {halfpipe_sif}")

    bidsdir_arg = f"{args.bidsdir}:{args.bidsdir}"
    workdir_arg = f"{args.workdir}:{args.workdir}"

    binds = [bidsdir_arg, workdir_arg]

    if args.seeddir:
        if not os.path.isdir(args.seeddir):
            raise RuntimeError(f"Seed-directory does not exist or is not a directory: {args.seeddir}")
        seeddir_arg = f"{args.seeddir}:{args.seeddir}"
        binds.append(seeddir_arg)

    bind_arg = ",".join(binds)

    # Base command parts; exec for new tui; run for old ui
    base_exec = ["singularity", "exec", "--bind", bind_arg, halfpipe_sif, "halfpipe", "--tui"]
    base_run  = ["singularity", "run",  "--bind", bind_arg, halfpipe_sif]

    # Choose mode
    if args.mode == "ui-old":
        # Old UI (singularity run ...)
        cmd = add_common_flags(base_run[:], args)
        return cmd

    if args.mode == "tui":
        # New terminal UI (no special flags)
        cmd = add_common_flags(base_exec[:], args)
        cmd = add_halfpipe_advanced_flags(cmd, args)
        cmd = add_subject_flags(cmd, args)
        cmd += ["--nipype-n-procs", str(args.n_procs)]
        return cmd

    if args.mode == "model":
        # Run only model chunk
        cmd = add_common_flags(base_exec[:], args)
        cmd = add_halfpipe_advanced_flags(cmd, args)
        cmd = add_subject_flags(cmd, args)
        cmd += ["--nipype-n-procs", str(args.n_procs)]
        cmd.append("--only-model-chunk")
        return cmd

    if args.mode == "group-level":
        # Use group-level command
        if not args.input_directory:
            raise RuntimeError("group-level requires --input-directory")
        cmd = add_common_flags(base_exec[:], args)
        cmd = add_halfpipe_advanced_flags(cmd, args)
        cmd = add_subject_flags(cmd, args)
        cmd += ["--nipype-n-procs", str(args.n_procs)]
        cmd += ["group-level", "--input-directory", args.input_directory]
        return cmd

    raise RuntimeError(f"Unknown mode: {args.mode}")


def main():
    parser = argparse.ArgumentParser(
        description="Run HALFpipe via singularity with different modes."
    )
    parser.add_argument("bidsdir", type=str, help="Path to BIDS directory.")

    parser.add_argument("workdir", type=str, help="Path to working and output directory.")

    # Subcommand-like choice:
    parser.add_argument(
        "mode",
        nargs="?",
        default="tui",
        choices=["ui-old", "tui", "model", "group-level"],
        help="Which HALFpipe start mode to run (default: tui).",
    )

    # Global toggles
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    parser.add_argument("--debug", action="store_true", help="Enable debug output.")

    # Only needed for some modes
    parser.add_argument(
        "--input-directory",
        type=str,
        help="Used for group-level mode.",
    )

    # Some optional flags:
    # Flag and directory need to be set to also bind this directory in singularity
    parser.add_argument(
        "--seeddir",
        type=str,
        help="Path to directory containing binary seed masks (optional).",
    )

    # Advanced HALFpipe use:
    # Option to either run only or skip a specific step
    step_group = parser.add_mutually_exclusive_group(required=False)
    step_group.add_argument(
        "--only-step",
        choices=["spec-ui", "workflow", "run"],
        help="Run only a single HALFpipe step (advanced).",
    )
    step_group.add_argument(
        "--skip-step",
        choices=["spec-ui", "workflow", "run"],
        help="Skip a single HALFpipe step (advanced).",
    )

    # Option to select specific subjects
    parser.add_argument(
        "--subject-include",
        dest="subject_include",
        nargs="+",
        help="Include only these subjects. Examples: 01 02 03 | sub-01 sub-02 | 1 2 3 | 01-03",
    )
    parser.add_argument(
        "--subject-exclude",
        dest="subject_exclude",
        nargs="+",
        help="Exclude these subjects. Examples: 20 | sub-20 | 1-3 | 01-03",
    )

    parser.add_argument(
        "--n-procs",
        type=int,
        default=None,
        help="Number of processes/cores for Nipype (maps to HALFpipe --nipype-n-procs). "
             "If not set, a capped default is used.",
    )
    default_max_procs = 100

    # Run-command will be printed in bash but not executed
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the constructed command and exit without running anything.",
    )

    args = parser.parse_args()

    license_path = ensure_freesurfer_license(args.workdir, fs_license_source)
    print(f"FreeSurfer license present: {license_path}")

    available = os.cpu_count() or 1

    if args.n_procs is None:
        args.n_procs = min(available, default_max_procs)
        nprocs_note = (
            f"No --n-procs provided → using min(available={available}, "
            f"default_max_procs={default_max_procs}) = {args.n_procs}"
        )
    else:
        if args.n_procs < 1:
            raise RuntimeError("--n-procs must be >= 1")
        if args.n_procs > available:
            print(
                f"Warning: --n-procs={args.n_procs} is greater than available cores ({available}).",
                file=sys.stderr,
            )
        nprocs_note = f"--n-procs explicitly set to {args.n_procs}"

    print(f"Directory containing BIDS data: {args.bidsdir}")
    print(f"Working directory: {args.workdir}")
    print(f"Mode: {args.mode}")
    print(nprocs_note)

    cmd = build_command(args)
    print("Running command:\n ", " ".join(cmd))
    if args.dry_run:
        print("Dry-run enabled: command was NOT executed.")
        return 0
    subprocess.run(cmd, check=True)

    print("... done. Have a nice day!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

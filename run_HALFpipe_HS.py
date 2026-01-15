#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import shutil

def add_common_flags(cmd, args):
    if args.verbose:
        cmd.append("--verbose")
    if args.debug:
        cmd.append("--debug")
    return cmd

def add_halfpipe_advanced_flags(cmd, args):
    if args.keep is not None:
        cmd += ["--keep", args.keep]
    if args.only_step:
        cmd.append(f"--only-{args.only_step}")
    if args.skip_step:
        cmd.append(f"--skip-{args.skip_step}")
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
    base_exec = ["singularity", "exec", "--bind", bind_arg, halfpipe_sif, "halfpipe", "--tui"] # "--nipype-n-procs", "1", "--nipype-run-plugin", "Linear"
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
        return cmd

    if args.mode == "model":
        # Run only model chunk
        cmd = add_common_flags(base_exec[:], args)
        cmd = add_halfpipe_advanced_flags(cmd, args)
        cmd.append("--only-model-chunk")
        return cmd

    if args.mode == "group-level":
        # Use group-level command
        if not args.input_directory:
            raise RuntimeError("group-level requires --input-directory")
        cmd = add_common_flags(base_exec[:], args)
        cmd = add_halfpipe_advanced_flags(cmd, args)
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

    # HALFpipe default: keep some intermediate files; keep all is useful for debugging
    parser.add_argument(
        "--keep",
        choices=["all", "some", "none"],
        default=None,
        help="Choose which intermediate files to keep (default: some).",
    )

    # Advanced HALFpipe use: option to either run only or skip a specific step
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

    # Run-command will be printed in bash but not executed
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the constructed command and exit without running anything.",
    )

    args = parser.parse_args()
    print(f"Directory containing BIDS data: {args.bidsdir}")
    print(f"Working directory: {args.workdir}")
    print(f"Mode: {args.mode}")

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

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

def build_command(args):
    """Return the full singularity command list based on the selected mode."""
    halfpipe_sif = os.getenv("HALFpipe_sif")
    if not halfpipe_sif:
        raise RuntimeError("Environment variable HALFpipe_sif is not set.")
    if not os.path.exists(halfpipe_sif):
        raise RuntimeError(f"HALFpipe_sif does not exist: {halfpipe_sif}")

    bind_arg = f"{args.bidsdir}:/data"

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
        return cmd

    if args.mode == "model":
        # Run only model chunk
        cmd = add_common_flags(base_exec[:], args)
        cmd.append("--only-model-chunk")
        return cmd

    if args.mode == "group-level":
        # Use group-level command
        if not args.input_directory:
            raise RuntimeError("group-level requires --input-directory")
        cmd = add_common_flags(base_exec[:], args)
        cmd += ["group-level", "--input-directory", args.input_directory]
        return cmd

    raise RuntimeError(f"Unknown mode: {args.mode}")


def main():
    parser = argparse.ArgumentParser(
        description="Run HALFpipe via singularity with different modes."
    )
    parser.add_argument("bidsdir", type=str, help="Path to BIDS directory.")

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

    args = parser.parse_args()
    print(f"Directory containing BIDS data: {args.bidsdir}")
    print(f"Mode: {args.mode}")

    cmd = build_command(args)
    print("Running command:\n ", " ".join(cmd))
    subprocess.run(cmd, check=True)

    print("... done. Have a nice day!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

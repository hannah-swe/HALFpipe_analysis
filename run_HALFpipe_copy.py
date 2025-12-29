#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import shutil

def build_command(args):
    """Return the full singularity command list based on the selected mode."""
    halfpipe_sif = os.getenv("HALFpipe_sif")
    if not halfpipe_sif:
        raise RuntimeError("Environment variable HALFpipe_sif is not set.")

    bind_arg = f"{args.bidsdir}:/data"

    # Base command parts (common)
    base_exec = ["singularity", "exec", "--bind", bind_arg, halfpipe_sif, "halfpipe"]
    base_run  = ["singularity", "run",  "--bind", bind_arg, halfpipe_sif]

    # Choose mode
    if args.mode == "ui-old":
        # Old UI (singularity run ...)
        cmd = base_run[:]
        if args.verbose:
            cmd.append("--verbose")
        return cmd

    if args.mode == "preproc":
        # New terminal UI (no special flags)
        cmd = base_exec[:]
        if args.tui:
            cmd.append("--tui")
        if args.verbose:
            cmd.append("--verbose")
        if args.debug:
            cmd.append("--debug")
        return cmd

    if args.mode == "feature":
        # only feature chunk
        cmd = base_exec[:]

    if args.mode == "model":
        # Your example: only model chunk
        cmd = base_exec + ["--tui", "--only-model-chunk"]
        if args.tui:
            cmd.append("--tui")
        if args.verbose:
            cmd.append("--verbose")
        if args.debug:
            cmd.append("--debug")
        return cmd

    if args.mode == "group-level":
        # Example based on your commented block
        if not args.input_directory:
            raise RuntimeError("group-level requires --input-directory")
        cmd = base_exec + [
            "--tui",
            "group-level",
            "--input-directory",
            args.input_directory,
        ]
        if args.verbose:
            cmd.append("--verbose")
        if args.debug:
            cmd.append("--debug")
        return cmd

    raise RuntimeError(f"Unknown mode: {args.mode}")


def copy_dataset_description(bidsdir: str):
    destdir = os.path.join(bidsdir, "derivatives", "halfpipe")
    mrti = os.getenv("MRITB")
    if not mrti:
        print("Warning: MRITB is not set, cannot copy dataset_description.json", file=sys.stderr)
        return

    srcfile = os.path.join(mrti, "HALFpipe_utils", "dataset_description.json")
    if os.path.exists(destdir):
        shutil.copy(srcfile, destdir)
        print(f"Copied {srcfile} to {destdir}.")
    else:
        print(f"Directory {destdir} does not exist.")


def main():
    parser = argparse.ArgumentParser(
        description="Run HALFpipe via singularity with different modes."
    )
    parser.add_argument("bidsdir", type=str, help="Path to BIDS directory.")

    # Subcommand-like choice:
    parser.add_argument(
        "mode",
        choices=["model", "tui", "ui-old", "group-level"],
        help="Which HALFpipe start mode to run.",
    )

    # Global toggles
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    parser.add_argument("--debug", action="store_true", help="Enable debug output.")

    # Only needed for some modes
    parser.add_argument(
        "--input-directory",
        type=str,
        help="Used for group-level mode (path inside or outside container, depending on your setup).",
    )

    args = parser.parse_args()
    print(f"Directory containing BIDS data: {args.bidsdir}")
    print(f"Mode: {args.mode}")

    cmd = build_command(args)
    print("Running command:\n ", " ".join(cmd))
    subprocess.run(cmd, check=True)

    copy_dataset_description(args.bidsdir)

    print("... done. Have a nice day!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

print("Hi Hannah")
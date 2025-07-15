#!/usr/bin/env python3
"""
Command-line interface for qcodespp.
"""

import sys
import argparse


def main():
    """Main entry point for the qcodespp CLI."""
    parser = argparse.ArgumentParser(
        description="qcodespp command-line interface",
        prog="qcodespp"
    )
    
    subparsers = parser.add_subparsers(
        dest="command", 
        help="Available commands"
    )
    
    # offline_plotting subcommand
    offline_parser = subparsers.add_parser(
        "offline_plotting",
        help="Start the offline plotting GUI"
    )
    offline_parser.add_argument(
        "--folder",
        type=str,
        default=None,
        help="Path to folder containing data files to be plotted"
    )
    offline_parser.add_argument(
        "--no-link-default",
        action="store_true",
        help="Don't link to the qcodespp default folder"
    )
    offline_parser.add_argument(
        "--no-thread",
        action="store_true", 
        help="Don't run in a separate thread (may be needed on some systems like macOS)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command == "offline_plotting":
        from qcodespp.plotting.offline.main import offline_plotting
        
        offline_plotting(
            folder=args.folder,
            link_to_default=not args.no_link_default,
            use_thread=not args.no_thread
        )
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

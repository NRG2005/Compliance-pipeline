import argparse
import asyncio
import sys
import os

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the two entry points we want to expose
from demo import run_pipeline as queue_run_pipeline
from run_real_tests import run as random_test_run

async def main():
    parser = argparse.ArgumentParser(description="Unified entry point for the Compliance Pipeline.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--queue",
        action="store_true",
        help="Pull transactions from the Azure queue and run the pipeline (default).",
    )
    mode_group.add_argument(
        "--test",
        action="store_true",
        help="Run the randomized test suite (previously run_real_tests).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of messages to pull from the Azure queue when using --queue.",
    )
    args = parser.parse_args()

    if args.test:
        # Run the random test suite
        await random_test_run()
    else:
        # Default to queue mode
        await queue_run_pipeline(count=args.count)

if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DB_URL = "postgresql://postgres:postgres@127.0.0.1:15432/postgres"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"


@dataclass(frozen=True)
class LoadStep:
    name: str
    module: str
    description: str
    unsafe: bool = False
    depends_on: tuple[str, ...] = ()


LOAD_STEPS = [
    LoadStep("media", "src.load.load_media", "Load catalog.media"),
    LoadStep("color", "src.load.load_color", "Load catalog.color"),
    LoadStep("materials", "src.load.load_materials", "Load catalog.material"),
    LoadStep("category", "src.load.load_category", "Load catalog.category"),
    LoadStep("collection", "src.load.load_collection", "Load catalog.collection"),
    LoadStep(
        "product_line",
        "src.load.load_product_line",
        "Load catalog.product_line",
        unsafe=True,
    ),
    LoadStep(
        "line_category",
        "src.load.load_line_category",
        "Load catalog.line_category",
        depends_on=("product_line",),
    ),
    LoadStep("size_chart", "src.load.load_size_chart", "Load catalog.size_chart"),
    LoadStep("size_option", "src.load.load_size_option", "Load catalog.size_option"),
    LoadStep(
        "measurement_type",
        "src.load.load_measurement_type",
        "Load catalog.measurement_type",
    ),
    LoadStep(
        "size_measurement",
        "src.load.load_size_measurement",
        "Load catalog.size_measurement",
    ),
    LoadStep(
        "product_component",
        "src.load.load_product_component",
        "Load catalog.product_component",
        depends_on=("product_line",),
    ),
    LoadStep(
        "product_variant",
        "src.load.load_product_variant",
        "Load catalog.product_variant",
        depends_on=("product_component",),
    ),
    LoadStep(
        "product_line_media",
        "src.load.load_product_line_media",
        "Load catalog.product_line_media",
        depends_on=("product_line",),
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run master-data loaders in dependency order."
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help=f"Run all steps against local Postgres ({LOCAL_DB_URL}).",
    )
    parser.add_argument(
        "--db-url",
        help="Override target database URL for all loader steps.",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        help="Run only specific step names, for example: color collection size_chart",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        default=[],
        help="Skip specific step names.",
    )
    parser.add_argument(
        "--include-unsafe",
        action="store_true",
        help="Include steps marked unsafe, such as product_line.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print available step names and exit.",
    )
    return parser.parse_args()


def print_step_list() -> None:
    for step in LOAD_STEPS:
        suffix = " [unsafe]" if step.unsafe else ""
        print(f"{step.name}: {step.description}{suffix}")


def validate_step_names(step_names: set[str]) -> None:
    known_names = {step.name for step in LOAD_STEPS}
    unknown_names = sorted(step_names - known_names)
    if unknown_names:
        raise ValueError(f"Unknown step names: {unknown_names}")


def select_steps(args: argparse.Namespace) -> list[LoadStep]:
    requested_only = set(args.only or [])
    requested_skip = set(args.skip or [])

    validate_step_names(requested_only | requested_skip)

    selected_steps: list[LoadStep] = []
    for step in LOAD_STEPS:
        if requested_only and step.name not in requested_only:
            continue
        if step.name in requested_skip:
            continue
        if step.unsafe and not args.include_unsafe:
            continue
        selected_steps.append(step)

    selected_by_name = {step.name: step for step in selected_steps}
    skipped_due_to_dependencies: dict[str, tuple[str, ...]] = {}

    changed = True
    while changed:
        changed = False
        current_names = set(selected_by_name)
        for step_name, step in list(selected_by_name.items()):
            missing_dependencies = tuple(
                dependency
                for dependency in step.depends_on
                if dependency not in current_names
            )
            if not missing_dependencies:
                continue

            skipped_due_to_dependencies[step_name] = missing_dependencies
            del selected_by_name[step_name]
            changed = True

    for step_name, missing_dependencies in skipped_due_to_dependencies.items():
        missing_list = ", ".join(missing_dependencies)
        print(
            f"Skipping step '{step_name}' because required dependency is not selected: "
            f"{missing_list}"
        )

    return [step for step in LOAD_STEPS if step.name in selected_by_name]


def build_child_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()

    if args.db_url:
        env["SUPABASE_DB_URL"] = args.db_url
    elif args.local:
        env["SUPABASE_DB_URL"] = LOCAL_DB_URL

    return env


def describe_target(args: argparse.Namespace) -> str:
    if args.db_url:
        return args.db_url
    if args.local:
        return LOCAL_DB_URL
    return "environment-configured database"


def run_step(step: LoadStep, env: dict[str, str]) -> None:
    python_executable = str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable))
    cmd = [python_executable, "-m", step.module]
    print(f"\n==> {step.name}: {step.description}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=True)


def main() -> int:
    args = parse_args()

    if args.list:
        print_step_list()
        return 0

    selected_steps = select_steps(args)
    if not selected_steps:
        raise ValueError("No loader steps selected.")

    env = build_child_env(args)
    print(f"Target database: {describe_target(args)}")
    print("Selected steps:")
    for step in selected_steps:
        suffix = " [unsafe]" if step.unsafe else ""
        print(f"- {step.name}{suffix}")

    for step in selected_steps:
        run_step(step, env)

    print("\nAll selected loader steps completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

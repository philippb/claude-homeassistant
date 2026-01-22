#!/usr/bin/env python3
"""Test suite runner for Home Assistant configuration validation.

Runs all validators and provides a comprehensive report.
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.ha_official_validator import HAOfficialValidator
from tools.reference_validator import ReferenceValidator
from tools.yaml_validator import YAMLValidator


@dataclass
class ValidatorResult:
    description: str
    passed: bool
    info: list[str]
    errors: list[str]
    warnings: list[str]
    duration: float


def run_validator(validator: Any, description: str) -> ValidatorResult:
    """Run a single validator."""
    start_time = time.time()
    try:
        is_valid = validator.validate_all()
        duration = time.time() - start_time
        return ValidatorResult(
            description,
            is_valid,
            getattr(validator, "info", []),
            validator.errors,
            validator.warnings,
            duration,
        )
    except Exception as e:
        duration = time.time() - start_time
        return ValidatorResult(
            description, False, [], [f"Failed to run validator: {e}"], [], duration
        )


def run_all_tests(config_dir: Path) -> list[ValidatorResult]:
    """Run all validation tests."""
    validators = [
        (YAMLValidator, "YAML Syntax Validation"),
        (
            ReferenceValidator,
            "Entity/Device Reference Validation",
        ),
        (
            HAOfficialValidator,
            "Official Home Assistant Configuration Validation",
        ),
    ]

    total_duration = 0.0

    print("🔍 Running Home Assistant Configuration Validation Tests")
    print("=" * 60)
    print()

    results = []

    for validator, description in validators:
        print(f"Running {description}...")
        validator_instance = validator(config_dir)
        result = run_validator(validator_instance, description)
        total_duration += result.duration
        results.append(result)

        if result.passed:
            print(f"  ✅ PASSED ({result.duration:.2f}s)")
        else:
            print(f"  ❌ FAILED ({result.duration:.2f}s)")

        print()

    print(f"Total execution time: {total_duration:.2f}s")
    print("=" * 60)

    return results


def run(config_dir: Path) -> bool:
    """Run the complete test suite."""
    if not config_dir.exists():
        print(f"❌ Config directory not found: {config_dir}")
        return False
    results = run_all_tests(config_dir)
    print_detailed_results(results)
    print_summary(results)
    return all(result.passed for result in results)


def print_detailed_results(results: list[ValidatorResult]) -> None:
    """Print detailed results for each validator."""
    for result in results:
        print(f"\n📋 {result.description}")
        print("-" * 50)

        if result.passed:
            print("Status: ✅ PASSED")
        else:
            print("Status: ❌ FAILED")

        print(f"Duration: {result.duration:.2f}s")

        info = result.info
        if info:
            print("\nINFO:")
            for item in info:
                print(f"  ℹ️  {item}")

        errors = result.errors
        if errors:
            print("\nERRORS:")
            for error in errors:
                print(f"  ❌ {error}")

        warnings = result.warnings
        if warnings:
            print("\nWARNINGS:")
            for warning in warnings:
                print(f"  ⚠️  {warning}")

        if not errors and not warnings:
            print("\n✅ No issues found")

        print()


def print_summary(results: list[ValidatorResult]) -> None:
    """Print test summary."""
    total_tests = len(results)
    passed_tests = sum(r.passed for r in results)
    failed_tests = total_tests - passed_tests

    print("\n📊 TEST SUMMARY")
    print("=" * 30)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")

    if failed_tests == 0:
        print("\n🎉 All tests passed! Your Home Assistant configuration is valid.")
    else:
        print(f"\n⚠️  {failed_tests} test(s) failed. Please review the errors above.")

    print()


def main():
    """Run main function for command line usage."""
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "config"
    success = run(Path(config_dir))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

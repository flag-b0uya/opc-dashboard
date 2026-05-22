import sys
import unittest


PHASE1_TEST_MODULES = [
    "tests.test_query_bank",
    "tests.test_noise_filter",
    "tests.test_manual_intake",
    "tests.test_source_metrics",
    "tests.test_pipeline_enricher",
    "tests.test_demand_pipeline_integration",
    "tests.test_local_runner_config",
    "tests.test_snapshot_exporter",
    "tests.test_dashboard_presenter",
    "tests.test_health_check",
    "tests.test_snapshot_upgrade",
    "tests.test_delivery_check",
]


def load_phase1_suite():
    return unittest.defaultTestLoader.loadTestsFromNames(PHASE1_TEST_MODULES)


def main():
    result = unittest.TextTestRunner(verbosity=2).run(load_phase1_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

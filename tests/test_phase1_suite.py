import unittest

from phase1_test_suite import PHASE1_TEST_MODULES, load_phase1_suite


class Phase1SuiteTest(unittest.TestCase):
    def test_phase1_suite_lists_only_first_phase_modules(self):
        expected = {
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
        }

        self.assertEqual(set(PHASE1_TEST_MODULES), expected)
        self.assertNotIn("tests.test_container_pipeline", PHASE1_TEST_MODULES)
        self.assertNotIn("tests.test_comment_pipeline", PHASE1_TEST_MODULES)

    def test_load_phase1_suite_returns_unittest_suite(self):
        suite = load_phase1_suite()

        self.assertIsInstance(suite, unittest.TestSuite)
        self.assertGreater(suite.countTestCases(), 0)


if __name__ == "__main__":
    unittest.main()

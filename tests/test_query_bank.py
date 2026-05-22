import unittest

from query_bank import runner_app_ids, runner_hn_queries, runner_subreddits


class QueryBankTest(unittest.TestCase):
    def test_runner_defaults_live_in_query_bank(self):
        self.assertIn("manual workflow", runner_hn_queries)
        self.assertIn("SaaS", runner_subreddits)
        self.assertIn("1232780281", runner_app_ids)


if __name__ == "__main__":
    unittest.main()

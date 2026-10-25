from rowproof.benchmark import benchmark
from tests.support import ProjectCase


class BenchmarkTests(ProjectCase):
    def test_control_flow_ablation_distinguishes_false_success_from_valid_artifacts(self):
        result = benchmark(self.root / "benchmark", repetitions=1)
        policies = {item["policy"]: item for item in result["policies"]}
        self.assertEqual(policies["exit-code-only"]["false_successes"], 1)
        self.assertEqual(policies["verify-only"]["reported_successes"], 0)
        self.assertEqual(policies["verify-and-repair"]["valid_artifacts"], 1)
        self.assertEqual(policies["verify-and-repair"]["mean_attempts"], 2)
        self.assertEqual(result["experiment_type"], "scripted_fixture_control_flow")

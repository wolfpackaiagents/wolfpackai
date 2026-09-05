"""Tests for deterministic evaluations and AMP score publishing."""

from wolfpack.evals import AmpScorePublisher, CallableEvaluator, EvalCase, EvalRunner, EvalScore


def test_runner_scores_cases_and_calculates_averages():
    exact_match = CallableEvaluator("exact_match", lambda case, output: output == case.expected)
    runner = EvalRunner(lambda text: text.upper(), [exact_match])

    report = runner.run([EvalCase(input="wolf", expected="WOLF"), EvalCase(input="pack", expected="wrong")])

    assert [result.scores[0].value for result in report.results] == [1.0, 0.0]
    assert report.averages == {"exact_match": 0.5}


def test_runner_publishes_each_score_for_cases_with_trace_ids():
    published = []

    class Publisher:
        def publish(self, trace_id, score):
            published.append((trace_id, score.name, score.value))

    runner = EvalRunner(
        lambda value: value,
        [CallableEvaluator("quality", lambda case, output: EvalScore("quality", 0.8))],
        publisher=Publisher(),
    )

    runner.run([EvalCase(input="answer", trace_id="trace_1"), EvalCase(input="local")])

    assert published == [("trace_1", "quality", 0.8)]


def test_amp_publisher_uses_public_scores_contract(monkeypatch):
    publisher = AmpScorePublisher("http://amp.test", "pk-test")
    captured = {}

    def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload

    monkeypatch.setattr(publisher, "_post", fake_post)
    publisher.publish("trace_1", EvalScore("correctness", 1.0, "matched expected output"))

    assert captured == {
        "path": "/scores",
        "payload": {
            "trace_id": "trace_1",
            "name": "correctness",
            "source": "EVAL",
            "value": 1.0,
            "comment": "matched expected output",
        },
    }

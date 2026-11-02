import unittest
import time
from src.congestion.manager import CongestionManager, CongestionState
from src.congestion.prediction import calculate_trend_and_prediction

class TestCongestionPrediction(unittest.TestCase):
    def setUp(self):
        self.manager = CongestionManager()
        self.manager.MAX_HISTORY_POINTS = 5 # Small bound for testing bounding

    def test_history_stores_completed_observations(self):
        # TEST 1
        job = self.manager.create_job("SJT")
        self.manager.update_job(job, {"location": "SJT", "congestion_score": 0.5})
        hist = self.manager.get_history("SJT")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0].congestion_score, 0.5)

    def test_history_is_separated_by_location(self):
        # TEST 2
        job1 = self.manager.create_job("SJT")
        self.manager.update_job(job1, {"location": "SJT", "congestion_score": 0.5})
        job2 = self.manager.create_job("TT")
        self.manager.update_job(job2, {"location": "TT", "congestion_score": 0.3})
        self.assertEqual(len(self.manager.get_history("SJT")), 1)
        self.assertEqual(len(self.manager.get_history("TT")), 1)

    def test_history_is_bounded(self):
        # TEST 3
        for i in range(10):
            job = self.manager.create_job("SJT")
            self.manager.update_job(job, {"location": "SJT", "congestion_score": 0.1 * i})
        
        hist = self.manager.get_history("SJT")
        self.assertEqual(len(hist), 5) # bounded by max history size

    def test_insufficient_history_produces_no_prediction(self):
        # TEST 7
        job1 = self.manager.create_job("SJT")
        self.manager.update_job(job1, {"location": "SJT", "congestion_score": 0.5})
        job2 = self.manager.create_job("SJT")
        self.manager.update_job(job2, {"location": "SJT", "congestion_score": 0.5})
        hist = self.manager.get_history("SJT")
        pred = calculate_trend_and_prediction(hist)
        self.assertFalse(pred["prediction_available"])

    def test_increasing_data_produces_increasing_trend(self):
        # TEST 4, 8
        t0 = time.time()
        hist = [
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.20, timestamp=t0),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.30, timestamp=t0 + 60),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.40, timestamp=t0 + 120),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.50, timestamp=t0 + 180),
        ]
        pred = calculate_trend_and_prediction(hist, horizon_minutes=10)
        self.assertTrue(pred["prediction_available"])
        self.assertEqual(pred["trend"], "INCREASING")
        self.assertTrue(pred["slope"] > 0)
        self.assertTrue(pred["predicted_score"] > 0.50)

    def test_decreasing_data_produces_decreasing_trend(self):
        # TEST 5
        t0 = time.time()
        hist = [
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.50, timestamp=t0),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.48, timestamp=t0 + 60),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.46, timestamp=t0 + 120),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.44, timestamp=t0 + 180),
        ]
        pred = calculate_trend_and_prediction(hist, horizon_minutes=10)
        self.assertTrue(pred["prediction_available"])
        self.assertEqual(pred["trend"], "DECREASING")
        self.assertTrue(pred["slope"] < 0)

    def test_stable_data_produces_stable_trend(self):
        # TEST 6
        t0 = time.time()
        hist = [
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.40, timestamp=t0),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.41, timestamp=t0 + 60),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.39, timestamp=t0 + 120),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.40, timestamp=t0 + 180),
        ]
        pred = calculate_trend_and_prediction(hist, horizon_minutes=10)
        self.assertTrue(pred["prediction_available"])
        self.assertEqual(pred["trend"], "STABLE")

    def test_prediction_is_clamped(self):
        # TEST 9
        t0 = time.time()
        hist = [
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.80, timestamp=t0),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=0.90, timestamp=t0 + 60),
            CongestionState(location="SJT", average_people=0, peak_people=0, congestion_level="", congestion_score=1.00, timestamp=t0 + 120),
        ]
        pred = calculate_trend_and_prediction(hist, horizon_minutes=10)
        self.assertTrue(pred["prediction_available"])
        self.assertEqual(pred["predicted_score"], 1.0) # clamped to 1.0

if __name__ == "__main__":
    unittest.main()

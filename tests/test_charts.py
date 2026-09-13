"""Regression checks for the sparse-data charts shown in Live mode."""
import unittest
import pandas as pd
import plotly.express as px
from pulse.ui.analytics import bars, time_axis


class ChartScales(unittest.TestCase):
    def test_single_bar_does_not_fill_panel(self):
        chart = bars(["Sewage"], [1])
        self.assertEqual(chart.data[0].width, .32)
        self.assertGreaterEqual(chart.layout.yaxis.range[0], 3.5)
        self.assertEqual(chart.layout.xaxis.dtick, 1)

    def test_risk_uses_full_scale(self):
        chart = bars(["Gulshan-e-Iqbal"], [53], risk=True)
        self.assertEqual(tuple(chart.layout.xaxis.range), (0, 100))

    def test_single_timestamp_has_meaningful_range(self):
        data = pd.DataFrame({"time": pd.to_datetime(["2026-09-12T21:00:00+05:00"]), "reports": [3]})
        chart = time_axis(px.line(data, x="time", y="reports"), data.time)
        start, end = chart.layout.xaxis.range
        self.assertGreaterEqual(end-start, pd.Timedelta(hours=1))
        self.assertEqual(chart.layout.xaxis.tickformat, "%H:%M<br>%d %b")


if __name__ == "__main__":
    unittest.main()

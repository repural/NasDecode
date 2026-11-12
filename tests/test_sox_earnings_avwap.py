import datetime as dt
import unittest
from scripts.sox_earnings_avwap import compute, aggregate

def bar(d,vw,c=None,volume=100):
    return {"t":int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()*1000),"vw":vw,"v":volume,"c":c or vw}

class TestAVWAP(unittest.TestCase):
    def test_after_close_anchor(self):
        r=compute([bar("2026-10-01",100),bar("2026-10-02",110)],"2026-10-01","after_close",asof=dt.date(2026,10,2))
        self.assertEqual(r["anchorDate"],"2026-10-02")
        self.assertEqual(r["avwap"],110)
    def test_weighted_and_momentum(self):
        bs=[bar(f"2026-10-{i:02d}",100+i,100+i,100*i) for i in range(1,9)]
        r=compute(bs,"2026-10-01","before_open",asof=dt.date(2026,10,8))
        self.assertAlmostEqual(r["avwap"],sum((100+i)*i for i in range(1,9))/sum(range(1,9)),places=4)
        self.assertIsNotNone(r["momentumPp"]["5d"])
    def test_fail_closed(self):
        self.assertEqual(compute([],"2026-04-01","after_close",asof=dt.date(2026,10,8))["status"],"outdated_anchor")
        self.assertEqual(compute([] ,None,None)["status"],"unverified_anchor")
    def test_denominator_and_basket(self):
        d={"A":{"status":"ok","distancePct":11,"momentumPp":{"1d":1,"3d":2,"5d":3}},
           "B":{"status":"ok","distancePct":-2,"momentumPp":{"1d":-1,"3d":0,"5d":1}}}
        a=aggregate(d,["A","B","C"],["A","C"])
        self.assertEqual(a["sox"]["covered"],2)
        self.assertEqual(a["sox"]["breadthPct"],50)
        self.assertEqual(a["originalBasket"]["breadthPct"],100)
        self.assertEqual(a["excluded"]["C"],"missing_anchor")

if __name__=="__main__": unittest.main()

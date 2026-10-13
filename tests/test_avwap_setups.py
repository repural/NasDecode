import datetime as dt
import unittest
from scripts.avwap_setups import assess

def bar(day,o,h,l,c,vw=None):
    stamp=int(dt.datetime(2026,10,day,tzinfo=dt.timezone.utc).timestamp()*1000)
    return {"t":stamp,"o":o,"h":h,"l":l,"c":c,"v":100,"vw":vw if vw is not None else c}

class AVWAPResearchTests(unittest.TestCase):
    def test_daily_bounce_proxy_vs_approaching(self):
        bars=[bar(6,103,104,102,103),bar(7,101,104,100,103)]
        anchors={"lowestLow":{"anchorDate":"2026-10-06","avwap":102}}
        touch,_,_=assess(bars,anchors,103,1.0,False)
        self.assertEqual(touch["state"],"match")
        self.assertEqual(touch["phase"],"bounce_confirmed_daily_proxy")
        self.assertTrue(touch["aggressiveTouch"])

    def test_reclaim_uses_each_sessions_avwap(self):
        bars=[bar(6,100,104,99,100,vw=102),bar(7,104,107,100,105,vw=104)]
        anchors={"highestHigh":{"anchorDate":"2026-10-06","avwap":103}}
        _,reclaim,_=assess(bars,anchors,105,1.0,False)
        self.assertEqual(reclaim["state"],"match")
        self.assertEqual(reclaim["reclaimedAnchors"],["highestHigh"])

    def test_pinch_checks_pair_not_just_two_lowest(self):
        bars=[bar(6,100,105,95,101,100),bar(7,100,105,95,101,101)]
        anchors={"a":{"anchorDate":"2026-10-06","avwap":100},
                 "b":{"anchorDate":"2026-10-06","avwap":101},
                 "c":{"anchorDate":"2026-10-06","avwap":101}}
        _,_,pinch=assess(bars,anchors,101,1.0,False)
        self.assertEqual(len(pinch["pairs"]),3)
        self.assertTrue(any(p["anchors"]==["a","c"] for p in pinch["pairs"]))

if __name__=="__main__":
    unittest.main()

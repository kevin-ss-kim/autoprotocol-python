import unittest
from autoprotocol.protocol import Protocol, Ref
from autoprotocol.instruction import Instruction, Thermocycle, Incubate, Pipette, Spin
from autoprotocol.container_type import ContainerType
from autoprotocol.container import Container, WellGroup, Well
from autoprotocol.unit import Unit
from autoprotocol.pipette_tools import *
import json


class ProtocolMultipleExistTestCase(unittest.TestCase):
    def runTest(self):
        p1 = Protocol()
        p2 = Protocol()

        p1.spin("dummy_ref", "2000:rpm", "560:second")
        self.assertEqual(len(p2.instructions), 0,
            "incorrect number of instructions in empty protocol")


class ProtocolBasicTestCase(unittest.TestCase):
    def runTest(self):
        protocol = Protocol()
        resource = protocol.ref("resource", None, "96-flat", discard=True)
        pcr = protocol.ref("pcr", None, "96-flat", discard=True)
        bacteria = protocol.ref("bacteria", None, "96-flat", discard=True)
        self.assertEqual(len(protocol.as_dict()['refs']), 3, 'incorrect number of refs')
        self.assertEqual(protocol.as_dict()['refs']['resource'], {"new": "96-flat",
                        "discard": True})

        bacteria_wells = WellGroup([bacteria.well("B1"), bacteria.well("C5"),
                                    bacteria.well("A5"), bacteria.well("A1")])

        protocol.distribute(resource.well("A1").set_volume("40:microliter"),
                            pcr.wells_from('A1',5), "5:microliter")
        protocol.distribute(resource.well("A1").set_volume("40:microliter"),
                            bacteria_wells, "5:microliter")

        self.assertEqual(len(protocol.instructions), 1)
        self.assertEqual(protocol.instructions[0].op, "pipette")
        self.assertEqual(len(protocol.instructions[0].groups), 2)

        protocol.incubate(bacteria, "warm_37", "30:minute")

        self.assertEqual(len(protocol.instructions), 2)
        self.assertEqual(protocol.instructions[1].op, "incubate")
        self.assertEqual(protocol.instructions[1].duration, "30:minute")


class ProtocolAppendTestCase(unittest.TestCase):
    def runTest(self):
        p = Protocol()
        self.assertEqual(len(p.instructions), 0,
            "should not be any instructions before appending to empty protocol")

        p.append(Spin("dummy_ref", "100:meter/second^2", "60:second"))
        self.assertEqual(len(p.instructions), 1,
            "incorrect number of instructions after single instruction append")
        self.assertEqual(p.instructions[0].op, "spin",
            "incorrect instruction appended")

        p.append([
                    Incubate("dummy_ref", "ambient", "30:second"),
                    Spin("dummy_ref", "2000:rpm", "120:second")
                ])
        self.assertEqual(len(p.instructions), 3,
            "incorrect number of instructions after appending instruction list")
        self.assertEqual(p.instructions[1].op, "incubate",
            "incorrect instruction order after list append")
        self.assertEqual(p.instructions[2].op, "spin",
            "incorrect instruction at end after list append.")


class RefTestCase(unittest.TestCase):
    def test_duplicates_not_allowed(self):
        p = Protocol()
        p.ref("test", None, "96-flat", discard=True)
        with self.assertRaises(RuntimeError):
            p.ref("test", None, "96-flat", storage="cold_20")
        self.assertTrue(p.refs["test"].opts["discard"])
        self.assertFalse("where" in p.refs["test"].opts)


class ThermocycleTestCase(unittest.TestCase):
    def test_thermocycle_append(self):
        t = Thermocycle("plate", [
            { "cycles": 1, "steps": [
                { "temperature": "95:celsius", "duration": "60:second" },
            ] },
            { "cycles": 30, "steps": [
                { "temperature": "95:celsius", "duration": "15:second" },
                { "temperature": "55:celsius", "duration": "15:second" },
                { "temperature": "72:celsius", "duration": "10:second" },
            ] },
            { "cycles": 1, "steps": [
                { "temperature": "72:celsius", "duration": "600:second" },
                { "temperature": "12:celsius", "duration": "120:second" },
            ] },
        ], "20:microliter")
        self.assertEqual(len(t.groups), 3, 'incorrect number of groups')
        self.assertEqual(t.volume, "20:microliter")

    def test_thermocycle_dyes_and_datarefs(self):
        self.assertRaises(ValueError,
                    Thermocycle,
                    "plate",
                    [{"cycles": 1,
                      "steps": [{
                          "temperature": "50: celsius",
                          "duration": "20:minute"
                      }]
                      }],
                    dyes={"FAM": ["A1"]})
        self.assertRaises(ValueError,
                    Thermocycle,
                    "plate",
                    [{"cycles": 1,
                      "steps": [{
                          "temperature": "50: celsius",
                          "duration": "20:minute"
                      }]
                      }],
                    dataref="test_dataref")
        self.assertRaises(ValueError,
                    Thermocycle,
                    "plate",
                    [{"cycles": 1,
                      "steps": [{
                          "temperature": "50: celsius",
                          "duration": "20:minute"
                      }]
                      }],
                    dyes={"ThisDyeIsInvalid": ["A1"]})

    def test_thermocycle_melting(self):
        self.assertRaises(ValueError,
                    Thermocycle,
                    "plate",
                    [{"cycles": 1,
                      "steps": [{
                          "temperature": "50: celsius",
                          "duration": "20:minute"
                      }]
                      }],
                    melting_start = "50:celsius")
        self.assertRaises(ValueError,
                    Thermocycle,
                    "plate",
                    [{"cycles": 1,
                      "steps": [{
                          "temperature": "50: celsius",
                          "duration": "20:minute"
                      }]
                      }],
                    melting_start = "50:celsius",
                    melting_end = "60:celsius",
                    melting_increment = "1:celsius",
                    melting_rate = "2:minute")


class DistributeTestCase(unittest.TestCase):
    def test_distribute_one_well(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.distribute(c.well(0).set_volume("20:microliter"),
                     c.well(1),
                     "5:microliter")
        self.assertEqual(1, len(p.instructions))
        self.assertEqual("distribute",
                         list(p.as_dict()["instructions"][0]["groups"][0].keys())[0])
        self.assertTrue(Unit(5, 'microliter'), c.well(1).volume)
        self.assertTrue(Unit(15, 'microliter'), c.well(0).volume)

    def test_distribute_multiple_wells(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.distribute(c.well(0).set_volume("20:microliter"),
                     c.wells_from(1, 3),
                     "5:microliter")
        self.assertEqual(1, len(p.instructions))
        self.assertEqual("distribute",
                         list(p.as_dict()["instructions"][0]["groups"][0].keys())[0])
        for w in c.wells_from(1, 3):
            self.assertTrue(Unit(5, 'microliter'), w.volume)
        self.assertTrue(Unit(5, 'microliter'), c.well(0).volume)

    def test_fill_wells(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        srcs = c.wells_from(1, 2).set_volume("100:microliter")
        dests = c.wells_from(7, 4)
        p.distribute(srcs, dests, "30:microliter", allow_carryover=True)
        self.assertEqual(2, len(p.instructions[0].groups))

        # track source vols
        self.assertEqual(Unit(10, 'microliter'), c.well(1).volume)
        self.assertEqual(Unit(70, 'microliter'), c.well(2).volume)

        # track dest vols
        self.assertEqual(Unit(30, 'microliter'), c.well(7).volume)
        self.assertIs(None, c.well(6).volume)

        # test distribute from Well to Well
        p.distribute(c.well("A1").set_volume("20:microliter"), c.well("A2"), "5:microliter")
        self.assertTrue("distribute" in p.instructions[-1].groups[-1])

    def test_unit_conversion(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.distribute(c.well(0).set_volume("100:microliter"), c.well(1), "200:nanoliter")
        self.assertTrue(str(p.instructions[0].groups[0]["distribute"]["to"][0]["volume"]) == "0.2:microliter")
        p.distribute(c.well(2).set_volume("100:microliter"), c.well(3), ".1:milliliter", new_group=True)
        self.assertTrue(str(p.instructions[-1].groups[0]["distribute"]["to"][0]["volume"]) == "100.0:microliter")


class TransferTestCase(unittest.TestCase):
    def test_single_transfer(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.transfer(c.well(0), c.well(1), "20:microliter")
        self.assertEqual(Unit(20, "microliter"), c.well(1).volume)
        self.assertEqual(None, c.well(0).volume)
        self.assertTrue("transfer" in p.instructions[-1].groups[-1])

    def test_gt_750uL_transfer(self):
        p = Protocol()
        c = p.ref("test", None, "96-deep", discard=True)
        p.transfer(
            c.well(0),
            c.well(1),
            "1800:microliter"
            )
        self.assertEqual(3, len(p.instructions[0].groups))
        self.assertEqual(
            Unit(750, 'microliter'),
            p.instructions[0].groups[0]['transfer'][0]['volume']
            )
        self.assertEqual(
            Unit(750, 'microliter'),
            p.instructions[0].groups[1]['transfer'][0]['volume']
            )
        self.assertEqual(
            Unit(300, 'microliter'),
            p.instructions[0].groups[2]['transfer'][0]['volume']
            )

    def test_gt_750uL_wellgroup_transfer(self):
        p = Protocol()
        c = p.ref("test", None, "96-deep", discard=True)
        p.transfer(
            c.wells_from(0, 8, columnwise=True),
            c.wells_from(1, 8, columnwise=True),
            '1800:microliter'
            )
        self.assertEqual(
            24,
            len(p.instructions[0].groups)
            )

    def test_transfer_option_propagation(self):
        p = Protocol()
        c = p.ref("test", None, "96-deep", discard=True)
        p.transfer(
            c.well(0),
            c.well(1),
            "1800:microliter",
            aspirate_source=aspirate_source(
                depth("ll_bottom", distance=".004:meter")
                )
            )
        self.assertEqual(
            len(p.instructions[0].groups[0]['transfer'][0]),
            len(p.instructions[0].groups[1]['transfer'][0])
            )
        self.assertEqual(
            len(p.instructions[0].groups[0]['transfer'][0]),
            len(p.instructions[0].groups[2]['transfer'][0])
            )

    def test_max_transfer(self):
        p = Protocol()
        c = p.ref("test", None, "micro-2.0", storage="cold_4")
        p.transfer(c.well(0), c.well(0), "3050:microliter")

    def test_multiple_transfers(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.transfer(c.wells_from(0, 2), c.wells_from(2, 2), "20:microliter")
        self.assertEqual(c.well(2).volume, c.well(3).volume)
        self.assertEqual(2, len(p.instructions[0].groups))

    def test_one_tip(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.transfer(c.wells_from(0, 2), c.wells_from(2, 2), "20:microliter",
            one_tip=True)
        self.assertEqual(c.well(2).volume, c.well(3).volume)
        self.assertEqual(1, len(p.instructions[0].groups))

    def test_one_source(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        with self.assertRaises(RuntimeError):
            p.transfer(c.wells_from(0, 2),
                   c.wells_from(2, 2), "40:microliter", one_source=True)
        with self.assertRaises(RuntimeError):
            p.transfer(c.wells_from(0, 2).set_volume("1:microliter"),
                       c.wells_from(1, 5), "10:microliter", one_source=True)
        p.transfer(c.wells_from(0, 2).set_volume("50:microliter"),
                   c.wells_from(2, 2), "40:microliter", one_source=True)
        self.assertEqual(2, len(p.instructions[0].groups))
        self.assertFalse(p.instructions[0].groups[0]["transfer"][0]["from"] == p.instructions[0].groups[1]["transfer"][0]["from"])
        p.transfer(c.wells_from(0, 2).set_volume("100:microliter"),
                   c.wells_from(2, 4), "40:microliter", one_source=True)
        self.assertEqual(7, len(p.instructions[0].groups))
        self.assertTrue(p.instructions[0].groups[2]["transfer"][0]["from"] == p.instructions[0].groups[4]["transfer"][0]["from"])
        self.assertTrue(p.instructions[0].groups[4]["transfer"][0]["volume"] == Unit.fromstring("20:microliter"))
        p.transfer(c.wells_from(0, 2).set_volume("100:microliter"),
                   c.wells_from(2, 4), ["20:microliter", "40:microliter", "60:microliter", "80:microliter"], one_source=True)
        self.assertEqual(12, len(p.instructions[0].groups))
        self.assertTrue(p.instructions[0].groups[7]["transfer"][0]["from"] == p.instructions[0].groups[9]["transfer"][0]["from"])
        self.assertFalse(p.instructions[0].groups[9]["transfer"][0]["from"] == p.instructions[0].groups[10]["transfer"][0]["from"])
        self.assertEqual(Unit.fromstring("20:microliter"), p.instructions[0].groups[10]["transfer"][0]["volume"])
        p.transfer(c.wells_from(0, 2).set_volume("50:microliter"), c.wells(2), "100:microliter", one_source=True)
        c.well(0).set_volume("50:microliter")
        c.well(1).set_volume("200:microliter")
        p.transfer(c.wells_from(0, 2), c.well(1), "100:microliter", one_source=True)
        self.assertFalse(p.instructions[0].groups[14]["transfer"][0]["from"] == p.instructions[0].groups[15]["transfer"][0]["from"])
        c.well(0).set_volume("100:microliter")
        c.well(1).set_volume("0:microliter")
        c.well(2).set_volume("100:microliter")
        p.transfer(c.wells_from(0, 3), c.wells_from(3, 2), "100:microliter", one_source=True)

    def test_one_tip_true_gt_750(self):
        p = Protocol()
        c = p.ref("test", None, "96-deep", discard=True)
        p.transfer(c.well(0), c.well(1), "1000:microliter", one_tip=True)
        self.assertEqual(1, len(p.instructions[0].groups))

    def test_unit_conversion(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.transfer(c.well(0), c.well(1), "200:nanoliter")
        self.assertTrue(str(p.instructions[0].groups[0]['transfer'][0]['volume']) == "0.2:microliter")
        p.transfer(c.well(1), c.well(2), ".5:milliliter", new_group=True)
        self.assertTrue(str(p.instructions[-1].groups[0]['transfer'][0]['volume']) == "500.0:microliter")

    def test_volume_rounding(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        c.well(0).set_volume("100.0000000000005:microliter")
        c.well(1).set_volume("100:microliter")
        p.transfer(c.wells_from(0, 2), c.wells_from(3, 3), "50:microliter", one_source=True)
        self.assertEqual(3, len(p.instructions[0].groups))

        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        c.well(0).set_volume("50:microliter")
        c.well(1).set_volume("101:microliter")
        p.transfer(c.wells_from(0, 2), c.wells_from(3, 3), "50.0000000000005:microliter", one_source=True)
        self.assertEqual(3, len(p.instructions[0].groups))

    def test_mix_before_and_after(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        with self.assertRaises(RuntimeError):
            p.transfer(c.well(0), c.well(1), "10:microliter", mix_vol="15:microliter")
            p.transfer(c.well(0), c.well(1), "10:microliter", repetitions_a=21)
            p.transfer(c.well(0), c.well(1), "10:microliter", repetitions=21)
            p.transfer(c.well(0), c.well(1), "10:microliter", repetitions_b=21)
            p.transfer(c.well(0), c.well(1), "10:microliter", flowrate_a="200:microliter/second")
        p.transfer(c.well(0), c.well(1), "12:microliter", mix_after=True,
                   mix_vol="10:microliter", repetitions_a=20)
        self.assertTrue(int(p.instructions[-1].groups[0]['transfer'][0]['mix_after']['repetitions']) == 20)
        p.transfer(c.well(0), c.well(1), "12:microliter", mix_after=True,
                   mix_vol="10:microliter", repetitions_b=20)
        self.assertTrue(int(p.instructions[-1].groups[-1]['transfer'][0]['mix_after']['repetitions']) == 10)
        p.transfer(c.well(0), c.well(1), "12:microliter", mix_after=True)
        self.assertTrue(int(p.instructions[-1].groups[-1]['transfer'][0]['mix_after']['repetitions']) == 10)
        self.assertTrue(str(p.instructions[-1].groups[-1]['transfer'][0]['mix_after']['speed']) == "100:microliter/second")
        self.assertTrue(str(p.instructions[-1].groups[-1]['transfer'][0]['mix_after']['volume']) == "6.0:microliter")
        p.transfer(c.well(0), c.well(1), "12:microliter", mix_before=True,
                   mix_vol="10:microliter", repetitions_b=20)
        self.assertTrue(int(p.instructions[-1].groups[-1]['transfer'][-1]['mix_before']['repetitions']) == 20)
        p.transfer(c.well(0), c.well(1), "12:microliter", mix_before=True,
                   mix_vol="10:microliter", repetitions_a=20)
        self.assertTrue(int(p.instructions[-1].groups[-1]['transfer'][-1]['mix_before']['repetitions']) == 10)
        p.transfer(c.well(0), c.well(1), "12:microliter", mix_before=True)
        self.assertTrue(int(p.instructions[-1].groups[-1]['transfer'][-1]['mix_before']['repetitions']) == 10)
        self.assertTrue(str(p.instructions[-1].groups[-1]['transfer'][-1]['mix_before']['speed']) == "100:microliter/second")
        self.assertTrue(str(p.instructions[-1].groups[-1]['transfer'][-1]['mix_before']['volume']) == "6.0:microliter")

    def test_mix_false(self):
        p = Protocol()
        c = p.ref("test", None, "96-deep", discard=True)
        p.transfer(c.well(0), c.well(1), "20:microliter", mix_after=False)
        self.assertFalse("mix_after" in p.instructions[0].groups[0]["transfer"][0])
        p.transfer(c.well(0), c.well(1), "20:microliter", mix_before=False)
        self.assertFalse("mix_before" in p.instructions[0].groups[1]["transfer"][0])
        p.transfer(c.well(0), c.well(1), "1800:microliter", mix_after=False)
        for i in range(2, 5):
            self.assertFalse("mix_after" in p.instructions[0].groups[i]["transfer"][0])
        p.transfer(c.well(0), c.well(1), "1800:microliter", mix_before=False)
        for i in range(5, 8):
            self.assertFalse("mix_before" in p.instructions[0].groups[i]["transfer"][0])


class ConsolidateTestCase(unittest.TestCase):
    def test_multiple_sources(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        with self.assertRaises(TypeError):
            p.consolidate(c.wells_from(0, 3), c.wells_from(2, 3), "10:microliter")
        with self.assertRaises(ValueError):
            p.consolidate(c.wells_from(0, 3), c.well(4), ["10:microliter"])
        p.consolidate(c.wells_from(0, 3), c.well(4), "10:microliter")
        self.assertEqual(Unit(30, "microliter"), c.well(4).volume)
        self.assertEqual(3, len(p.instructions[0].groups[0]["consolidate"]["from"]))

    def test_one_source(self):
        p = Protocol()
        c = p.ref("test", None, "96-flat", discard=True)
        p.consolidate(c.well(0), c.well(4), "30:microliter")
        self.assertEqual(Unit(30, "microliter"), c.well(4).volume)


class StampTestCase(unittest.TestCase):
    def test_volume_tracking(self):
        p = Protocol()
        plate_96 = p.ref("plate_96", None, "96-pcr", discard=True)
        plate_96_2 = p.ref("plate_96_2", None, "96-pcr", discard=True)
        plate_384 = p.ref("plate_384", None, "384-pcr", discard=True)
        plate_384_2 = p.ref("plate_384_2", None, "384-pcr", discard=True)
        p.stamp(plate_96.well(0), plate_384.well(0), "5:microliter",
                {"columns": 12, "rows": 1})
        self.assertEqual(plate_384.well(0).volume, Unit(5, 'microliter'))
        self.assertTrue(plate_384.well(1).volume is None)
        p.stamp(plate_96.well(0), plate_96_2.well(0), "10:microliter",
                {"columns": 12, "rows": 1})
        p.stamp(plate_96.well(0), plate_96_2.well(0), "10:microliter",
                {"columns": 1, "rows": 8})
        self.assertTrue(plate_96_2.well(0).volume == Unit(20, "microliter"))
        for w in plate_96_2.wells_from(1, 11):
            self.assertTrue(w.volume == Unit(10, "microliter"))
        p.stamp(plate_96.well(0), plate_384_2.well(0), "5:microliter",
                {"columns": 1, "rows": 8})
        for w in plate_384_2.wells_from(0, 16, columnwise=True)[0::2]:
            self.assertTrue(w.volume == Unit(5, "microliter"))
        for w in plate_384_2.wells_from(1, 16, columnwise=True)[0::2]:
            self.assertTrue(w.volume is None)
        for w in plate_384_2.wells_from(1, 24)[0::2]:
            self.assertTrue(w.volume is None)
        plate_384_2.all_wells().set_volume("0:microliter")
        p.stamp(plate_96.well(0), plate_384_2.well(0), "15:microliter", {"columns": 3, "rows": 8})
        self.assertEqual(plate_384_2.well("C3").volume, Unit(15, "microliter"))
        self.assertEqual(plate_384_2.well("B2").volume, Unit(0, "microliter"))

    def test_single_transfers(self):
        p = Protocol()
        plate_1_6 = p.ref("plate_1_6", None, "6-flat", discard=True)
        plate_1_96 = p.ref("plate_1_96", None, "96-flat", discard=True)
        plate_2_96 = p.ref("plate_2_96", None, "96-flat", discard=True)
        plate_1_384 = p.ref("plate_1_384", None, "384-flat", discard=True)
        plate_2_384 = p.ref("plate_2_384", None, "384-flat", discard=True)
        p.stamp(plate_1_96.well("G1"), plate_2_96.well("H1"),
                "10:microliter", dict(rows=1, columns=12))
        p.stamp(plate_1_96.well("A1"), plate_1_384.well("A2"),
                "10:microliter", dict(rows=8, columns=2))
        # Verify full plate to full plate transfer works for 96, 384 container input
        p.stamp(plate_1_96, plate_2_96, "10:microliter")
        p.stamp(plate_1_384, plate_2_384, "10:microliter")

        with self.assertRaises(ValueError):
            p.stamp(plate_1_96.well("A1"), plate_2_96.well("A2"),
                    "10:microliter", dict(rows=9, columns=1))
        with self.assertRaises(ValueError):
            p.stamp(plate_1_96.well("A1"), plate_2_96.well("B1"),
                    "10:microliter", dict(rows=1, columns=13))
        with self.assertRaises(ValueError):
            p.stamp(plate_1_384.well("A1"), plate_2_384.well("A2"),
                    "10:microliter", dict(rows=9, columns=1))
        with self.assertRaises(ValueError):
            p.stamp(plate_1_384.well("A1"), plate_2_384.well("B1"),
                    "10:microliter", dict(rows=1, columns=13))
        with self.assertRaises(ValueError):
            p.stamp(plate_1_96.well("A1"), plate_2_96.well("A2"),
                    "10:microliter", dict(rows=1, columns=12))
        with self.assertRaises(ValueError):
            p.stamp(plate_1_96.well("A1"), plate_2_96.well("D1"),
                    "10:microliter", dict(rows=6, columns=12))

    def test_multiple_transfers(self):
        # Set maximum number of full plate transfers (limited by maximum
        # number of tip boxes)
        maxFullTransfers = 4

        # Test: Ensure individual transfers are appended one at a time
        p = Protocol()
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat",
                     discard=True) for x in range(2)]

        for i in range(maxFullTransfers):
            p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                    "10:microliter")
            self.assertEqual(i+1, len(p.instructions[0].groups))

        # Ensure new stamp operation overflows into new instruction
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter")
        self.assertEqual(len(p.instructions), 2)
        self.assertEqual(1, len(p.instructions[1].groups))

        # Test: Maximum number of containers on a deck
        maxContainers = 3
        p = Protocol()
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat",
                     discard=True) for x in range(maxContainers+1)]

        for i in range(maxContainers-1):
            p.stamp(plateList[i], plateList[i+1], "10:microliter")
        self.assertEqual(1, len(p.instructions))
        self.assertEqual(maxContainers-1, len(p.instructions[0].groups))

        p.stamp(plateList[maxContainers-1].well("A1"),
                plateList[maxContainers].well("A1"), "10:microliter")
        self.assertEqual(2, len(p.instructions))

        # Test: Ensure col/row/full plate stamps are in separate instructions
        p = Protocol()
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat",
                     discard=True) for x in range(2)]

        p.stamp(plateList[0].well("G1"), plateList[1].well("G1"),
                "10:microliter", dict(rows=1, columns=12))
        self.assertEqual(len(p.instructions), 1)
        p.stamp(plateList[0].well("G1"), plateList[1].well("G1"),
                "10:microliter", dict(rows=2, columns=12))
        self.assertEqual(len(p.instructions), 1)
        self.assertEqual(len(p.instructions[0].groups), 2)

        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=2))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A12"),
                "10:microliter", dict(rows=8, columns=1))
        self.assertEqual(len(p.instructions), 2)
        self.assertEqual(len(p.instructions[1].groups), 2)

        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=12))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=12))
        self.assertEqual(len(p.instructions), 3)
        self.assertEqual(len(p.instructions[2].groups), 2)

        # Test: Check on max transfer limit - Full plate
        p = Protocol()
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat",
                     discard=True) for x in range(2)]

        for i in range(maxFullTransfers):
            p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                    "10:microliter", dict(rows=8, columns=12))
        self.assertEqual(len(p.instructions), 1)

        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=12))
        self.assertEqual(len(p.instructions), 2)
        self.assertEqual(maxFullTransfers, len(p.instructions[0].groups))
        self.assertEqual(1, len(p.instructions[1].groups))

        # Test: Check on max transfer limit - Row-wise
        p = Protocol()
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat",
                     discard=True) for x in range(2)]
        # Mixture of rows
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=3, columns=12))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=1, columns=12))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=2, columns=12))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=2, columns=12))
        self.assertEqual(len(p.instructions), 1)
        # Maximum number of row transfers
        for i in range(8):
            p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                    "10:microliter", dict(rows=1, columns=12))
        self.assertEqual(len(p.instructions), 2)
        self.assertEqual(len(p.instructions[0].groups), 4)
        self.assertEqual(len(p.instructions[1].groups), 8)
        # Overflow check
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=1, columns=12))
        self.assertEqual(len(p.instructions), 3)

        # Test: Check on max transfer limit - Col-wise
        p = Protocol()
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat",
                     discard=True) for x in range(2)]
        # Mixture of columns
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=4))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=6))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=2))
        self.assertEqual(len(p.instructions), 1)
        # Maximum number of col transfers
        for i in range(12):
            p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                    "10:microliter", dict(rows=8, columns=1))
        self.assertEqual(len(p.instructions), 2)
        self.assertEqual(len(p.instructions[0].groups), 3)
        self.assertEqual(len(p.instructions[1].groups), 12)

        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "10:microliter", dict(rows=8, columns=1))
        self.assertEqual(len(p.instructions), 3)

        # Test: Check on switching between tip volume types
        p = Protocol()
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat",
                     discard=True) for x in range(2)]
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "31:microliter")
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "31:microliter")
        self.assertEqual(len(p.instructions), 1)
        self.assertEqual(2, len(p.instructions[0].groups))

        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "90:microliter")
        self.assertEqual(len(p.instructions), 2)
        self.assertEqual(2, len(p.instructions[0].groups))
        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "90:microliter")
        self.assertEqual(len(p.instructions), 2)
        self.assertEqual(2, len(p.instructions[1].groups))

        p.stamp(plateList[0].well("A1"), plateList[1].well("A1"),
                "31:microliter")
        self.assertEqual(len(p.instructions), 3)

    def test_one_tip(self):

        p = Protocol()
        plateCount = 2
        plateList = [p.ref("plate_%s_384" % str(x+1), None, "384-flat", discard=True) for x in range(plateCount)]
        p.stamp(plateList[0], plateList[1], "330:microliter", one_tip=True)
        self.assertEqual(len(p.instructions[0].groups[0]["transfer"]), 12)
        self.assertEqual(len(p.instructions[0].groups), 1)

    def test_one_tip_variable_volume(self):

        p = Protocol()
        plateCount = 2
        plateList = [p.ref("plate_%s_384" % str(x+1), None, "384-flat", discard=True) for x in range(plateCount)]
        with self.assertRaises(RuntimeError):
            p.stamp(WellGroup([plateList[0].well(0), plateList[0].well(1)]), WellGroup([plateList[1].well(0), plateList[1].well(1)]), ["20:microliter", "90:microliter"], one_tip=True)
        p.stamp(WellGroup([plateList[0].well(0), plateList[0].well(1)]), WellGroup([plateList[1].well(0), plateList[1].well(1)]), ["20:microliter", "90:microliter"], mix_after=True, mix_vol="40:microliter", one_tip=True)
        self.assertEqual(len(p.instructions[0].groups[0]["transfer"]), 2)
        self.assertEqual(len(p.instructions[0].groups), 1)

    def test_wellgroup(self):
        p = Protocol()
        plateCount = 2
        plateList = [p.ref("plate_%s_384" % str(x+1), None, "384-flat", discard=True) for x in range(plateCount)]
        p.stamp(plateList[0].wells(list(range(12))), plateList[1].wells(list(range(12))), "30:microliter", shape={"rows": 8, "columns": 1})
        self.assertEqual(len(p.instructions[0].groups), 12)

    def test_gt_148uL_transfer(self):
        p = Protocol()
        plateCount = 2
        plateList = [p.ref("plate_%s_96" % str(x+1), None, "96-flat", discard=True) for x in range(plateCount)]
        p.stamp(plateList[0], plateList[1], "296:microliter")
        self.assertEqual(2, len(p.instructions[0].groups))
        self.assertEqual(
            Unit(148, 'microliter'),
            p.instructions[0].groups[0]['transfer'][0]['volume']
            )
        self.assertEqual(
            Unit(148, 'microliter'),
            p.instructions[0].groups[1]['transfer'][0]['volume']
            )

    def test_one_source(self):
        p = Protocol()
        plateCount = 2
        plateList = [p.ref("plate_%s_384" % str(x+1), None, "384-flat", discard=True) for x in range(plateCount)]
        with self.assertRaises(RuntimeError):
                p.stamp(plateList[0].wells(list(range(4))), plateList[1].wells(list(range(12))), "30:microliter", shape={"rows": 8, "columns": 1}, one_source=True)
        plateList[0].wells_from(0, 64, columnwise=True).set_volume("10:microliter")
        with self.assertRaises(RuntimeError):
                p.stamp(plateList[0].wells(list(range(4))), plateList[1].wells(list(range(12))), "30:microliter", shape={"rows": 8, "columns": 1}, one_source=True)
        plateList[0].wells_from(0, 64, columnwise=True).set_volume("15:microliter")
        p.stamp(plateList[0].wells(list(range(4))), plateList[1].wells(list(range(12))), "5:microliter", shape={"rows": 8, "columns": 1}, one_source=True)
        self.assertEqual(len(p.instructions[0].groups), 12)

class RefifyTestCase(unittest.TestCase):
    def test_refifying_various(self):
        p = Protocol()
        # refify container
        refs = {"plate": p.ref("test", None, "96-flat", "cold_20")}
        self.assertEqual(p._refify(refs["plate"]), "test")
        # refify dict
        self.assertEqual(p._refify(refs), {"plate": "test"})

        # refify Well
        well = refs["plate"].well("A1")
        self.assertEqual(p._refify(well), "test/0")

        # refify WellGroup
        wellgroup = refs["plate"].wells_from("A2", 3)
        self.assertEqual(p._refify(wellgroup), ["test/1", "test/2", "test/3"])

        # refify other
        s = "randomstring"
        i = 24
        self.assertEqual("randomstring", p._refify(s))
        self.assertEqual(24, p._refify(i))

class OutsTestCase(unittest.TestCase):
    def test_outs(self):
        p = Protocol()
        self.assertFalse('outs' in p.as_dict())
        plate = p.ref("plate", None, "96-pcr", discard=True)
        plate.well(0).set_name("test_well")
        plate.well(0).set_properties({"test": "foo"})
        self.assertTrue(plate.well(0).name == "test_well")
        self.assertTrue(list(p.as_dict()['outs'].keys()) == ['plate'])
        self.assertTrue(list(list(p.as_dict()['outs'].values())[0].keys()) == ['0'])
        self.assertTrue(list(p.as_dict()['outs'].values())[0]['0']['name'] == 'test_well')
        self.assertTrue(list(p.as_dict()['outs'].values())[0]['0']['properties']['test'] == 'foo')


class AbsorbanceTestCase(unittest.TestCase):
    def test_single_well(self):
        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.absorbance(test_plate, test_plate.well(0), "475:nanometer",
                     "test_reading")
        self.assertTrue(isinstance(p.instructions[0].wells, list))

    def test_temperature(self):
        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.absorbance(test_plate, test_plate.well(0), "475:nanometer",
                     "test_reading", temperature="30:celsius")
        self.assertEqual(p.instructions[0].temperature, "30:celsius")

    def test_incubate(self):
        from autoprotocol.util import incubate_params

        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.absorbance(test_plate, test_plate.well(0), "475:nanometer",
                     "test_reading",
                     incubate_before=incubate_params(
                                                     "10:second",
                                                     "3:millimeter",
                                                     True
                                                     )
                     )

        self.assertEqual(p.instructions[0].incubate_before["shaking"]["orbital"], True)
        self.assertEqual(p.instructions[0].incubate_before["shaking"]["amplitude"], "3:millimeter")
        self.assertEqual(p.instructions[0].incubate_before["duration"], "10:second")

        p.absorbance(test_plate, test_plate.well(0), "475:nanometer",
                     "test_reading",
                     incubate_before=incubate_params("10:second"))

        self.assertFalse("shaking" in p.instructions[1].incubate_before)
        self.assertEqual(p.instructions[1].incubate_before["duration"], "10:second")

        with self.assertRaises(ValueError):
            p.absorbance(test_plate, test_plate.well(0), "475:nanometer", "test_reading", incubate_before=incubate_params("10:second", "-3:millimeter", True))

        with self.assertRaises(ValueError):
            p.absorbance(test_plate, test_plate.well(0), "475:nanometer", "test_reading", incubate_before=incubate_params("10:second", "3:millimeter", "foo"))

        with self.assertRaises(ValueError):
            p.absorbance(test_plate, test_plate.well(0), "475:nanometer", "test_reading", incubate_before=incubate_params("-10:second", "3:millimeter", True))

        with self.assertRaises(RuntimeError):
            p.absorbance(test_plate, test_plate.well(0), "475:nanometer", "test_reading", incubate_before=incubate_params("10:second", "3:millimeter"))

        with self.assertRaises(RuntimeError):
            p.absorbance(test_plate, test_plate.well(0), "475:nanometer", "test_reading", incubate_before=incubate_params("10:second", shake_orbital=True))


class FluorescenceTestCase(unittest.TestCase):
    def test_single_well(self):
        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.fluorescence(test_plate, test_plate.well(0),
                       excitation="587:nanometer", emission="610:nanometer",
                       dataref="test_reading")
        self.assertTrue(isinstance(p.instructions[0].wells, list))

    def test_temperature(self):
        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.fluorescence(test_plate, test_plate.well(0), excitation="587:nanometer", emission="610:nanometer", dataref="test_reading", temperature="30:celsius")
        self.assertEqual(p.instructions[0].temperature, "30:celsius")

    def test_incubate(self):
        from autoprotocol.util import incubate_params

        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.fluorescence(test_plate, test_plate.well(0),
                       excitation="587:nanometer", emission="610:nanometer",
                       dataref="test_reading",
                       incubate_before=incubate_params("10:second",
                                                       "3:millimeter",
                                                       True))

        self.assertEqual(p.instructions[0].incubate_before["shaking"]["orbital"], True)
        self.assertEqual(p.instructions[0].incubate_before["shaking"]["amplitude"], "3:millimeter")
        self.assertEqual(p.instructions[0].incubate_before["duration"], "10:second")

        p.fluorescence(test_plate, test_plate.well(0),
                       excitation="587:nanometer", emission="610:nanometer",
                       dataref="test_reading",
                       incubate_before=incubate_params("10:second"))

        self.assertFalse("shaking" in p.instructions[1].incubate_before)
        self.assertEqual(p.instructions[1].incubate_before["duration"], "10:second")

        with self.assertRaises(ValueError):
            p.fluorescence(test_plate, test_plate.well(0), excitation="587:nanometer", emission="610:nanometer", dataref="test_reading", incubate_before=incubate_params("10:second", "-3:millimeter", True))

        with self.assertRaises(ValueError):
            p.fluorescence(test_plate, test_plate.well(0), excitation="587:nanometer", emission="610:nanometer", dataref="test_reading", incubate_before=incubate_params("10:second", "3:millimeter", "foo"))

        with self.assertRaises(ValueError):
            p.fluorescence(test_plate, test_plate.well(0), excitation="587:nanometer", emission="610:nanometer", dataref="test_reading", incubate_before=incubate_params("-10:second", "3:millimeter", True))

        with self.assertRaises(RuntimeError):
            p.fluorescence(test_plate, test_plate.well(0), excitation="587:nanometer", emission="610:nanometer", dataref="test_reading", incubate_before=incubate_params("10:second", "3:millimeter"))

        with self.assertRaises(RuntimeError):
            p.fluorescence(test_plate, test_plate.well(0), excitation="587:nanometer", emission="610:nanometer", dataref="test_reading", incubate_before=incubate_params("10:second", shake_orbital=True))


class LuminescenceTestCase(unittest.TestCase):
    def test_single_well(self):
        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.luminescence(test_plate, test_plate.well(0), "test_reading")
        self.assertTrue(isinstance(p.instructions[0].wells, list))

    def test_temperature(self):
        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.luminescence(test_plate, test_plate.well(0), "test_reading", temperature="30:celsius")
        self.assertEqual(p.instructions[0].temperature, "30:celsius")

    def test_incubate(self):
        from autoprotocol.util import incubate_params

        p = Protocol()
        test_plate = p.ref("test", None, "96-flat", discard=True)
        p.luminescence(test_plate, test_plate.well(0), "test_reading",
                       incubate_before=incubate_params("10:second",
                                                       "3:millimeter",
                                                       True))

        self.assertEqual(p.instructions[0].incubate_before["shaking"]["orbital"], True)
        self.assertEqual(p.instructions[0].incubate_before["shaking"]["amplitude"], "3:millimeter")
        self.assertEqual(p.instructions[0].incubate_before["duration"], "10:second")

        p.luminescence(test_plate, test_plate.well(0), "test_reading",
                       incubate_before=incubate_params("10:second"))

        self.assertFalse("shaking" in p.instructions[1].incubate_before)
        self.assertEqual(p.instructions[1].incubate_before["duration"], "10:second")

        with self.assertRaises(ValueError):
            p.luminescence(test_plate, test_plate.well(0), "test_reading", incubate_before=incubate_params("10:second", "-3:millimeter", True))

        with self.assertRaises(ValueError):
            p.luminescence(test_plate, test_plate.well(0), "test_reading", incubate_before=incubate_params("10:second", "3:millimeter", "foo"))

        with self.assertRaises(ValueError):
            p.luminescence(test_plate, test_plate.well(0), "test_reading", incubate_before=incubate_params("-10:second", "3:millimeter", True))

        with self.assertRaises(RuntimeError):
            p.luminescence(test_plate, test_plate.well(0), "test_reading", incubate_before=incubate_params("10:second", "3:millimeter"))

        with self.assertRaises(RuntimeError):
            p.luminescence(test_plate, test_plate.well(0), "test_reading", incubate_before=incubate_params("10:second", shake_orbital=True))


class AcousticTransferTestCase(unittest.TestCase):
    def test_append(self):
        p = Protocol()
        echo = p.ref("echo", None, "384-echo", discard=True)
        dest = p.ref("dest", None, "384-flat", discard=True)
        dest2 = p.ref("dest2", None, "384-flat", discard=True)
        p.acoustic_transfer(echo.well(0), dest.wells(1,3,5), "25:microliter")
        self.assertTrue(len(p.instructions) == 1)
        p.acoustic_transfer(echo.well(0), dest.wells(0,2,4), "25:microliter")
        self.assertTrue(len(p.instructions) == 1)
        p.acoustic_transfer(echo.well(0), dest.wells(0,2,4), "25:microliter",
                            droplet_size="0.50:microliter")
        self.assertTrue(len(p.instructions) == 2)
        p.acoustic_transfer(echo.well(0), dest2.wells(0,2,4), "25:microliter")
        self.assertTrue(len(p.instructions) == 3)

    def test_one_source(self):
        p = Protocol()
        echo = p.ref("echo", None, "384-echo", discard=True)
        dest = p.ref("dest", None, "384-flat", discard=True)
        p.acoustic_transfer(echo.wells(0,1).set_volume("2:microliter"),
                            dest.wells(0,1,2,3), "1:microliter", one_source=True)
        self.assertTrue(p.instructions[-1].data["groups"][0]["transfer"][-1]["from"] == echo.well(1))
        self.assertTrue(p.instructions[-1].data["groups"][0]["transfer"][0]["from"] == echo.well(0))

class MagneticTransferTestCase(unittest.TestCase):

    def test_head_type(self):
        p = Protocol()
        pcr = p.ref("pcr", None, "96-pcr", discard=True)

        with self.assertRaises(ValueError):
                p.mag_dry("96-flat", pcr, "30:minute", new_tip=False, new_instruction=False)
        p.mag_dry("96-pcr", pcr, "30:minute", new_tip=False, new_instruction=False)
        self.assertEqual(len(p.instructions), 1)

    def test_head_compatibility(self):
        p = Protocol()

        pcrs = [p.ref("pcr_%s" % cont_type, None, cont_type, discard=True) for cont_type in ["96-pcr", "96-v-kf", "96-flat", "96-flat-uv"]]
        deeps = [p.ref("deep_%s" % cont_type, None, cont_type, discard=True) for cont_type in ["96-v-kf", "96-deep-kf", "96-deep"]]

        for i, pcr in enumerate(pcrs):
            p.mag_dry("96-pcr", pcr, "30:minute", new_tip=False, new_instruction=False)
            self.assertEqual(len(p.instructions[-1].groups[0]), i+1)

        for i, deep in enumerate(deeps):
            if i == 0:
                n_i = True
            else:
                n_i = False
            p.mag_dry("96-deep", deep, "30:minute", new_tip=False, new_instruction=n_i)
            self.assertEqual(len(p.instructions[-1].groups[0]), i+1)

        bad_pcrs = [p.ref("bad_pcr_%s" % cont_type, None, cont_type, discard=True) for cont_type in ["96-pcr"]]
        bad_deeps = [p.ref("bad_deep_%s" % cont_type, None, cont_type, discard=True) for cont_type in ["96-deep-kf", "96-deep"]]

        for pcr in bad_pcrs:
            with self.assertRaises(ValueError):
                p.mag_dry("96-deep", pcr, "30:minute", new_tip=False, new_instruction=False)

        for deep in bad_deeps:
            with self.assertRaises(ValueError):
                p.mag_dry("96-pcr", deep, "30:minute", new_tip=False, new_instruction=False)

    def test_temperature_valid(self):
        p = Protocol()

        pcr = p.ref("pcr", None, "96-pcr", discard=True)

        for i in range(27, 96):
            p.mag_incubate("96-pcr", pcr, "30:minute", temperature="%s:celsius" % i)
            self.assertEqual(len(p.instructions[-1].groups[0]), i-26)

        for i in range(-300, -290):
            with self.assertRaises(ValueError):
                p.mag_incubate("96-pcr", pcr, "30:minute", temperature="%s:celsius" % i)

    def test_frequency_valid(self):
        p = Protocol()

        pcr = p.ref("pcr", None, "96-pcr", discard=True)

        for i in range(27, 96):
            p.mag_mix("96-pcr", pcr, "30:second", "%s:hertz" % i, center=1, amplitude=0)
            self.assertEqual(len(p.instructions[-1].groups[0]), i-26)

        for i in range(-10, -5):
            with self.assertRaises(ValueError):
                p.mag_mix("96-pcr", pcr, "30:second", "%s:hertz" % i, center=1, amplitude=0)

    def test_magnetize_valid(self):
        p = Protocol()

        pcr = p.ref("pcr", None, "96-pcr", discard=True)

        p.mag_mix("96-pcr", pcr, "30:second", "60:hertz", center=1, amplitude=0, magnetize=True)
        self.assertEqual(len(p.instructions[-1].groups[0]), 1)

        p.mag_mix("96-pcr", pcr, "30:second", "60:hertz", center=1, amplitude=0, magnetize=False)
        self.assertEqual(len(p.instructions[-1].groups[0]), 2)

        with self.assertRaises(ValueError):
            p.mag_mix("96-pcr", pcr, "30:second", "60:hertz", center=1, amplitude=0, magnetize="Foo")

    def test_center_valid(self):
        p = Protocol()

        pcr = p.ref("pcr", None, "96-pcr", discard=True)

        for i in range(0, 200):
            p.mag_mix("96-pcr", pcr, "30:second", "60:hertz", center=float(i)/100, amplitude=0)
            self.assertEqual(len(p.instructions[-1].groups[0]), i*4+1)
            p.mag_collect("96-pcr", pcr, 5, "30:second", bottom_position=float(i)/100)
            self.assertEqual(len(p.instructions[-1].groups[0]), i*4+2)
            p.mag_incubate("96-pcr", pcr, "30:minute", tip_position=float(i)/100)
            self.assertEqual(len(p.instructions[-1].groups[0]), i*4+3)
            p.mag_release("96-pcr", pcr, "30:second", "1:hertz", center=float(i)/100, amplitude=0)
            self.assertEqual(len(p.instructions[-1].groups[0]), i*4+4)

        for i in range(-1, 3, 4):
            with self.assertRaises(ValueError):
                p.mag_mix("96-pcr", pcr, "30:second", "60:hertz", center=i, amplitude=0)
            with self.assertRaises(ValueError):
                p.mag_collect("96-pcr", pcr, 5, "30:second", bottom_position=i)
            with self.assertRaises(ValueError):
                p.mag_incubate("96-pcr", pcr, "30:minute", tip_position=i)
            with self.assertRaises(ValueError):
                p.mag_release("96-pcr", pcr, "30:second", "1:hertz", center=i, amplitude=0)

    def test_amplitude_valid(self):
        p = Protocol()

        pcr = p.ref("pcr", None, "96-pcr", discard=True)

        for i in range(0, 100):
            p.mag_mix("96-pcr", pcr, "30:second", "60:hertz", center=1, amplitude=float(i)/100)
            self.assertEqual(len(p.instructions[-1].groups[0]), i*2+1)
            p.mag_release("96-pcr", pcr, "30:second", "1:hertz", center=1, amplitude=float(i)/100)
            self.assertEqual(len(p.instructions[-1].groups[0]), i*2+2)

        for i in range(-1, 2, 3):
            with self.assertRaises(ValueError):
                p.mag_mix("96-pcr", pcr, "30:second", "60:hertz", center=1, amplitude=i)
            with self.assertRaises(ValueError):
                p.mag_release("96-pcr", pcr, "30:second", "1:hertz", center=1, amplitude=i)

    def test_mag_append(self):
        p = Protocol()

        pcrs = [p.ref("pcr_%s" % i, None, "96-pcr", storage="cold_20") for i in range(7)]

        pcr = pcrs[0]

        p.mag_dry("96-pcr", pcr, "30:minute", new_tip=False, new_instruction=False)
        self.assertEqual(len(p.instructions[-1].groups[0]), 1)
        self.assertEqual(len(p.instructions[-1].groups), 1)

        p.mag_dry("96-pcr", pcr, "30:minute", new_tip=True, new_instruction=False)
        self.assertEqual(len(p.instructions[-1].groups), 2)
        self.assertEqual(len(p.instructions), 1)

        p.mag_dry("96-pcr", pcr, "30:minute", new_tip=True, new_instruction=True)
        self.assertEqual(len(p.instructions), 2)

        for plate in pcrs:
            p.mag_dry("96-pcr", plate, "30:minute", new_tip=False, new_instruction=False)
            self.assertEqual(len(p.instructions), 2)

        with self.assertRaises(RuntimeError):
            pcr_too_many = p.ref("pcr_7", None, "96-pcr", discard=True)
            p.mag_dry("96-pcr", pcr_too_many, "30:minute", new_tip=False, new_instruction=False)

        p.mag_dry("96-pcr", pcr, "30:minute", new_tip=True, new_instruction=True)
        self.assertEqual(len(p.instructions), 3)

        p.mag_dry("96-pcr", pcr, "30:minute", new_tip=True, new_instruction=False)
        self.assertEqual(len(p.instructions[-1].groups), 2)

        with self.assertRaises(RuntimeError):
            for plate in pcrs:
                p.mag_dry("96-pcr", plate, "30:minute", new_tip=False, new_instruction=False)


class AutopickTestCase(unittest.TestCase):

    def test_autopick(self):
        p = Protocol()
        dest_plate = p.ref("dest", None, "96-flat", discard=True)

        p.refs["agar_plate"] = Ref("agar_plate", {"reserve": "ki17reefwqq3sq", "discard": True}, Container(None, p.container_type("6-flat"), name="agar_plate"))

        agar_plate = Container(None, p.container_type("6-flat"), name="agar_plate")

        p.refs["agar_plate_1"] = Ref("agar_plate_1", {"reserve": "ki17reefwqq3sq", "discard": True}, Container(None, p.container_type("6-flat"), name="agar_plate_1"))

        agar_plate_1 = Container(None, p.container_type("6-flat"), name="agar_plate_1")

        p.autopick([agar_plate.well(0), agar_plate.well(1)], [dest_plate.well(1)]*4, min_abort=0, dataref="0", newpick=False)

        self.assertEqual(len(p.instructions), 1)
        self.assertEqual(len(p.instructions[0].groups), 1)
        self.assertEqual(len(p.instructions[0].groups[0]["from"]), 2)

        p.autopick([agar_plate.well(0), agar_plate.well(1)], [dest_plate.well(1)]*4, min_abort=0, dataref="1", newpick=True)

        self.assertEqual(len(p.instructions), 2)

        p.autopick([agar_plate.well(0), agar_plate.well(1)], [dest_plate.well(1)]*4, min_abort=0, dataref="1", newpick=False)

        self.assertEqual(len(p.instructions), 2)

        for i in range(20):
            p.autopick([agar_plate.well(i % 6), agar_plate.well((i+1) % 6)], [dest_plate.well(i % 96)]*4, min_abort=i, dataref="1", newpick=False)

        self.assertEqual(len(p.instructions), 2)

        p.autopick([agar_plate_1.well(0), agar_plate_1.well(1)], [dest_plate.well(1)]*4, min_abort=0, dataref="1", newpick=False)

        self.assertEqual(len(p.instructions), 3)

        p.autopick([agar_plate_1.well(0), agar_plate_1.well(1)], [dest_plate.well(1)]*4, min_abort=0, dataref="2", newpick=False)

        self.assertEqual(len(p.instructions), 4)

        with self.assertRaises(RuntimeError):
            p.autopick([agar_plate.well(0), agar_plate_1.well(1)], [dest_plate.well(1)]*4, min_abort=0, dataref="1", newpick=False)

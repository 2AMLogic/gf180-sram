#!/usr/bin/env python3
"""Write the wordline-RC gate testbench bodies and klt sim requests (issue #204).

Usage (repo root):  python3 sim/wordline-rc/gen.py

DUTs (``dut/``) are one-row slices of the committed array generator
(``layout/sram_256x32/generate.py --rows 1 --cols N``) extracted with
``klt extract --deck gf180mcu --pdk gf180mcuD --parasitics --distributed-rc
--critical-net WL0`` (exact commands in README.md):

* ``wl_row_128`` -- the ratified 4:1 row, 128 cells / 571 um, 256 access gates.
* ``wl_row_64``  -- 64 cells / 285 um (a 2:1 row, or one half of a centre-fed 4:1 row).

The extracted WL0 net is a per-segment RC chain over the access-transistor
gates. Its two end nodes are the first cell (``WL0__t0``, at the landing pad) and
the last cell. The extractor's own pin node (``WL0``) is the *129th of 256 gates*,
in the middle of the chain -- not where the pad is -- so it is left undriven and
the driver feeds the pad-end node, which the generated ``*.ported.spice`` copies
expose as an extra port (header edit only).

Topologies:

* ``row128``  -- left-fed 128-cell row (the architecture as ratified).
* ``centre``  -- one driver feeding two 64-cell halves from their pad ends
  (4:1 with a centre decoder).
* ``row64``   -- left-fed 64-cell row (2:1).

Each is run with the extracted Poly2 resistance as reported (``x1``) and with every
WL0 segment resistance x1.5 (``x1p5``); the extractor applies no process or
temperature scaling to Poly2 R. 1.5 is an assumed sensitivity, not a
PDK-characterized bound and not a corner (spec/wordline-rc-decision.md).
"""
import collections
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RSCALE = 1.5
W_FLOOR_NS = 2.0  # spec/write-pulse-width-decision.md
W_MACRO_NS = 5.88  # wr_wl_en_width at ss_125c_2.97v, sim/macro-smoke record 20261018-082301-37ba562


def read(name: str) -> str:
    with open(os.path.join(HERE, "dut", name)) as fh:
        return fh.read()


def write(rel: str, text: str) -> None:
    with open(os.path.join(HERE, rel), "w") as fh:
        fh.write(text)


def scale_r(text: str) -> str:
    out = re.sub(
        r"^(RWL0_seg\d+ \S+ \S+ )(\S+)$",
        lambda m: m.group(1) + format(float(m.group(2)) * RSCALE, ".9g"),
        text,
        flags=re.M,
    )
    assert out != text
    return out


PORT_LINE = re.compile(r"^(\+ .*\bVDD VSS WL0)$", re.M)


def prepare(dut: str) -> dict:
    """Return the DUT's subckt name, pin list and chain end nodes; write x1/x1p5 ported copies."""
    base = read(f"{dut}.extracted.spice")
    m = re.search(r"^\.subckt (\S+)((?:[ \t]+\S+|\n\+[^\n]*)*)", base, re.M | re.I)
    pins = m.group(2).replace("\n+", " ").split()
    assert pins[-3:] == ["VDD", "VSS", "WL0"] and m.group(1) == dut, (m.group(1), pins[-3:])
    deg = collections.Counter()
    for s in re.finditer(r"^RWL0_seg\d+ (\S+) (\S+) \S+$", base, re.M):
        deg[s.group(1)] += 1
        deg[s.group(2)] += 1
    ends = sorted(n for n, c in deg.items() if c == 1)
    assert len(ends) == 2 and "WL0__t0" in ends, ends
    far = next(n for n in ends if n != "WL0__t0")
    assert len(PORT_LINE.findall(base)) == 1
    for tag, text in (("x1", base), ("x1p5", scale_r(base))):
        ported = PORT_LINE.sub(rf"\1 WL0__t0 {far}", text)
        write(f"dut/{dut}.{tag}.ported.spice", ported)
    return {"pins": pins, "far": far}


def inst(label: str, dut: str, info: dict, pad: str, far: str) -> str:
    conn = ["VDD" if p.startswith("BL") else p for p in info["pins"]]  # BL/BLB precharged
    conn[conn.index("WL0")] = f"mid_{label}"  # the extractor's mid-chain pin: undriven
    return f"X{label} " + " ".join(conn) + f" {pad} {far} {dut}"


# Probes are digitised at 10/50/90 % of VDD so the literal thresholds in the .meas
# cards hold at every supply. Pulse 1 is the 2 ns floor, pulse 2 the macro's pulse.
MEAS = []
for w, tag in ((1, "p2ns"), (2, "p588")):
    # d_<sig>_<w> is the digitised probe masked to pulse w (w1: t < 10 ns, w2: t >= 10 ns),
    # so a threshold the far end never reaches in pulse w is reported as an error rather
    # than silently picked up from the other pulse.
    MEAS += [
        (f"drv_rise50_{tag}", f"trig v(d_in_{w}) val=0.5 rise=1 targ v(d_drv_{w}) val=0.5 rise=1"),
        (f"far_rise50_{tag}", f"trig v(d_in_{w}) val=0.5 rise=1 targ v(d_far_{w}) val=0.5 rise=1"),
        (f"far_width50_{tag}", f"trig v(d_far_{w}) val=0.5 rise=1 targ v(d_far_{w}) val=0.5 fall=1"),
        (f"drv_width50_{tag}", f"trig v(d_drv_{w}) val=0.5 rise=1 targ v(d_drv_{w}) val=0.5 fall=1"),
        (f"far_rise90_{tag}", f"trig v(d_in_{w}) val=0.5 rise=1 targ v(d_far90_{w}) val=0.5 rise=1"),
        (f"far_rise10_90_{tag}", f"trig v(d_far10_{w}) val=0.5 rise=1 targ v(d_far90_{w}) val=0.5 rise=1"),
        (f"far_width90_{tag}", f"trig v(d_far90_{w}) val=0.5 rise=1 targ v(d_far90_{w}) val=0.5 fall=1"),
    ]
PEAKS = [  # unit V: the highest the far end gets during each pulse
    ("far_peak_p2ns", "max v(wl_far) from=1n to=3.2n"),
    ("far_peak_p588", "max v(wl_far) from=12n to=18n"),
]


def probes() -> str:
    sigs = {
        "in": "v(IN) > v(VDD)/2",
        "drv": "v(wl_drv) > v(VDD)/2",
        "far": "v(wl_far) > v(VDD)/2",
        "far10": "v(wl_far) > 0.1*v(VDD)",
        "far90": "v(wl_far) > 0.9*v(VDD)",
    }
    lines = []
    for w, cond in ((1, "time < 10n"), (2, "time >= 10n")):
        for sig, expr in sigs.items():
            lines.append(f"Bd_{sig}_{w} d_{sig}_{w} 0 V='({expr} ? 1 : 0) * ({cond} ? 1 : 0)'")
    return "\n".join(lines)


PROBES = probes()


def body(topo: str, tag: str, label: str) -> str:
    if topo == "row128":
        insts = [inst("A", "wl_row_128", INFO["wl_row_128"], "wl_pad", "wl_far")]
        dutfiles = ["wl_row_128"]
    elif topo == "row64":
        insts = [inst("A", "wl_row_64", INFO["wl_row_64"], "wl_pad", "wl_far")]
        dutfiles = ["wl_row_64"]
    else:  # centre: two halves fed from their pad ends by one driver
        insts = [
            inst("A", "wl_row_64", INFO["wl_row_64"], "wl_pad", "wl_far"),
            inst("B", "wl_row_64", INFO["wl_row_64"], "wl_pad", "wl_far_b"),
        ]
        dutfiles = ["wl_row_64"]
    includes = "\n".join(f".include '../dut/{d}.{tag}.ported.spice'" for d in dutfiles)
    return f"""* Wordline RC gate: {topo}, {label} -- klt sim circuit BODY (issue #204;
* spec/periphery-architecture.md "Wordline RC gate"). A real `rowdrv`
* (design/netlist/rowdrv.spice, W=6u/3u output stage) drives the extracted wordline from
* its landing-pad end. Pulse 1 is the {W_FLOOR_NS} ns write-pulse floor of
* spec/write-pulse-width-decision.md; pulse 2 is {W_MACRO_NS} ns, the wl_en width the
* control block makes at ss_125c_2.97v (sim/macro-smoke record 20261018-082301-37ba562).
* Both rowdrv inputs get the pulse with 0.1 ns edges (an ideal stand-in for predecode).
.include '../../../design/netlist/rowdrv.spice'
{includes}
.options rshunt=1e12

* PDK default params normally supplied by design.ngspice (via corner.inc)
.param sw_stat_global=0
.param sw_stat_mismatch=0
.param mc_skew=3
.param res_mc_skew=3
.param cap_mc_skew=3
.param fnoicor=0

VVDD VDD 0 DC 3.3
V1IN in1 0 PWL(0 0 1n 0 1.1n 1 3n 1 3.1n 0 12n 0 12.1n 1 17.88n 1 17.98n 0 30n 0)
BIN IN 0 V='v(VDD)*v(in1)'
XDRV IN IN wl_drv VDD 0 rowdrv
Rpad wl_drv wl_pad 1m
{chr(10).join(insts)}

* digitised probes (1 when above 10 / 50 / 90 % of VDD), one set per pulse window
{PROBES}"""


def request(tb: str, with_90: bool) -> dict:
    meas = [{"name": n, "spice": f".meas tran {n} {s}", "unit": "s"}
            for n, s in MEAS if with_90 or "p588" not in n or "90" not in n]
    meas += [{"name": n, "spice": f".meas tran {n} {s}", "unit": "V"} for n, s in PEAKS]
    return {
        "netlist": f"../testbench/{tb}",
        "engine": "ngspice",
        "models": {"lib": "$PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": "ss", "sections": ["ss"]}],
            "supply_v": {"vvdd": [2.97]},
            "temperature_c": [125],
        },
        "analysis": {"kind": "tran", "args": "0.005n 30n"},
        "measurements": meas,
        "netlist_source": "schematic",
        "options": {"timeout_s": 900},
    }


INFO = {d: prepare(d) for d in ("wl_row_128", "wl_row_64")}
for topo in ("row128", "centre", "row64"):
    for tag, label in (("x1", "extracted Poly2 R"), ("x1p5", f"extracted Poly2 R x{RSCALE}")):
        name = f"{topo}_{tag}"
        write(f"testbench/tb_wl_rc_{name}.klt.spice", body(topo, tag, label))
        with open(os.path.join(HERE, "requests", f"wl_rc_{name}.json"), "w") as fh:
            # the 90 % measurements are errors when the far end never gets there, so
            # they stay in the request and report `error` for that measurement honestly
            json.dump(request(f"tb_wl_rc_{name}.klt.spice", True), fh, indent=2)
            fh.write("\n")
print("wrote testbench bodies and requests")

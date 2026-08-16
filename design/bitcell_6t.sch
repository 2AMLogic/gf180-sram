v {xschem version=3.4.7 file_version=1.2
* bitcell_6t -- 6T SRAM storage cell (issue #21, T1 item 1)
*
* Standard 6T topology: two cross-coupled CMOS inverters (MPL/MNL storing Q,
* MPR/MNR storing QB) plus two NMOS access transistors (MAL, MAR) gated by a
* shared wordline, connecting the storage nodes to a differential bitline
* pair. This is the textbook 6T cell topology -- see e.g. OpenRAM's
* sky130 sram_sp_cell (github.com/VLSIDA/OpenRAM) for the same architecture
* on a different PDK, cited per CLAUDE.md as a reference/comparison, not
* reimplemented from its source.
*
* Devices: gf180mcu 3.3V core devices (nfet_03v3 / pfet_03v3), matching
* spec/sram.md's single 3.3V supply target and this org's other gf180mcu
* canary blocks' device choice for the 3.3V domain.
*
* Sizing (first-cut, not yet SNM/write-margin optimized -- that
* characterization is spec/sram.md's Characterization section, tracked by a
* separate downstream issue, not this one):
*   MPL/MPR (pull-up,   pfet_03v3): W=0.22u L=0.28u  (minimum width: wmin
*                                    for pfet_03v3 is 2.2e-7 m per
*                                    libs.tech/ngspice/sm141064.ngspice)
*   MNL/MNR (pull-down, nfet_03v3): W=0.36u L=0.28u
*   MAL/MAR (access,    nfet_03v3): W=0.24u L=0.28u
* Cell ratio  (pull-down/access) = 0.36/0.24 = 1.50  (>1: read stability)
* Pull-up ratio (access/pull-up) = 0.24/0.22 = 1.09  (>1: writability)
* L is drawn at nfet_03v3/pfet_03v3's minimum (0.28u, both devices' model
* default) for cell density.
*
* NOTE on the reference bitcell: spec/bitcell-decision.md cites gf180mcu's
* own foundry-hardened SRAM IP (gf180mcu_fd_ip_sram) bitcell subcircuit
* "018SRAM_cell1" as the topology reference. Its SPICE body is a
* *.SEEDPROM black box in the shipped deck (libs.ref/gf180mcu_fd_ip_sram/
* spice/gf180mcu_fd_ip_sram__sram64x8m8wm1.spice, ".SUBCKT 018SRAM_cell1" /
* "** N=8 ..." / "*.SEEDPROM" / ".ENDS", no device lines) -- the foundry
* does not disclose that macro's actual transistor sizing, only that it is
* an 8-device (N=8) 6T-family cell. There is therefore no real sizing to
* cite or reproduce from that source, consistent with
* spec/bitcell-decision.md's own instruction to use it as a topology
* reference, "not reimplement its exact topology verbatim" -- the sizing
* above is this repo's own first-cut, independent of that undisclosed data.
*
* Ports: BL, BLB (differential bitline pair), WL (wordline), VDD, VSS.
* This is the storage-cell level of the hierarchy only -- address decode,
* column mux, sense amp and write driver (the rest of a 1RW macro's port
* list per spec/sram.md) are periphery, out of this issue's scope; see
* design/README.md.
}
G {}
K {}
V {}
S {}
E {}
* --- pull-up pair: MPL (D=Q top slot, S=VDD bottom slot), MPR mirrored ---
C {symbols/pfet_03v3.sym} 0 600 0 0 {name=MPL model=pfet_03v3 W=0.22u L=0.28u nf=1 m=1}
N 20 630 20 650 {}
C {lab_pin.sym} 20 650 0 0 {name=l1 lab=Q}
N 20 570 20 550 {}
C {lab_pin.sym} 20 550 0 0 {name=l2 lab=VDD}
N -20 600 -40 600 {}
C {lab_pin.sym} -40 600 0 0 {name=l3 lab=QB}
N 20 600 40 600 {}
C {lab_pin.sym} 40 600 0 0 {name=l4 lab=VDD}

C {symbols/pfet_03v3.sym} 600 600 0 0 {name=MPR model=pfet_03v3 W=0.22u L=0.28u nf=1 m=1}
N 620 630 620 650 {}
C {lab_pin.sym} 620 650 0 0 {name=l5 lab=QB}
N 620 570 620 550 {}
C {lab_pin.sym} 620 550 0 0 {name=l6 lab=VDD}
N 580 600 560 600 {}
C {lab_pin.sym} 560 600 0 0 {name=l7 lab=Q}
N 620 600 640 600 {}
C {lab_pin.sym} 640 600 0 0 {name=l8 lab=VDD}

* --- pull-down pair: MNL (S=VSS top slot, D=Q bottom slot), MNR mirrored ---
C {symbols/nfet_03v3.sym} 0 300 0 0 {name=MNL model=nfet_03v3 W=0.36u L=0.28u nf=1 m=1}
N 20 330 20 350 {}
C {lab_pin.sym} 20 350 0 0 {name=l9 lab=VSS}
N 20 270 20 250 {}
C {lab_pin.sym} 20 250 0 0 {name=l10 lab=Q}
N -20 300 -40 300 {}
C {lab_pin.sym} -40 300 0 0 {name=l11 lab=QB}
N 20 300 40 300 {}
C {lab_pin.sym} 40 300 0 0 {name=l12 lab=VSS}

C {symbols/nfet_03v3.sym} 600 300 0 0 {name=MNR model=nfet_03v3 W=0.36u L=0.28u nf=1 m=1}
N 620 330 620 350 {}
C {lab_pin.sym} 620 350 0 0 {name=l13 lab=VSS}
N 620 270 620 250 {}
C {lab_pin.sym} 620 250 0 0 {name=l14 lab=QB}
N 580 300 560 300 {}
C {lab_pin.sym} 560 300 0 0 {name=l15 lab=Q}
N 620 300 640 300 {}
C {lab_pin.sym} 640 300 0 0 {name=l16 lab=VSS}

* --- access pair: MAL (S=Q top slot, D=BL bottom slot), MAR mirrored ---
C {symbols/nfet_03v3.sym} 0 0 0 0 {name=MAL model=nfet_03v3 W=0.24u L=0.28u nf=1 m=1}
N 20 30 20 50 {}
C {lab_pin.sym} 20 50 0 0 {name=l17 lab=Q}
N 20 -30 20 -50 {}
C {lab_pin.sym} 20 -50 0 0 {name=l18 lab=BL}
N -20 0 -40 0 {}
C {lab_pin.sym} -40 0 0 0 {name=l19 lab=WL}
N 20 0 40 0 {}
C {lab_pin.sym} 40 0 0 0 {name=l20 lab=VSS}

C {symbols/nfet_03v3.sym} 600 0 0 0 {name=MAR model=nfet_03v3 W=0.24u L=0.28u nf=1 m=1}
N 620 30 620 50 {}
C {lab_pin.sym} 620 50 0 0 {name=l21 lab=QB}
N 620 -30 620 -50 {}
C {lab_pin.sym} 620 -50 0 0 {name=l22 lab=BLB}
N 580 0 560 0 {}
C {lab_pin.sym} 560 0 0 0 {name=l23 lab=WL}
N 620 0 640 0 {}
C {lab_pin.sym} 640 0 0 0 {name=l24 lab=VSS}

* --- top-level ports ---
C {iopin.sym} -200 -50 0 0 {name=p1 lab=BL}
C {iopin.sym} 800 -50 0 0 {name=p2 lab=BLB}
C {ipin.sym} -200 0 0 0 {name=p3 lab=WL}
C {iopin.sym} -200 700 0 0 {name=p4 lab=VDD}
C {iopin.sym} -200 -150 0 0 {name=p5 lab=VSS}

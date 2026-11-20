// sram_256x32 -- behavioural (functional-only) Verilog model of the
// 256 x 32 1RW SRAM macro (issue #468).
//
// Provenance: written from spec/macro-interface-decision.md (resolves #198)
// "Decisions" rows 1-9 and "Behavior the record fixes", plus the consumer
// interface note there. NOT transcribed from the foundry
// gf180mcu_fd_ip_sram Verilog model -- this repo's stance on the foundry IP
// is comparison, not copy (spec/sram.md "Deliverables"; the model here was
// compared against that record, and the record itself was derived from the
// foundry model at 256 x 8).
//
//   row 1-3, 9   A[7:0], D[31:0], Q[31:0], descending [N-1:0] bit order
//   row 4, 7     WEN[31:0] per-bit active-low write mask: WEN[i]=0 writes
//                D[i] into bit i; WEN[i]=1 leaves bit i unchanged; WEN all
//                ones with GWEN=0 is a no-op write
//   row 5         CEN active low
//   row 6         GWEN active-low write (GWEN=1 is a read)
//   row 8         1-cycle registered read: address sampled at a rising CLK
//                edge, Q valid after that same edge, held until the next
//                read; a write never drives Q (no write-through)
//   "Q across    Q is undefined (X) before the first read and holds the
//    writes"      last read value across writes and idle cycles
//   "CEN at      the macro is not operational until CEN has been sampled
//    reset"       high once at a rising CLK edge (the consumer-side
//                 "hold CEN=1 during reset, then assert" rule, modelled
//                 the same way the record states it)
//
// Port order follows the committed top .subckt in
// design/netlist/sram_256x32.spice (A[7:0] CEN GWEN CLK D[31:0] WEN[31:0]
// Q[31:0] VDD VSS); design/check_macro_pins.py checks the two agree.
//
// Scope: functional only, NO timing -- no specify block, no delays, no
// setup/hold checks. Not evidence for any spec row and not a substitute for
// the Liberty view of #200. Run the bench: ./views/check_model.sh.

`timescale 1ns/1ps

module sram_256x32 (
    input  wire [7:0]  A,
    input  wire        CEN,
    input  wire        GWEN,
    input  wire        CLK,
    input  wire [31:0] D,
    input  wire [31:0] WEN,
    output reg  [31:0] Q,
    inout  wire        VDD,
    inout  wire        VSS
);

    reg [31:0] mem [0:255];

    // "CEN at reset": not operational until CEN has been sampled high once.
    reg cen_armed = 1'b0;

    // "Q is undefined before the first read" -- explicit, though an
    // unassigned reg would read as X anyway.
    initial Q = {32{1'bx}};

    always @(posedge CLK) begin
        if (CEN)
            cen_armed <= 1'b1;
        if (!CEN && cen_armed) begin
            if (!GWEN) begin
                // per-bit active-low mask (rows 4, 7); with WEN all ones
                // this assigns the word its own value -- the no-op write
                mem[A] <= (D & ~WEN) | (mem[A] & WEN);
            end else begin
                // 1-cycle registered read (row 8); Q keeps this value
                // across later writes and idle cycles (no write-through)
                Q <= mem[A];
            end
        end
    end

endmodule

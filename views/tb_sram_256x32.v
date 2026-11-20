// tb_sram_256x32 -- self-checking bench for views/sram_256x32.v (issue #468).
//
// Covers, in order:
//   * the "CEN at reset" rule: a write issued before CEN has been sampled
//     high once is a no-op (verified in phase 5 by reading the cell back
//     as all-X after real traffic has flowed);
//   * the sim/macro-smoke/smoke.py OPS table replayed verbatim (ten cycles,
//     seven expected Q words) -- agreement on that vector set only, not an
//     equivalence claim against the SPICE macro;
//   * Q all-X through the two writes before the first read (no
//     write-through, Q undefined before the first read);
//   * a within-byte per-bit mask (bits 8 and 1 of byte 0 written, the rest
//     of the byte masked) -- a per-byte-mask fault the OPS table's
//     halfword mask cannot catch;
//   * WEN all ones with GWEN = 0 as a no-op write (state unchanged, Q
//     holds the last read value);
//   * read-hold across writes, masked writes, CEN-deselect cycles.
//
// Self-verdict for `klt functional-verification` (verilog_top bench):
// prints "TB-RESULT: FAIL" on any mismatch and "TB-RESULT: PASS" exactly
// once, after the last check. Run it with ./views/check_model.sh -- no PDK
// needed. T = 20 ns is the smoke deck's CLK period for readability only;
// a functional model asserts nothing about timing.

`timescale 1ns/1ps

module tb_sram_256x32;

    localparam integer T = 20;           // ns, smoke.py's PERIOD
    localparam [31:0] M32 = 32'hFFFFFFFF;

    reg         CLK = 1'b0;
    reg         CEN = 1'b0;              // start disarmed, to test the CEN-at-reset rule
    reg         GWEN = 1'b1;
    reg  [7:0]  A = 8'h00;
    reg  [31:0] D = 32'h00000000;
    reg  [31:0] WEN = M32;               // safe default: nothing writable
    wire [31:0] Q;
    wire        VDD = 1'b1;
    wire        VSS = 1'b0;

    integer errors = 0;

    sram_256x32 dut (
        .A(A), .CEN(CEN), .GWEN(GWEN), .CLK(CLK),
        .D(D), .WEN(WEN), .Q(Q), .VDD(VDD), .VSS(VSS)
    );

    always #(T/2) CLK = ~CLK;

    task check(input [8*48-1:0] label, input [31:0] got, input [31:0] exp);
        begin
            if (got !== exp) begin
                errors = errors + 1;
                $display("  FAIL %0s: Q=%h expected %h", label, got, exp);
            end else begin
                $display("  ok   %0s: Q=%h", label, got);
            end
        end
    endtask

    task check_x(input [8*48-1:0] label, input [31:0] val);
        begin
            if (val !== {32{1'bx}}) begin
                errors = errors + 1;
                $display("  FAIL %0s: Q=%h expected all-X", label, val);
            end else begin
                $display("  ok   %0s: Q is all-X", label);
            end
        end
    endtask

    // Drive one op half a period before a rising edge, return half a
    // period after it, once the edge's Q update has landed.
    task op(input cen, input gwen, input [7:0] a, input [31:0] d, input [31:0] wen);
        begin
            @(negedge CLK);
            CEN = cen; GWEN = gwen; A = a; D = d; WEN = wen;
            @(negedge CLK);
        end
    endtask

    initial begin
        $display("phase 1: CEN-at-reset -- a write before CEN is sampled high is a no-op");
        // (posedge #1 samples the safe initial inputs, CEN=0, disarmed: nothing happens)
        op(1'b0, 1'b0, 8'h55, 32'hBAD0BAD0, 32'h00000000);
        check_x("Q all-X after the disarmed write", Q);

        $display("phase 2: sim/macro-smoke/smoke.py OPS replay (10 cycles, 7 Q words)");
        op(1'b1, 1'b1, 8'h00, 32'h00000000, M32);                 // idle-init
        check_x("Q all-X after idle-init", Q);
        op(1'b0, 1'b0, 8'hA7, 32'hDEADBEEF, 32'h00000000);        // write A7
        check_x("Q all-X after write A7 (no write-through)", Q);
        op(1'b0, 1'b0, 8'h3C, 32'h12345678, 32'h00000000);        // write 3C
        check_x("Q all-X after write 3C", Q);
        op(1'b0, 1'b1, 8'hA7, 32'h00000000, M32);                 // read A7
        check("OPS 3 read A7", Q, 32'hDEADBEEF);
        op(1'b0, 1'b1, 8'h3C, 32'h00000000, M32);                 // read 3C
        check("OPS 4 read 3C", Q, 32'h12345678);
        op(1'b0, 1'b0, 8'hA7, 32'hFFFFFFFF, 32'h0000FFFF);        // masked write A7
        check("OPS 5 Q holds 3C across the masked write", Q, 32'h12345678);
        op(1'b0, 1'b1, 8'hA7, 32'h00000000, M32);                 // read A7 after mask
        check("OPS 6 read A7 = FFFFBEEF", Q, 32'hFFFFBEEF);
        op(1'b0, 1'b1, 8'h3C, 32'h00000000, M32);                 // read 3C neighbour
        check("OPS 7 read 3C", Q, 32'h12345678);
        op(1'b1, 1'b0, 8'hA7, 32'h00000000, 32'h00000000);        // idle: no write, Q holds
        check("OPS 8 Q holds across the CEN=1 cycle", Q, 32'h12345678);
        op(1'b0, 1'b1, 8'hA7, 32'h00000000, M32);                 // read A7 after idle
        check("OPS 9 read A7 = FFFFBEEF", Q, 32'hFFFFBEEF);

        $display("phase 3: within-byte per-bit mask (bits 8 and 1 of byte 0)");
        op(1'b0, 1'b0, 8'h11, 32'h00000000, 32'h00000000);        // clear cell 0x11
        check("Q holds across the clear write", Q, 32'hFFFFBEEF);
        op(1'b0, 1'b0, 8'h11, 32'hFFFFFFFF, 32'hFFFFFEFE);        // write only bits 8, 1
        op(1'b0, 1'b1, 8'h11, 32'h00000000, M32);
        check("masked write landed bits 8,1 only", Q, 32'h00000101);

        $display("phase 4: WEN all ones with GWEN=0 is a no-op write");
        op(1'b0, 1'b0, 8'h22, 32'hCAFEBABE, 32'h00000000);
        op(1'b0, 1'b1, 8'h22, 32'h00000000, M32);
        check("read 0x22 before the no-op", Q, 32'hCAFEBABE);
        op(1'b0, 1'b0, 8'h22, 32'h600DF00D, M32);                 // the no-op "write"
        check("Q holds across the no-op write", Q, 32'hCAFEBABE);
        op(1'b0, 1'b1, 8'h22, 32'h00000000, M32);
        check("cell 0x22 unchanged by the no-op", Q, 32'hCAFEBABE);

        $display("phase 5: the phase-1 disarmed write never landed");
        op(1'b0, 1'b1, 8'h55, 32'h00000000, M32);
        check_x("cell 0x55 reads all-X", Q);

        if (errors == 0) begin
            $display("TB-RESULT: PASS (all sram_256x32 model checks)");
            $finish;
        end else begin
            $display("TB-RESULT: FAIL (%0d check error(s))", errors);
            $finish;
        end
    end

endmodule

// tb_sram_256x32 -- self-checking bench for views/sram_256x32.v (issue #468).
//
// Covers, in order:
//   * CEN held high with the clock stopped during reset, then asserted
//     before the first rising edge for a write, followed by a read;
//   * the sim/macro-smoke/smoke.py OPS table replayed verbatim (ten cycles,
//     seven expected Q words) -- agreement on that vector set only, not an
//     equivalence claim against the SPICE macro;
//   * Q all-X through the two writes before the first read (no
//     write-through, Q undefined before the first read);
//   * a mask enabling bits 0 and 8 only (one bit in each low byte),
//     which detects byte-wide writes that the OPS halfword mask allows;
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
    reg         CEN = 1'b1;
    reg         GWEN = 1'b1;
    reg  [7:0]  A = 8'h00;
    reg  [31:0] D = 32'h00000000;
    reg  [31:0] WEN = M32;               // safe default: nothing writable
    wire [31:0] Q;
    wire        VDD = 1'b1;
    wire        VSS = 1'b0;

    integer errors = 0;
    time smoke_start;

    // A separate instance keeps the smoke replay's Q at its power-up value.
    reg         startup_cen = 1'b1;
    reg         startup_gwen = 1'b0;
    wire [31:0] startup_q;

    sram_256x32 startup_dut (
        .A(8'h55), .CEN(startup_cen), .GWEN(startup_gwen), .CLK(CLK),
        .D(32'hDEADBEEF), .WEN(32'h0), .Q(startup_q), .VDD(VDD), .VSS(VSS)
    );

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

    // Called with CLK low. Drive the next rising edge and return on the
    // following falling edge, after the registered Q update.
    task op(input cen, input gwen, input [7:0] a, input [31:0] d, input [31:0] wen);
        begin
            CEN = cen; GWEN = gwen; A = a; D = d; WEN = wen;
            @(negedge CLK);
        end
    endtask

    initial begin
        $display("phase 1: first-edge write after CEN high during reset");
        #(T/4);
        check_x("startup Q all-X before first edge", startup_q);
        startup_cen = 1'b0;
        @(negedge CLK);
        check_x("startup Q all-X after first-edge write", startup_q);
        startup_gwen = 1'b1;
        @(negedge CLK);
        check("read back first-edge write", startup_q, 32'hDEADBEEF);

        $display("phase 2: sim/macro-smoke/smoke.py OPS replay (10 cycles, 7 Q words)");
        smoke_start = $time;
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

        if ($time - smoke_start != 10*T) begin
            errors = errors + 1;
            $display("  FAIL OPS replay took %0d ns, expected %0d ns", $time - smoke_start, 10*T);
        end

        $display("phase 3: per-bit mask enables bits 0 and 8");
        op(1'b0, 1'b0, 8'h11, 32'h00000000, 32'h00000000);        // clear cell 0x11
        check("Q holds across the clear write", Q, 32'hFFFFBEEF);
        op(1'b0, 1'b0, 8'h11, 32'hFFFFFFFF, 32'hFFFFFEFE);        // write only bits 0 and 8
        op(1'b0, 1'b1, 8'h11, 32'h00000000, M32);
        check("masked write landed bits 0 and 8 only", Q, 32'h00000101);

        $display("phase 4: WEN all ones with GWEN=0 is a no-op write");
        op(1'b0, 1'b0, 8'h22, 32'hCAFEBABE, 32'h00000000);
        op(1'b0, 1'b1, 8'h22, 32'h00000000, M32);
        check("read 0x22 before the no-op", Q, 32'hCAFEBABE);
        op(1'b0, 1'b0, 8'h22, 32'h600DF00D, M32);                 // the no-op "write"
        check("Q holds across the no-op write", Q, 32'hCAFEBABE);
        op(1'b0, 1'b1, 8'h22, 32'h00000000, M32);
        check("cell 0x22 unchanged by the no-op", Q, 32'hCAFEBABE);

        if (errors == 0) begin
            $display("TB-RESULT: PASS (all sram_256x32 model checks)");
            $finish;
        end else begin
            $display("TB-RESULT: FAIL (%0d check error(s))", errors);
            $finish;
        end
    end

endmodule

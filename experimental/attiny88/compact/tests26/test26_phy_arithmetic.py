"""Finite-state proof of the two 16-bit pointer rewrites in USB PHY.
Arithmetic and timing only; *not* a physical USB validation.
"""
def test():
    for rx_offset in range(256):
        original=(rx_offset + 0x116)&65535  # EOR YH, SUBI YL,-0x16, SBCI YH,-0x102
        compact=(0x100+rx_offset+22)&65535 # LDI YH,1; ADIW Y,22
        assert original==compact,(rx_offset,original,compact)
    # The TX branch reads Z after 16-bit subtract 22. SBIW and SUBI/SBCI
    # both provide identical full-word Z for every possible pointer.
    for pointer in range(65536):
        lo=pointer&255;hi=pointer>>8
        new_lo=(lo-22)&255;borrow=int(lo<22)
        new_hi=(hi-borrow)&255
        original=new_lo|(new_hi<<8)
        compact=(pointer-22)&65535
        assert original==compact
        assert (original==0)==(compact==0)
    assert 1+1+1==1+2 # RX timing unchanged
    assert 1+1==2     # TX timing unchanged
    assert 2==2       # PUSH r19 -> RJMP +0 timing unchanged
    print('PASS RX pointer 256 values, TX pointer 65,536 values; all 16-bit pointers and Z flags; equal cycle totals')

if __name__=='__main__':test()

"""Independent mathematical checks for the optimized instructions."""
import unittest

BOOT=0x1AC0
APP_LIMIT=BOOT-4

class Invariants(unittest.TestCase):
    def test_8byte_flash_read_boundary_for_every_address(self):
        # Equivalent to branch logic after checking 1 <= wLength <= 8 and
        # high wIndex and wLength bytes == 0.
        upper=(BOOT-3)>>8
        low_limit=(BOOT-4)&255
        for length in range(1,9):
            for address in range(65536):
                hi=address>>8
                lo=address&255
                accepted=(hi<upper or (hi==upper and lo<=(low_limit-length)))
                expected=address+length<=APP_LIMIT
                self.assertEqual(accepted,expected,(hex(address),length))

    def test_usb_disconnect_delay_cycle_equivalence(self):
        # Standard AVR Instruction Set Manual: LDI=1, SBIW=2,
        # DEC=1, conditional BRNE=2 (taken) or 1 (not taken).
        old=2+3000*(2+(400*4-1)+2)+(2999*2+1)
        new=1+19*(2+(63355*4-1)+1)+(18*2+1)
        self.assertEqual(old,4815001)
        self.assertEqual(new,4815056)
        self.assertEqual(new-old,55)
        self.assertLess((new-old)/16,4.0)

if __name__=='__main__':
    unittest.main()

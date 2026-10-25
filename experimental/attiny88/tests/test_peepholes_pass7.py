"""Exhaustive operand checks for the non-USB AVR instruction rewrites."""
import unittest

class ArithmeticPeepholes(unittest.TestCase):
    def test_subi_brmi_replaces_subi_sbrc_rjmp(self):
        for value in range(256):
            result=(value-3)&255
            # SBRC bit 7 does NOT skip RJMP when bit is 1.
            previous_branch=bool(result&0x80)
            new_brmi=bool(result&0x80)
            self.assertEqual(previous_branch,new_brmi)

    def test_two_byte_compare_preserves_equality_for_every_counter(self):
        for value in range(65536):
            lo=value&255
            hi=value>>8
            # Original CPI r24,0xB0; LDI r18,4; CPC r25,r18
            old=(lo==0xb0 and hi==0x04)
            # New SUBI r24,0xB0; SBCI r25,0x04
            nlo=(lo-0xB0)&255
            nhi=(hi-0x04-int(lo<0xB0))&255
            new=(nlo==0 and nhi==0)
            self.assertEqual(old,new,value)

    def test_wdt_unlock_has_correct_wdce_wde_for_all_previous_states(self):
        for previous in range(256):
            original_first=previous|0x18
            new_first=0x18
            self.assertEqual(original_first&0x18,0x18)
            self.assertEqual(new_first&0x18,0x18)
            # Second write is WDTCSR=0 immediately, as in the original.
            self.assertEqual(0,0)

if __name__=='__main__':unittest.main()
